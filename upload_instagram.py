#!/usr/bin/env python3
"""Publica un video como Reel de Instagram (lo usa el panel tras la confirmación).

  python upload_instagram.py out/<carpeta>
El caption sale de meta.json["ig_caption"] (editable en el panel) o del calendario.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from explapix import instagram, youtube


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    a = ap.parse_args()
    mf = a.folder / "meta.json"
    meta = json.loads(mf.read_text(encoding="utf-8"))
    if meta.get("instagram_id"):
        raise SystemExit(f"Ya estaba en Instagram: {meta.get('instagram_permalink')}")
    caption = meta.get("ig_caption") or f"{meta['title']}\n\n{meta['description']}"
    print("[1/1] Subida a Instagram", flush=True)
    r = instagram.publish_reel(a.folder / "final.mp4", caption)
    meta.update(instagram_id=r["id"], instagram_permalink=r.get("permalink"),
                instagram_uploaded=datetime.now().isoformat(timespec="seconds"))
    youtube.save_json(mf, meta)
    print(f"Publicado en Instagram: {r.get('permalink')}", flush=True)


if __name__ == "__main__":
    main()
