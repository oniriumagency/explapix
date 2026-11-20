#!/usr/bin/env python3
"""Sube a YouTube un video ya generado (lo usa el panel tras la confirmación).

  python upload.py out/<carpeta> --privacy private|unlisted|public
Lee título/descripción/tags de meta.json (editables desde el panel) y guarda youtube_id.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from explapix import youtube


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    a = ap.parse_args()
    meta_f = a.folder / "meta.json"
    meta = json.loads(meta_f.read_text(encoding="utf-8"))
    if meta.get("youtube_id"):
        raise SystemExit(f"Ya estaba subido: {meta['youtube_id']}")
    print("[1/1] Subida", flush=True)
    largo = meta.get("formato") == "largo"
    vid = youtube.upload(a.folder / "final.mp4", meta["title"], meta["description"],
                         meta.get("tags", []), a.privacy, short=not largo)
    meta.update(youtube_id=vid, privacy=a.privacy,
                uploaded=datetime.now().isoformat(timespec="seconds"))
    youtube.save_json(meta_f, meta)
    url = f"https://youtu.be/{vid}" if largo else f"https://youtube.com/shorts/{vid}"
    print(f"Subido: {url} ({a.privacy})", flush=True)
    if largo:
        print("Ahora enlaza los shorts: python scripts/corregir_y_enlazar.py --aplicar  (y --youtube con aprobación)",
              flush=True)


if __name__ == "__main__":
    main()
