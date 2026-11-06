"""Explapix Studio: panel web para revisar y controlar el flujo del canal.

Arranque:  .venv/bin/python -m uvicorn web.app:app --host 0.0.0.0 --port 8097
Se usa por Tailscale (http://100.96.241.48:8097). Protegido con usuario/contraseña
(usuario EXPLAPIX_PANEL_USER, por defecto "magne"; contraseña en secrets/panel_password).
Nunca sirve secrets/ ni .env: los archivos solo salen por rutas explícitas y validadas.
"""
from __future__ import annotations

import base64
import json
import os
import re
import secrets as pysecrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get("EXPLAPIX_OUT", ROOT / "out"))
SECRETS = Path(os.environ.get("EXPLAPIX_SECRETS_DIR", ROOT / "secrets"))
ENV_FILE = Path(os.environ.get("EXPLAPIX_ENV_FILE", ROOT / ".env"))
STUDIO = OUT / "_studio"
VOICES_OUT = OUT / "voces"
PY = os.environ.get("EXPLAPIX_PYTHON", sys.executable)
USER = os.environ.get("EXPLAPIX_PANEL_USER", "magne")
VIDEO_RE = re.compile(r"^\d{8}-\d{4}-[a-z0-9-]+$")
SAFE_FILE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
STEP_RE = re.compile(r"\[(\d)/(\d)\]\s*(.+)")
QUOTA_LIMIT = 10_000

# ---------------------------------------------------------------- utilidades


def read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def panel_password() -> str:
    f = SECRETS / "panel_password"
    if not f.exists():
        SECRETS.mkdir(parents=True, exist_ok=True)
        f.write_text(pysecrets.token_urlsafe(14) + "\n")
        f.chmod(0o600)
    return f.read_text().strip()


def read_env() -> dict[str, str]:
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def write_env(updates: dict[str, str]) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    done = set()
    for i, line in enumerate(lines):
        k = line.split("=", 1)[0].strip()
        if k in updates and not line.strip().startswith("#"):
            lines[i] = f"{k}={updates[k]}"
            done.add(k)
    lines += [f"{k}={v}" for k, v in updates.items() if k not in done]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV_FILE.chmod(0o600)


def video_dir(vid: str) -> Path:
    if not VIDEO_RE.match(vid) or not (OUT / vid).is_dir():
        raise HTTPException(404, "Video no encontrado")
    return OUT / vid


def video_status(meta: dict, d: Path) -> str:
    if not (d / "final.mp4").exists():
        return "error" if (d / "render_error.log").exists() else "incompleto"
    if meta.get("youtube_id"):
        return {"public": "publico", "unlisted": "no_listado"}.get(meta.get("privacy"), "subido_privado")
    return {"approved": "aprobado", "rejected": "rechazado"}.get(
        meta.get("review", {}).get("status"), "generado")


def video_summary(d: Path) -> dict:
    meta = read_json(d / "meta.json", {}) or {}
    sb = read_json(d / "storyboard.json", {}) or {}
    timing = read_json(d / "timing.json", {}) or {}
    created = meta.get("created") or datetime.strptime(d.name[:13], "%Y%m%d-%H%M").isoformat()
    return {
        "id": d.name,
        "title": meta.get("title") or sb.get("title") or d.name,
        "topic": meta.get("topic") or sb.get("topic", ""),
        "created": created,
        "duration": meta.get("duration") or timing.get("total"),
        "engine": meta.get("engine") or timing.get("engine") or "piper",
        "status": video_status(meta, d),
        "youtube_id": meta.get("youtube_id"),
        "privacy": meta.get("privacy"),
        "review": meta.get("review"),
        "has_video": (d / "final.mp4").exists(),
    }


def list_videos() -> list[dict]:
    if not OUT.exists():
        return []
    ds = [d for d in OUT.iterdir() if d.is_dir() and VIDEO_RE.match(d.name)]
    return sorted((video_summary(d) for d in ds), key=lambda v: v["id"], reverse=True)


# ---------------------------------------------------------------- cola de trabajos

class Jobs:
    """Cola persistente (JSON), un trabajo a la vez (GPU/CPU compartida)."""

    def __init__(self):
        self.file = STUDIO / "jobs.json"
        self.logs = STUDIO / "logs"
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.proc: subprocess.Popen | None = None
        self.jobs: list[dict] = read_json(self.file, []) or []
        for j in self.jobs:  # lo que estaba corriendo cuando se apagó el panel
            if j["status"] == "running":
                j.update(status="error", error="Interrumpido (el panel se reinició)")
        self.save()
        self.thread: threading.Thread | None = None

    def start(self):
        if not self.thread:
            self.thread = threading.Thread(target=self.loop, daemon=True)
            self.thread.start()

    def save(self):
        with self.lock:
            write_json(self.file, self.jobs[-300:])

    def add(self, kind: str, title: str, cmd: list[str], env: dict | None = None,
            meta: dict | None = None) -> dict:
        j = {"id": uuid.uuid4().hex[:10], "kind": kind, "title": title, "cmd": cmd,
             "env": env or {}, "meta": meta or {}, "status": "queued",
             "created": datetime.now().isoformat(timespec="seconds"), "started": None,
             "finished": None, "step": None, "result": None, "error": None}
        with self.lock:
            self.jobs.append(j)
            self.save()
        self.wake.set()
        return {k: v for k, v in j.items() if k not in ("cmd", "env")}

    def get(self, jid: str) -> dict:
        for j in self.jobs:
            if j["id"] == jid:
                return j
        raise HTTPException(404, "Trabajo no encontrado")

    def cancel(self, jid: str) -> dict:
        with self.lock:
            j = self.get(jid)
            if j["status"] == "queued":
                j.update(status="cancelled", finished=datetime.now().isoformat(timespec="seconds"))
            elif j["status"] == "running" and self.proc:
                j["cancel"] = True
                os.killpg(self.proc.pid, signal.SIGTERM)
            self.save()
            return j

    def log_path(self, jid: str) -> Path:
        return self.logs / f"{jid}.log"

    def loop(self):
        while True:
            with self.lock:
                j = next((x for x in self.jobs if x["status"] == "queued"), None)
            if not j:
                self.wake.wait(2)
                self.wake.clear()
                continue
            self.run(j)

    def run(self, j: dict):
        self.logs.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env.update(read_env())
        env.update(j["env"])
        env["PYTHONUNBUFFERED"] = "1"
        with self.lock:
            j.update(status="running", started=datetime.now().isoformat(timespec="seconds"))
            self.save()
        log = self.log_path(j["id"])
        try:
            with open(log, "w", encoding="utf-8") as fh:
                self.proc = subprocess.Popen(j["cmd"], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT, text=True, bufsize=1,
                                             start_new_session=True)
                for line in self.proc.stdout:
                    fh.write(line)
                    fh.flush()
                    m = STEP_RE.search(line)
                    if m:
                        j["step"] = {"n": int(m.group(1)), "of": int(m.group(2)),
                                     "name": m.group(3).strip()}
                    m = re.search(r"Listo: .*/out/([^/]+)/final\.mp4", line)
                    if m:
                        j["result"] = m.group(1)
                rc = self.proc.wait()
            with self.lock:
                if j.get("cancel"):
                    j["status"] = "cancelled"
                elif rc == 0:
                    j["status"] = "done"
                else:
                    j["status"] = "error"
                    tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()
                    j["error"] = (tail[-1] if tail else f"código {rc}")[:300]
                self.after(j)
        except Exception as e:  # noqa: BLE001
            j.update(status="error", error=str(e)[:300])
        finally:
            self.proc = None
            with self.lock:
                j["finished"] = datetime.now().isoformat(timespec="seconds")
                self.save()

    @staticmethod
    def after(j: dict):
        """Efectos al terminar: enlazar el video regenerado con el original."""
        src = j["meta"].get("replaces")
        if j["status"] == "done" and src and j.get("result") and (OUT / src).is_dir():
            mf = OUT / src / "meta.json"
            meta = read_json(mf, {}) or {}
            meta.setdefault("review", {})["replaced_by"] = j["result"]
            write_json(mf, meta)
            nf = OUT / j["result"] / "meta.json"
            nmeta = read_json(nf, {}) or {}
            nmeta["replaces"] = src
            write_json(nf, nmeta)


jobs = Jobs()

# ---------------------------------------------------------------- app y seguridad

@asynccontextmanager
async def lifespan(_app):
    panel_password()
    jobs.start()
    yield


app = FastAPI(title="Explapix Studio", docs_url=None, redoc_url=None, openapi_url=None,
              lifespan=lifespan)


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    ok = False
    h = request.headers.get("authorization", "")
    if h.lower().startswith("basic "):
        try:
            u, _, p = base64.b64decode(h[6:]).decode().partition(":")
            ok = pysecrets.compare_digest(u, USER) and pysecrets.compare_digest(p, panel_password())
        except Exception:  # noqa: BLE001
            ok = False
    if not ok:
        return Response("Autenticación requerida", status_code=401,
                        headers={"WWW-Authenticate": 'Basic realm="Explapix Studio", charset="UTF-8"'})
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


# ---------------------------------------------------------------- videos

@app.get("/api/videos")
def api_videos():
    return list_videos()


@app.get("/api/videos/{vid}")
def api_video(vid: str):
    d = video_dir(vid)
    sb = read_json(d / "storyboard.json", {}) or {}
    timing = read_json(d / "timing.json", {}) or {}
    meta = read_json(d / "meta.json", {}) or {}
    segs = []
    for i, s in enumerate(sb.get("segments", [])):
        t = timing.get("segments", [])
        segs.append({**s, "duration": t[i]["duration"] if i < len(t) else None})
    err = d / "render_error.log"
    scene = d / "scene.py"
    return {**video_summary(d), "description": meta.get("description") or sb.get("description", ""),
            "tags": meta.get("tags") or sb.get("tags", []), "segments": segs,
            "notes": meta.get("notes"), "replaces": meta.get("replaces"),
            "scene": scene.read_text(encoding="utf-8") if scene.exists() else "",
            "error_log": err.read_text(encoding="utf-8")[-6000:] if err.exists() else ""}


@app.put("/api/videos/{vid}/meta")
def api_video_meta(vid: str, body: dict = Body(...)):
    d = video_dir(vid)
    meta = read_json(d / "meta.json", None)
    if meta is None:
        raise HTTPException(409, "Este video no terminó de generarse")
    if meta.get("youtube_id"):
        raise HTTPException(409, "Ya está en YouTube: edítalo desde YouTube Studio")
    title = str(body.get("title", meta["title"])).strip()
    if not title or len(title) > 100:
        raise HTTPException(422, "El título debe tener entre 1 y 100 caracteres")
    tags = body.get("tags", meta.get("tags", []))
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    meta.update(title=title, description=str(body.get("description", meta["description"]))[:5000],
                tags=tags[:30])
    write_json(d / "meta.json", meta)
    return video_summary(d)


@app.post("/api/videos/{vid}/review")
def api_review(vid: str, body: dict = Body(...)):
    d = video_dir(vid)
    status = body.get("status")
    if status not in ("approved", "rejected", "pending"):
        raise HTTPException(422, "status debe ser approved, rejected o pending")
    meta = read_json(d / "meta.json", None)
    if meta is None:
        raise HTTPException(409, "Este video no terminó de generarse")
    note = str(body.get("note", "")).strip()[:1000]
    if status == "pending":
        meta.pop("review", None)
    else:
        meta["review"] = {**meta.get("review", {}), "status": status, "note": note,
                          "at": datetime.now().isoformat(timespec="seconds")}
    write_json(d / "meta.json", meta)
    return video_summary(d)


@app.post("/api/videos/{vid}/regenerate")
def api_regenerate(vid: str, body: dict = Body(default={})):
    """mode=ai: nuevo guion+animación con la nota como indicación (usa Claude).
    mode=voice: misma escena y guion, solo vuelve a generar voz y render (sin costo)."""
    d = video_dir(vid)
    sb = read_json(d / "storyboard.json", {}) or {}
    meta = read_json(d / "meta.json", {}) or {}
    mode = body.get("mode", "ai")
    note = str(body.get("note") or meta.get("review", {}).get("note", "")).strip()[:1000]
    env = _tts_env(body)
    q = _quality(body)
    if mode == "voice":
        if not (d / "scene.py").exists():
            raise HTTPException(409, "No hay escena para re-renderizar")
        cmd = [PY, "make_video.py", "--storyboard", str(d / "storyboard.json"), "--scene",
               str(d / "scene.py"), "--quality", q]
        title = f"Re-render: {sb.get('topic', vid)}"
    elif mode == "ai":
        _need_anthropic()
        cmd = [PY, "make_video.py", "--topic", sb.get("topic") or meta.get("topic") or vid,
               "--quality", q] + (["--notes", note] if note else [])
        title = f"Regenerar: {sb.get('topic', vid)}"
    else:
        raise HTTPException(422, "mode debe ser ai o voice")
    return jobs.add("video", title, cmd, env, {"replaces": vid, "note": note})


@app.post("/api/videos/{vid}/upload")
def api_upload(vid: str, body: dict = Body(...)):
    d = video_dir(vid)
    privacy = body.get("privacy", "private")
    if privacy not in ("private", "unlisted", "public"):
        raise HTTPException(422, "Privacidad inválida")
    if body.get("confirm") is not True:
        raise HTTPException(422, "Falta la confirmación explícita")
    meta = read_json(d / "meta.json", None)
    if meta is None or not (d / "final.mp4").exists():
        raise HTTPException(409, "El video no está listo")
    if meta.get("youtube_id"):
        raise HTTPException(409, "Ya está subido")
    if not (SECRETS / "token.json").exists():
        raise HTTPException(409, "Primero conecta YouTube en Sistema")
    if any(j["kind"] == "upload" and j["meta"].get("video") == vid and j["status"] in
           ("queued", "running") for j in jobs.jobs):
        raise HTTPException(409, "Ya hay una subida en cola para este video")
    return jobs.add("upload", f"Subir ({privacy}): {meta['title']}",
                    [PY, "upload.py", str(d), "--privacy", privacy], meta={"video": vid})


@app.delete("/api/videos/{vid}")
def api_delete(vid: str):
    d = video_dir(vid)
    trash = OUT / "_papelera"
    trash.mkdir(exist_ok=True)
    shutil.move(str(d), str(trash / d.name))
    return {"ok": True}


@app.get("/media/{vid}/video.mp4")
def media_video(vid: str):
    f = video_dir(vid) / "final.mp4"
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(f, media_type="video/mp4")


@app.get("/media/{vid}/thumb.jpg")
def media_thumb(vid: str):
    d = video_dir(vid)
    th, src = d / "thumb.jpg", d / "final.mp4"
    if not src.exists():
        raise HTTPException(404)
    if not th.exists() or th.stat().st_mtime < src.stat().st_mtime:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "4", "-i", str(src), "-frames:v", "1",
                        "-vf", "scale=360:-2", "-q:v", "4", str(th)], check=False)
    if not th.exists():
        raise HTTPException(404)
    return FileResponse(th, media_type="image/jpeg", headers={"Cache-Control": "max-age=60"})


# ---------------------------------------------------------------- nuevos videos y trabajos

def _need_anthropic():
    if not (read_env().get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")):
        raise HTTPException(409, "Falta ANTHROPIC_API_KEY (ponla en Sistema)")


def _tts_env(body: dict) -> dict:
    eng = body.get("engine")
    if eng and eng not in ("chatterbox", "kokoro", "piper"):
        raise HTTPException(422, "Voz inválida")
    return {"EXPLAPIX_TTS": eng} if eng else {}


def _quality(body: dict) -> str:
    q = body.get("quality", "hd")
    if q not in ("hd", "draft"):
        raise HTTPException(422, "Calidad inválida")
    return q


@app.post("/api/jobs")
def api_new_job(body: dict = Body(...)):
    kind = body.get("kind", "video")
    env, q = _tts_env(body), _quality(body)
    if kind == "example":
        ex = ROOT / "examples" / "refrigerador"
        return [jobs.add("video", "Ejemplo: refrigerador (sin IA)",
                         [PY, "make_video.py", "--storyboard", str(ex / "storyboard.json"),
                          "--scene", str(ex / "scene.py"), "--quality", q], env)]
    if kind != "video":
        raise HTTPException(422, "Tipo de trabajo inválido")
    topics = body.get("topics") or []
    if isinstance(topics, str):
        topics = topics.splitlines()
    topics = [t.strip() for t in topics if t.strip()][:20]
    if not topics:
        raise HTTPException(422, "Escribe al menos un tema")
    _need_anthropic()
    notes = str(body.get("notes", "")).strip()[:1000]
    return [jobs.add("video", t, [PY, "make_video.py", "--topic", t, "--quality", q] +
                     (["--notes", notes] if notes else []), env) for t in topics]


@app.get("/api/jobs")
def api_jobs():
    return [{k: v for k, v in j.items() if k not in ("cmd", "env")} for j in reversed(jobs.jobs[-100:])]


@app.get("/api/jobs/{jid}/log")
def api_job_log(jid: str, offset: int = 0):
    jobs.get(jid)
    f = jobs.log_path(jid)
    if not f.exists():
        return {"text": "", "offset": 0}
    data = f.read_bytes()
    offset = max(0, min(offset, len(data)))
    return {"text": data[offset:].decode("utf-8", errors="replace"), "offset": len(data)}


@app.post("/api/jobs/{jid}/cancel")
def api_job_cancel(jid: str):
    j = jobs.cancel(jid)
    return {k: v for k, v in j.items() if k not in ("cmd", "env")}


# ---------------------------------------------------------------- comentarios

DRAFTS = OUT / "comment_drafts.json"


@app.get("/api/comments")
def api_comments():
    return read_json(DRAFTS, []) or []


@app.put("/api/comments/{cid}")
def api_comment_edit(cid: str, body: dict = Body(...)):
    drafts = read_json(DRAFTS, []) or []
    for d in drafts:
        if d.get("comment_id") == cid:
            if d.get("sent"):
                raise HTTPException(409, "Esa respuesta ya se envió")
            if "reply" in body:
                d["reply"] = str(body["reply"]).strip()[:1500]
            if "approved" in body:
                d["approved"] = bool(body["approved"])
            if "discarded" in body:
                d["discarded"] = bool(body["discarded"])
                if d["discarded"]:
                    d["approved"] = False
            write_json(DRAFTS, drafts)
            return d
    raise HTTPException(404, "Comentario no encontrado")


@app.post("/api/comments/fetch")
def api_comments_fetch():
    _need_anthropic()
    if not (SECRETS / "token.json").exists():
        raise HTTPException(409, "Primero conecta YouTube en Sistema")
    return jobs.add("comments", "Buscar comentarios nuevos", [PY, "reply_comments.py"])


@app.post("/api/comments/send")
def api_comments_send(body: dict = Body(...)):
    if body.get("confirm") is not True:
        raise HTTPException(422, "Falta la confirmación explícita")
    n = sum(1 for d in read_json(DRAFTS, []) or [] if d.get("approved") and not d.get("sent")
            and not d.get("discarded"))
    if not n:
        raise HTTPException(409, "No hay respuestas aprobadas pendientes")
    return jobs.add("comments", f"Enviar {n} respuesta(s)", [PY, "reply_comments.py", "--send-approved"])


# ---------------------------------------------------------------- voces

VOICE_KEYS = ("EXPLAPIX_TTS", "EXPLAPIX_KOKORO_VOICE", "EXPLAPIX_CB_EXAGGERATION", "EXPLAPIX_CB_CFG")


@app.get("/api/voices")
def api_voices():
    env = read_env()
    files = []
    if VOICES_OUT.exists():
        for f in sorted(VOICES_OUT.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if f.suffix in (".wav", ".mp3") and not (f.suffix == ".wav" and f.with_suffix(".mp3").exists()):
                files.append({"name": f.name, "size": f.stat().st_size})
    ref = ROOT / "voices" / "ref.wav"
    return {"files": files, "settings": {k: env.get(k, "") for k in VOICE_KEYS},
            "default_engine": env.get("EXPLAPIX_TTS") or "chatterbox",
            "ref": {"exists": ref.exists(), "mtime": ref.stat().st_mtime if ref.exists() else None,
                    "custom": (ROOT / "voices" / "ref_propia.txt").exists()}}


@app.get("/media/voces/{name}")
def media_voice(name: str):
    if not SAFE_FILE_RE.match(name) or not name.endswith((".wav", ".mp3")):
        raise HTTPException(404)
    f = VOICES_OUT / name
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(f, media_type="audio/mpeg" if name.endswith(".mp3") else "audio/wav")


@app.get("/media/ref.wav")
def media_ref():
    f = ROOT / "voices" / "ref.wav"
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(f, media_type="audio/wav")


@app.put("/api/settings/voice")
def api_voice_settings(body: dict = Body(...)):
    upd = {}
    if "EXPLAPIX_TTS" in body:
        if body["EXPLAPIX_TTS"] not in ("chatterbox", "kokoro", "piper"):
            raise HTTPException(422, "Voz inválida")
        upd["EXPLAPIX_TTS"] = body["EXPLAPIX_TTS"]
    if "EXPLAPIX_KOKORO_VOICE" in body:
        if body["EXPLAPIX_KOKORO_VOICE"] not in ("em_alex", "ef_dora", "em_santa"):
            raise HTTPException(422, "Voz Kokoro inválida")
        upd["EXPLAPIX_KOKORO_VOICE"] = body["EXPLAPIX_KOKORO_VOICE"]
    for k, lo, hi in (("EXPLAPIX_CB_EXAGGERATION", 0.25, 1.5), ("EXPLAPIX_CB_CFG", 0.1, 1.0)):
        if k in body:
            v = float(body[k])
            if not lo <= v <= hi:
                raise HTTPException(422, f"{k} fuera de rango")
            upd[k] = f"{v:.2f}"
    write_env(upd)
    return api_voices()


@app.post("/api/voices/test")
def api_voice_test(body: dict = Body(...)):
    env = _tts_env(body)
    eng = env.get("EXPLAPIX_TTS") or read_env().get("EXPLAPIX_TTS") or "chatterbox"
    text = str(body.get("text", "")).strip()[:400]
    if not text:
        raise HTTPException(422, "Escribe una frase")
    name = f"prueba_{eng}_{datetime.now():%Y%m%d-%H%M%S}"
    out = VOICES_OUT / f"{name}.wav"
    script = (f"from pathlib import Path; from explapix import tts; import subprocess; "
              f"tts.synth({text!r}, Path({str(out)!r}), {eng!r}); "
              f"subprocess.run(['ffmpeg','-y','-v','error','-i',{str(out)!r},'-b:a','128k',"
              f"{str(out.with_suffix('.mp3'))!r}], check=True); print('Listo voz', flush=True)")
    return jobs.add("voice", f"Prueba de voz ({eng})", [PY, "-c", script], env, {"file": f"{name}.mp3"})


@app.post("/api/voices/ref")
async def api_voice_ref(file: UploadFile = File(...)):
    """Sube tu propia grabación (10-20 s, sin ruido) como timbre para Chatterbox."""
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "Archivo muy grande (máx. 25 MB)")
    tmpdir = STUDIO / "upload"
    tmpdir.mkdir(parents=True, exist_ok=True)
    src = tmpdir / f"ref_{uuid.uuid4().hex}"
    src.write_bytes(data)
    voices = ROOT / "voices"
    voices.mkdir(exist_ok=True)
    ref = voices / "ref.wav"
    if ref.exists() and not (voices / "ref_kokoro.wav").exists():
        shutil.copy(ref, voices / "ref_kokoro.wav")   # respaldo de la referencia anterior
    tmp_out = tmpdir / "ref_new.wav"
    p = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-t", "25", "-ac", "1",
                        "-ar", "24000", "-af", "loudnorm=I=-18", str(tmp_out)],
                       capture_output=True, text=True)
    src.unlink(missing_ok=True)
    if p.returncode != 0:
        raise HTTPException(422, "No pude leer ese audio. Usa wav, mp3, m4a u ogg.")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(tmp_out)], capture_output=True,
                               text=True).stdout or 0)
    if dur < 5:
        tmp_out.unlink(missing_ok=True)
        raise HTTPException(422, f"Muy corto ({dur:.1f} s). Graba al menos 8-10 s.")
    tmp_out.replace(ref)
    (voices / "ref_propia.txt").write_text(f"{file.filename} {datetime.now().isoformat()}\n")
    return {"ok": True, "duration": round(dur, 1)}


@app.post("/api/voices/ref/reset")
def api_voice_ref_reset():
    voices = ROOT / "voices"
    if (voices / "ref_kokoro.wav").exists():
        shutil.copy(voices / "ref_kokoro.wav", voices / "ref.wav")
    (voices / "ref_propia.txt").unlink(missing_ok=True)
    return {"ok": True}


# ---------------------------------------------------------------- sistema

def _gpu():
    try:
        q = "name,utilization.gpu,memory.used,memory.total,temperature.gpu"
        out = subprocess.run(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        n, u, mu, mt, t = [x.strip() for x in out.splitlines()[0].split(",")]
        return {"name": n, "util": int(u), "mem_used": int(mu), "mem_total": int(mt), "temp": int(t)}
    except Exception:  # noqa: BLE001
        return None


def _quota():
    sys.path.insert(0, str(ROOT))
    from explapix.youtube import QUOTA_FILE, quota_day  # noqa: PLC0415
    data = read_json(QUOTA_FILE, {}) or {}
    used = data.get(quota_day(), 0)
    return {"used": used, "limit": QUOTA_LIMIT, "uploads_left": max(0, (QUOTA_LIMIT - used) // 1600),
            "day": quota_day()}


@app.get("/api/status")
def api_status():
    env = read_env()
    du = shutil.disk_usage(ROOT)
    out_size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file()) if OUT.exists() else 0
    running = next((j for j in jobs.jobs if j["status"] == "running"), None)
    return {
        "anthropic_key": bool(env.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")),
        "youtube_client": (SECRETS / "client_secret.json").exists(),
        "youtube_token": (SECRETS / "token.json").exists(),
        "tts": env.get("EXPLAPIX_TTS") or "chatterbox",
        "gpu": _gpu(),
        "disk": {"free_gb": round(du.free / 1e9, 1), "total_gb": round(du.total / 1e9, 1),
                 "out_gb": round(out_size / 1e9, 2)},
        "quota": _quota(),
        "queue": {"queued": sum(j["status"] == "queued" for j in jobs.jobs),
                  "running": running and {"id": running["id"], "title": running["title"],
                                          "step": running.get("step")}},
        "videos": len(list_videos()),
    }


@app.put("/api/settings/anthropic")
def api_set_anthropic(body: dict = Body(...)):
    key = str(body.get("key", "")).strip()
    if not re.match(r"^sk-ant-[A-Za-z0-9_\-]{20,}$", key):
        raise HTTPException(422, "Esa no parece una clave de Anthropic (empieza por sk-ant-)")
    write_env({"ANTHROPIC_API_KEY": key})
    return {"ok": True}


_flows: dict[str, object] = {}


@app.post("/api/youtube/auth-url")
def api_yt_auth_url():
    from google_auth_oauthlib.flow import Flow  # noqa: PLC0415
    sys.path.insert(0, str(ROOT))
    from explapix.youtube import SCOPES  # noqa: PLC0415
    cs = SECRETS / "client_secret.json"
    if not cs.exists():
        raise HTTPException(409, "Falta secrets/client_secret.json")
    flow = Flow.from_client_secrets_file(str(cs), SCOPES, redirect_uri="http://localhost:8765/")
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    _flows.clear()
    _flows[state] = flow
    return {"url": url}


@app.post("/api/youtube/auth-code")
def api_yt_auth_code(body: dict = Body(...)):
    from urllib.parse import parse_qs, urlparse  # noqa: PLC0415
    resp_url = str(body.get("url", "")).strip()
    qs = parse_qs(urlparse(resp_url).query)
    state = (qs.get("state") or [""])[0]
    flow = _flows.get(state)
    if not flow or "code" not in qs:
        raise HTTPException(422, "Pega la URL completa a la que te llevó Google (empieza por http://localhost:8765/?state=...)")
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"   # redirección local a localhost (app de escritorio)
    try:
        flow.fetch_token(authorization_response=resp_url)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Google rechazó el código: {e}") from e
    tok = SECRETS / "token.json"
    tok.write_text(flow.credentials.to_json())
    tok.chmod(0o600)
    _flows.clear()
    return {"ok": True}


# ---------------------------------------------------------------- frontend

STATIC = Path(__file__).resolve().parent / "static"


@app.get("/fonts/{name}")
def fonts(name: str):
    if name not in ("Fredoka.ttf", "Nunito.ttf"):
        raise HTTPException(404)
    return FileResponse(ROOT / "fonts" / name, media_type="font/ttf",
                        headers={"Cache-Control": "max-age=86400"})


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")


@app.exception_handler(HTTPException)
async def http_error(_, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
