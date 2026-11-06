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
          retries: int, music: Path | None, upload: bool, privacy: str, notes: str = "") -> Path:
    if storyboard:
        sb = json.loads(storyboard.read_text(encoding="utf-8"))
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
            code = llm.scene_code(sb, timing, previous=code, error=err)
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
    final = render.mux(silent, work / "audio" / "narration.wav", work / "final.mp4", music)
    meta = {"title": sb["title"], "description": sb["description"], "tags": sb["tags"],
            "topic": sb.get("topic", ""), "file": str(final), "engine": timing.get("engine"),
            "duration": timing.get("total"), "quality": quality,
            "created": datetime.now().isoformat(timespec="seconds")}
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
    ap.add_argument("--notes", default="", help="indicaciones extra para el guion (p. ej. nota de revisión)")
    ap.add_argument("--quality", choices=list(render.QUALITY), default="hd")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--music", type=Path, help="música de fondo libre de derechos (mp3/wav)")
    ap.add_argument("--upload", action="store_true", help="subir a YouTube al terminar")
    ap.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    a = ap.parse_args()

    topics = [a.topic] if a.topic else ([None] if a.storyboard else
              [l.strip() for l in a.topics.read_text(encoding="utf-8").splitlines() if l.strip()])
    for t in topics:
        build(t, a.storyboard, a.scene, a.quality, a.retries, a.music, a.upload, a.privacy, a.notes)


if __name__ == "__main__":
    main()
