#!/usr/bin/env python3
"""Re-renderiza la animación de videos ya generados con el kit actual (zona segura, efectos), usando
su scene.py y su voz existentes: sin tokens y sin volver a sintetizar la voz.

  python rerender.py out/<carpeta> [out/<otra> ...]
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from remix import remix
from explapix import render


def rerender(folder: Path) -> str:
    scene = folder / "scene.py"
    if not scene.exists() or not (folder / "timing.json").exists():
        return f"{folder.name}: falta scene.py o timing.json"
    old_media = folder / "media"
    if old_media.exists():
        shutil.rmtree(old_media)
    ok, log, silent = render.render_scene(scene, folder, "hd")
    if not ok:
        (folder / "render_error.log").write_text(log, encoding="utf-8")
        return f"{folder.name}: falló el render (ver render_error.log)"
    return remix(folder)


if __name__ == "__main__":
    print("[1/1] Re-render", flush=True)
    for f in sys.argv[1:]:
        print("  ", rerender(Path(f)), flush=True)
