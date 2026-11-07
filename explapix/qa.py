"""Verificador automático de cada video contra config/reglas.yaml.

  python -m explapix.qa out/<carpeta>      # uno
  python -m explapix.qa --all              # todos
Guarda el resultado en meta.json["qa"] = {"ok", "checks": [{id, label, ok, detail, fix}], "at"}.
`fix` dice cómo se corrige solo: remix (re-mezcla), tts (voz + render), render, guion (Claude).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SAFE_SINCE = datetime(2026, 11, 6, 17, 12).timestamp()   # renders con zona segura desde aquí


def reglas() -> dict:
    return yaml.safe_load((ROOT / "config" / "reglas.yaml").read_text(encoding="utf-8"))


def _p(r, sec, key, default=None):
    return ((r.get(sec) or {}).get("parametros") or {}).get(key, default)


def _json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _dur(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def _loudness(p: Path) -> tuple[float, float]:
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", "loudnorm=print_format=json", "-f",
                          "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)
    d = json.loads(m.group(0)) if m else {}
    return float(d.get("input_i", -99)), float(d.get("input_tp", 0))


def _silences(p: Path, min_d=0.15) -> int:
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", f"silencedetect=n=-40dB:d={min_d}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    return err.count("silence_start")


def _transcribe(p: Path) -> str:
    py = ROOT / ".venv-tts" / "bin" / "python"
    code = ("import sys,librosa\nfrom faster_whisper import WhisperModel\n"
            "m=WhisperModel('small',device='cpu',compute_type='int8')\n"
            "a,_=librosa.load(sys.argv[1],sr=16000)\n"
            "print(' '.join(s.text for s in m.transcribe(a,language='es')[0]))")
    r = subprocess.run([str(py), "-c", code, str(p)], capture_output=True, text=True, timeout=900)
    return r.stdout.strip()


def _words(t: str) -> list[str]:
    from explapix import textnorm  # noqa: PLC0415
    return re.sub(r"[^a-záéíóúñü ]", " ", textnorm.normalize(t).lower()).split()


def check(folder: Path, whisper: bool = True) -> dict:
    import difflib  # noqa: PLC0415
    r = reglas()
    meta = _json(folder / "meta.json", {}) or {}
    sb = _json(folder / "storyboard.json", {}) or {}
    timing = _json(folder / "timing.json", {}) or {}
    events = _json(folder / "sfx_events.json", []) or []
    segs, tsegs = sb.get("segments", []), timing.get("segments", [])
    final = folder / "final.mp4"
    checks = []

    def add(cid, label, ok, detail="", fix=""):
        checks.append({"id": cid, "label": label, "ok": bool(ok), "detail": detail, "fix": "" if ok else fix})

    # --- duración
    dur = _dur(final) if final.exists() else 0
    dmin, dmax = _p(r, "guion", "duracion_min_s", 61), _p(r, "guion", "duracion_max_s", 175)
    add("duracion", f"Duración entre {dmin} y {dmax} s", dmin <= dur <= dmax + 3, f"{dur:.1f} s", "guion")

    # --- marca
    nombre = _p(r, "marca", "nombre", "Factos Didácticos")
    textos = " ".join([meta.get("title", ""), meta.get("description", ""), sb.get("title", ""),
                       " ".join(s.get("narration", "") for s in segs)])
    prohibidas = [w for w in _p(r, "marca", "prohibido", []) if w in textos]
    tag = _p(r, "marca", "hashtag", "#FactosDidacticos")
    desc = meta.get("description", "") or sb.get("description", "")
    tag_ok = tag.lower() in desc.lower()
    add("marca", f"Marca correcta ({nombre}, {tag}, sin nombres internos)", tag_ok and not prohibidas,
        "prohibidas: " + ", ".join(prohibidas) if prohibidas else ("" if tag_ok else f"falta {tag} en la descripción"),
        "guion")

    # --- CTA
    starts, t = [], 0.0
    for x in tsegs:
        starts.append(t)
        t += x["duration"]
    total = t or dur or 1
    ctas = [(i, s.get("cta"), starts[i] if i < len(starts) else 0, s.get("narration", ""))
            for i, s in enumerate(segs) if s.get("cta")]
    pre = _p(r, "cta", "sin_cta_antes_de_s", 5)
    add("cta_inicio", f"Sin CTA en los primeros {pre} s", all(st >= pre for _, _, st, _ in ctas),
        ", ".join(f"{k} en {st:.0f}s" for _, k, st, _ in ctas if st < pre), "guion")
    mx = _p(r, "cta", "max_hablados", 3)
    add("cta_cantidad", f"Entre 1 y {mx} CTA hablados", 1 <= len(ctas) <= mx, f"{len(ctas)} CTA", "guion")
    frase = _p(r, "cta", "guardar_frase", "Guarda este video para").lower()
    w0, w1 = _p(r, "cta", "guardar_ventana", [0.2, 0.42])
    g = [c for c in ctas if c[1] == "guardar"]
    gok = bool(g) and frase in g[0][3].lower() and w0 <= g[0][2] / total <= w1
    add("cta_guardar", f"Guardar ({int(w0*100)}-{int(w1*100)} %) con «{frase.capitalize()}…»", gok,
        (f"en {g[0][2]:.0f} s ({g[0][2]/total:.0%})" + ("" if frase in g[0][3].lower() else "; frase distinta"))
        if g else "no hay CTA de guardar", "guion")
    c0, c1 = _p(r, "cta", "comentar_ventana", [0.45, 0.72])
    c = [x for x in ctas if x[1] == "comentar"]
    cok = bool(c) and "?" in c[0][3] and c0 <= c[0][2] / total <= c1
    add("cta_comentar", f"Comentar ({int(c0*100)}-{int(c1*100)} %) con pregunta", cok,
        f"en {c[0][2]:.0f} s ({c[0][2]/total:.0%})" if c else "no hay CTA de comentar", "guion")
    fd = _p(r, "cta", "final_desde", 0.7)
    f = [x for x in ctas if x[1] in ("compartir", "seguir")]
    add("cta_final", f"Compartir/seguir después del {int(fd*100)} %", bool(f) and f[-1][2] / total >= fd,
        f"en {f[-1][2]:.0f} s ({f[-1][2]/total:.0%})" if f else "no hay CTA de compartir/seguir", "guion")
    cebo = [pat for pat in _p(r, "cta", "cebo_prohibido", []) if re.search(pat, textos, re.I)]
    add("sin_cebo", "Sin cebo de interacción", not cebo, ", ".join(cebo), "guion")
    icons = [e for e in events if str(e.get("kind", "")).startswith("cta_")]
    add("cta_iconos", "Cada CTA con su ícono en pantalla", len(icons) >= len(ctas) and bool(ctas),
        f"{len(icons)} íconos / {len(ctas)} CTA", "render")

    # --- zona segura
    silent = next(folder.glob("media/videos/*/*/silent.mp4"), None)
    safe = any(e.get("kind") == "layout_safe" for e in events) or (
        silent is not None and silent.stat().st_mtime > SAFE_SINCE)
    add("zona_segura", "Encuadre dentro de la zona segura", safe, "", "render")

    # --- audio
    if final.exists():
        lufs, tp = _loudness(final)
        lo, hi = _p(r, "audio", "lufs", [-18.5, -13.5])
        pk = _p(r, "audio", "pico_max_db", -1.0)
        add("audio_niveles", f"Volumen {lo} a {hi} LUFS y picos < {pk} dB", lo <= lufs <= hi and tp < pk,
            f"{lufs:.1f} LUFS, pico {tp:.1f} dB", "remix")
    from explapix import music  # noqa: PLC0415
    lib = music.library()
    mname = meta.get("music")
    add("musica_licencia", "Música con licencia comercial", bool(mname) and lib.get(mname, {}).get("commercial", False),
        mname or "sin música", "remix")
    add("efectos", "Efectos de sonido presentes", bool(meta.get("sfx")) and bool(events), "", "remix")

    # --- voz
    narr = folder / "audio" / "narration.wav"
    if whisper and narr.exists():
        ref = " ".join(x.get("spoken") or x.get("text", "") for x in tsegs)
        hyp = _transcribe(narr)
        ratio = difflib.SequenceMatcher(None, _words(ref), _words(hyp)).ratio() if hyp else 0
        mn = _p(r, "voz", "coincidencia_min", 0.95)
        add("voz_transcripcion", f"La voz dice el guion (Whisper ≥ {int(mn*100)} %)", ratio >= mn,
            f"{ratio:.1%}", "tts")
    if narr.exists():
        marks = sum(len(re.findall(r"[.,;:?!]", x.get("spoken") or x.get("text", ""))) for x in tsegs)
        sil = _silences(narr)
        add("voz_pausas", "Pausas en la puntuación", sil >= 0.6 * marks, f"{sil} pausas / {marks} signos", "tts")

    # --- textos para redes
    cap = meta.get("ig_caption", "")
    if cap:
        lines = [l for l in cap.splitlines() if l.strip()]
        head = " ".join(lines[:2]).lower()
        body = [l for l in lines if not l.strip().startswith("#")]
        cta_ok = any(k in head for k in ("guarda", "compárte", "comparte", "mándaselo", "síguenos"))
        q_ok = bool(body) and "?" in body[-1]
        pin = meta.get("pinned_comment", "")
        add("caption", "Caption con CTA arriba y pregunta al final; comentario fijado con pregunta",
            cta_ok and q_ok and "?" in pin, "" if cta_ok and q_ok else "revisar caption", "textos")

    ok = all(c["ok"] for c in checks)
    return {"ok": ok, "checks": checks, "passed": sum(c["ok"] for c in checks), "total": len(checks),
            "at": datetime.now().isoformat(timespec="seconds")}


def save(folder: Path, res: dict) -> None:
    mf = folder / "meta.json"
    meta = _json(mf, {}) or {}
    meta["qa"] = res
    mf.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    args = sys.argv[1:]
    folders = sorted(d for d in (ROOT / "out").glob("2*") if d.is_dir() and (d / "final.mp4").exists()) \
        if "--all" in args else [Path(a) for a in args if not a.startswith("--")]
    print("[1/1] Verificación", flush=True)
    for f in folders:
        res = check(f, whisper="--no-whisper" not in args)
        save(f, res)
        bad = [c["id"] for c in res["checks"] if not c["ok"]]
        print(f"   {f.name}: {res['passed']}/{res['total']} " + ("✓" if res["ok"] else "✗ " + ", ".join(bad)),
              flush=True)


if __name__ == "__main__":
    main()
