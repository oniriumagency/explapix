#!/usr/bin/env python3
"""Factos Didácticos (código interno: explapix): tema -> guion -> voz -> animación -> video final (+ subida opcional).

Ejemplos:
  python make_video.py --topic "Cómo funciona un microondas"
  python make_video.py --storyboard examples/refrigerador/storyboard.json \
                       --scene examples/refrigerador/scene.py          # sin IA, sin costo
  python make_video.py --topics topics.txt --upload --privacy private  # lote
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

from explapix import render, tts

ROOT = Path(__file__).resolve().parent


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]


def build(topic: str | None, storyboard: Path | None, scene: Path | None, quality: str,
          retries: int, music: Path | None, upload: bool, privacy: str, notes: str = "",
          expand: bool = False, base_scene: Path | None = None) -> Path:
    if storyboard:
        sb = json.loads(storyboard.read_text(encoding="utf-8"))
        if expand:
            from explapix import llm
            print(f"[1/4] Guion ampliado: {sb.get('topic')}", flush=True)
            sb = llm.expand_storyboard(sb, notes)
            print(f"   duración objetivo: {sb.get('duracion_objetivo_s')} s · "
                  f"{len(sb['segments'])} segmentos · {sb.get('justificacion_duracion', '')}", flush=True)
    else:
        from explapix import llm
        print(f"[1/4] Guion: {topic}", flush=True)
        sb = llm.storyboard(topic, f"Indicaciones del editor: {notes}" if notes else "")

    work = ROOT / "out" / f"{datetime.now():%Y%m%d-%H%M}-{slug(sb['topic'])}"
    work.mkdir(parents=True, exist_ok=True)
    (work / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[2/4] Voz", flush=True)
    timing = tts.narrate([s["narration"] for s in sb["segments"]], work / "audio")
    shutil.copy(work / "audio" / "timing.json", work / "timing.json")

    print("[3/4] Animación", flush=True)
    scene_file = work / "scene.py"
    if scene:
        shutil.copy(scene, scene_file)
        ok, log, silent = render.render_scene(scene_file, work, quality)
    else:
        from explapix import llm
        code, err = None, None
        for attempt in range(retries + 1):
            code = llm.scene_code(sb, timing, previous=code, error=err,
                                  base_scene=base_scene.read_text(encoding="utf-8") if base_scene else None)
            scene_file.write_text(code, encoding="utf-8")
            ok, log, silent = render.render_scene(scene_file, work, quality)
            if ok:
                break
            err = log
            print(f"   intento {attempt + 1} falló, corrigiendo…", flush=True)
    if not ok:
        (work / "render_error.log").write_text(log, encoding="utf-8")
        raise SystemExit(f"Render falló, ver {work / 'render_error.log'}")

    print("[4/4] Mezcla final", flush=True)
    from explapix import music as music_lib, sfx  # noqa: PLC0415
    music = music or music_lib.pick()
    events = sfx.load_events(work / "sfx_events.json")
    sfx_wav = None
    if events:
        sfx_wav = work / "audio" / "sfx.wav"
        n_sfx = sfx.build_track(events, render._dur(silent), sfx_wav)
        print(f"   efectos: {n_sfx} · música: {music.name if music else 'ninguna'}", flush=True)
    final = render.mux(silent, work / "audio" / "narration.wav", work / "final.mp4", music, sfx_wav)
    from explapix import config as _cfg  # noqa: PLC0415
    real = render._dur(final)
    tope = float(_cfg.get("formato.duracion_maxima_s", 175))
    if real >= 180 or real > tope + 3:
        bad = final.with_name("final_demasiado_largo.mp4")
        final.replace(bad)
        raise SystemExit(f"El video dura {real:.1f} s: pasa el límite de 3 min de Shorts/Reels "
                         f"(tope {tope:.0f} s). Quedó en {bad}; acorta el guion y regenera.")
    meta = {"title": sb["title"], "description": sb["description"], "tags": sb["tags"],
            "topic": sb.get("topic", ""), "file": str(final), "engine": timing.get("engine"),
            "duration": timing.get("total"), "quality": quality,
            "created": datetime.now().isoformat(timespec="seconds"),
            "music": music.name if music else None, "sfx": bool(events),
            "target_s": sb.get("duracion_objetivo_s"), "duration_reason": sb.get("justificacion_duracion")}
    if notes:
        meta["notes"] = notes
    if upload:
        from explapix import youtube
        meta["youtube_id"] = youtube.upload(final, sb["title"], sb["description"], sb["tags"], privacy)
        meta["privacy"] = privacy
        print(f"   subido: https://youtube.com/shorts/{meta['youtube_id']} ({privacy})")
    (work / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Listo: {final}", flush=True)
    return final


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--topic")
    g.add_argument("--topics", type=Path, help="archivo con un tema por línea")
    g.add_argument("--storyboard", type=Path)
    ap.add_argument("--scene", type=Path, help="usar esta escena en vez de generarla")
    ap.add_argument("--expand", action="store_true", help="ampliar el guion a la estructura de 61-90 s")
    ap.add_argument("--base-scene", type=Path, help="escena corta a reutilizar al extender")
    ap.add_argument("--notes", default="", help="indicaciones extra para el guion (p. ej. nota de revisión)")
    from explapix import config
    ap.add_argument("--quality", choices=list(render.QUALITY), default=config.get("formato.calidad", "hd"))
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--music", type=Path, help="música de fondo libre de derechos (mp3/wav)")
    ap.add_argument("--upload", action="store_true", help="subir a YouTube al terminar")
    ap.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    a = ap.parse_args()

    topics = [a.topic] if a.topic else ([None] if a.storyboard else
              [l.strip() for l in a.topics.read_text(encoding="utf-8").splitlines() if l.strip()])
    for t in topics:
        build(t, a.storyboard, a.scene, a.quality, a.retries, a.music, a.upload, a.privacy, a.notes,
              a.expand, a.base_scene)


if __name__ == "__main__":
    main()
