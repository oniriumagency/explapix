#!/usr/bin/env python3
"""Vuelve a mezclar el audio de videos ya generados (sin re-renderizar la animación ni gastar tokens).

  python remix.py out/<carpeta> [--music archivo.mp3]   # uno
  python remix.py --all                                  # todos los de out/
Usa la animación muda (media/.../silent.mp4), la voz (audio/narration.wav), los eventos de
efectos si existen (sfx_events.json) y una pista de la rotación de música.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from explapix import music as music_lib, render, sfx

ROOT = Path(__file__).resolve().parent


def remix(folder: Path, music: Path | None = None) -> str:
    silent = next(folder.glob("media/videos/*/*/silent.mp4"), None)
    voice = folder / "audio" / "narration.wav"
    if not silent or not voice.exists():
        return f"{folder.name}: falta silent.mp4 o narration.wav, omitido"
    music = music or music_lib.pick()
    events = sfx.load_events(folder / "sfx_events.json")
    sfx_wav = None
    if events:
        sfx_wav = folder / "audio" / "sfx.wav"
        sfx.build_track(events, render._dur(silent), sfx_wav)
    render.mux(silent, voice, folder / "final.mp4", music, sfx_wav)
    mf = folder / "meta.json"
    if mf.exists():
        meta = json.loads(mf.read_text(encoding="utf-8"))
        meta.update(music=music.name if music else None, sfx=bool(events))
        mf.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    thumb = folder / "thumb.jpg"
    thumb.unlink(missing_ok=True)
    return f"{folder.name}: música={music.name if music else 'ninguna'} efectos={len(events)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", nargs="?", type=Path)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--music", type=Path)
    a = ap.parse_args()
    folders = sorted(d for d in (ROOT / "out").glob("2*") if d.is_dir()) if a.all else [a.folder]
    print("[1/1] Remezcla", flush=True)
    for f in folders:
        print("  ", remix(f, a.music), flush=True)


if __name__ == "__main__":
    main()
