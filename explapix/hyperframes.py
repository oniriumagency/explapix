"""Motor de animación alternativo: HyperFrames (HTML/SVG + GSAP renderizado con Chrome).

Convive con Manim: una escena .py se renderiza con Manim y una escena .js con HyperFrames
(explapix.render.render_scene decide por la extensión). La escena usa el kit hyperframes/kit.js, que copia
la estética y las reglas de explapix/kit.py (moods, cámara viva, caritas, CTA con flecha, subtítulos,
capítulos, cierre) y lee la zona segura de config/reglas.yaml.

Requisitos: Node 22+ y `npm ci` en hyperframes/ (lo hace setup_server.sh). Chrome lo descarga
HyperFrames la primera vez (`hyperframes browser ensure`). Telemetría y avisos de actualización apagados.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HF = ROOT / "hyperframes"
CLI = HF / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
QUALITY = {"draft": ("draft", 24), "hd": ("looks", 30)}
ENV = {"HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1", "HYPERFRAMES_NO_UPDATE_CHECK": "1",
       "HYPERFRAMES_SKIP_SKILLS": "1", "HYPERFRAMES_NO_AUTO_INSTALL": "1"}


def _env() -> dict:
    return dict(os.environ, **ENV)


def _node() -> str:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("HyperFrames necesita Node 22+ (no encontré `node`); corre setup_server.sh")
    v = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip().lstrip("v")
    if int((v.split(".") or ["0"])[0] or 0) < 22:
        raise RuntimeError(f"HyperFrames necesita Node 22+ (hay {v}); corre setup_server.sh")
    return node


def ready() -> tuple[bool, str]:
    """¿Está instalado el motor? (para el panel)."""
    try:
        _node()
    except RuntimeError as e:
        return False, str(e)
    if not CLI.exists():
        return False, "faltan los paquetes de hyperframes/ (corre: cd hyperframes && npm ci)"
    return True, ""


def ensure() -> tuple[str, str]:
    """Devuelve (node, chrome). Instala los paquetes fijados y Chrome si faltan."""
    node = _node()
    if not CLI.exists():
        subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=HF, check=True, env=_env())
    p = subprocess.run([node, str(CLI), "browser", "ensure"], cwd=HF, capture_output=True, text=True, env=_env())
    chrome = next((ln.strip() for ln in reversed((p.stdout or "").splitlines()) if ln.strip().startswith("/")), "")
    if not chrome:
        p = subprocess.run([node, str(CLI), "browser", "path"], cwd=HF, capture_output=True, text=True, env=_env())
        chrome = (p.stdout or "").strip().splitlines()[-1].strip() if p.stdout.strip() else ""
    if not chrome or not Path(chrome).exists():
        raise RuntimeError(f"No encontré Chrome para HyperFrames: {(p.stdout + p.stderr)[-500:]}")
    return node, chrome


def _reglas() -> dict:
    import yaml  # noqa: PLC0415
    return yaml.safe_load((ROOT / "config" / "reglas.yaml").read_text(encoding="utf-8"))


def config_for(workdir: Path, formato: str = "vertical") -> dict:
    """Datos que la escena necesita: duraciones reales del audio, textos, CTA y zona segura.

    formato "largo" = horizontal 16:9 (YouTube): como en kit.py, sin interfaz encima, solo el margen de TV del
    5 % y una franja de subtítulos más baja, con líneas más largas."""
    timing = json.loads((workdir / "timing.json").read_text(encoding="utf-8"))
    sbp = workdir / "storyboard.json"
    segs = json.loads(sbp.read_text(encoding="utf-8")).get("segments", []) if sbp.exists() else []
    r = _reglas()
    zona = ((r.get("zona_segura") or {}).get("parametros") or {})
    alt = (((r.get("cta") or {}).get("parametros") or {}).get("botones_altura") or {})
    tsegs = timing["segments"]
    largo = formato == "largo"
    zona_v = {k: float(zona.get(k, d)) for k, d in
              (("arriba", 0.12), ("abajo", 0.20), ("derecha", 0.15), ("izquierda", 0.05))}
    return {
        "formato": "largo" if largo else "vertical",
        "ancho": 1920 if largo else 1080,
        "alto": 1080 if largo else 1920,
        "duracion": round(sum(float(t["duration"]) for t in tsegs), 3),
        "segmentos": [{"duracion": float(t["duration"]), "texto": t.get("text", ""),
                       "cta": (segs[i].get("cta") or "") if i < len(segs) else ""} for i, t in enumerate(tsegs)],
        "zona": dict.fromkeys(zona_v, 0.05) if largo else zona_v,
        "franja_subtitulos": 1.1 * 120 if largo else 1.75 / 16 * 1920,   # CAPTION_BAND de kit.py, en px
        "caracteres_por_linea": 44 if largo else 22,
        "botones_altura": float(alt.get("general", 0.65)),
        "semilla": 7,
    }


def build_project(scene_file: Path, workdir: Path, formato: str = "vertical") -> Path:
    """Arma la carpeta del proyecto HyperFrames (workdir/hyperframes) con el kit, las fuentes y la escena."""
    proj = workdir / "hyperframes"
    if proj.exists():
        shutil.rmtree(proj)
    (proj / "fonts").mkdir(parents=True)
    for f in ("kit.js", "kit.css"):
        shutil.copy(HF / f, proj / f)
    shutil.copy(HF / "node_modules" / "gsap" / "dist" / "gsap.min.js", proj / "gsap.min.js")
    for f in ("Fredoka.ttf", "Nunito.ttf"):
        shutil.copy(ROOT / "fonts" / f, proj / "fonts" / f)
    shutil.copy(scene_file, proj / "escena.js")
    cfg = config_for(workdir, formato)
    html = (HF / "plantilla.html").read_text(encoding="utf-8")
    html = html.replace("__ANCHO__", str(cfg["ancho"])).replace("__ALTO__", str(cfg["alto"])).replace(
        "__ORIENTACION__", "landscape" if cfg["formato"] == "largo" else "portrait")
    html = html.replace("__DURACION__", str(cfg["duracion"])).replace(
        "__CONFIG__", json.dumps(cfg, ensure_ascii=False).replace("</", "<\\/"))
    (proj / "index.html").write_text(html, encoding="utf-8")
    (proj / "hyperframes.json").write_text(json.dumps({"media": {"autoProxy": False}}), encoding="utf-8")
    return proj


def inspect(proj: Path, node: str, chrome: str) -> dict:
    p = subprocess.run([node, str(HF / "inspeccionar.mjs"), str(proj), chrome], cwd=HF, capture_output=True,
                       text=True, timeout=900, env=_env())
    try:
        return json.loads(p.stdout)
    except ValueError:
        return {"ok": False, "error": (p.stdout + p.stderr)[-3000:] or f"código {p.returncode}"}


def layout_problems(workdir: Path) -> str:
    """Texto con lo que quedó fuera de la zona segura en el último render (vacío si nada)."""
    try:
        data = json.loads((workdir / "layout.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    fuera = data.get("fuera") or []
    if not fuera:
        return ""
    return "Texto fuera de la zona segura (muévelo hacia adentro o hazlo más chico):\n" + "\n".join(
        f"- «{x['texto']}» en t={x['t']} s, se sale por {x['borde']}" for x in fuera[:15])


def render_scene(scene_file: Path, workdir: Path, quality: str = "hd",
                 formato: str = "vertical") -> tuple[bool, str, Path | None]:
    """Mismo contrato que render.render_scene: (ok, log, video_sin_audio)."""
    scene_file, workdir = Path(scene_file).resolve(), Path(workdir).resolve()   # node corre desde hyperframes/
    try:
        node, chrome = ensure()
        proj = build_project(scene_file, workdir, formato)
    except (RuntimeError, OSError, subprocess.CalledProcessError, KeyError, ValueError) as e:
        return False, f"HyperFrames: {e}", None
    chk = subprocess.run([node, "--check", str(proj / "escena.js")], capture_output=True, text=True)
    if chk.returncode != 0:
        return False, "Error de sintaxis en escena.js:\n" + chk.stderr[-3000:], None
    info = inspect(proj, node, chrome)
    if not info.get("ok"):
        return False, "La escena falló al construirse en el navegador:\n" + str(info.get("error"))[-4000:], None
    eventos = [e for e in info.get("eventos", []) if e.get("kind") != "layout_safe_frame"]
    if not info.get("fuera"):
        eventos.insert(0, {"t": 0.0, "kind": "layout_safe", "gain": 0})
    (workdir / "sfx_events.json").write_text(json.dumps(sorted(eventos, key=lambda e: e["t"])), encoding="utf-8")
    dur = float(info.get("duracion") or 0)
    if dur > config_for(workdir, formato)["duracion"] + 0.05:     # la animación sigue tras la voz (pantalla final)
        idx = proj / "index.html"
        idx.write_text(re.sub(r'data-duration="[^"]*"', f'data-duration="{dur}"', idx.read_text(encoding="utf-8"), 1),
                       encoding="utf-8")
    (workdir / "layout.json").write_text(json.dumps({"fuera": info.get("fuera", []), "avisos": info.get("avisos", [])},
                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    q, fps = QUALITY.get(quality, QUALITY["hd"])
    out = workdir / "media" / "hyperframes" / "silent.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [node, str(CLI), "render", str(proj), "-o", str(out), "-q", q, "--fps", str(fps), "--quiet"]
    p = subprocess.run(cmd, cwd=HF, capture_output=True, text=True, env=_env())
    log = (p.stdout or "") + (p.stderr or "")
    avisos = "\n".join(info.get("avisos", []))
    if avisos:
        log = "Avisos de la escena:\n" + avisos + "\n" + log
    if p.returncode != 0 or not out.exists():
        return False, log[-6000:], None
    return True, log[-2000:], out
