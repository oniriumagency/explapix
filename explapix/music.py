"""Rotación de música de fondo (assets/music + library.json).

library.json: {"archivo.mp3": {"title", "source", "license", "enabled", "commercial"}}
Solo entran en la rotación las pistas con enabled=true Y commercial=true (licencia que permite
monetizar). Nunca se repite la misma pista dos veces seguidas.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "assets" / "music"
LIB = DIR / "library.json"
STATE = ROOT / "out" / "_studio" / "music_state.json"
EXTS = (".mp3", ".wav", ".ogg", ".m4a", ".flac")


def library() -> dict:
    try:
        lib = json.loads(LIB.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        lib = {}
    for f in DIR.glob("*"):
        if f.suffix.lower() in EXTS and f.name not in lib:
            lib[f.name] = {"title": f.stem, "source": "", "license": "", "enabled": False,
                           "commercial": False}
    for name in list(lib):
        if not (DIR / name).exists():
            del lib[name]
    return lib


def save(lib: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    LIB.write_text(json.dumps(lib, ensure_ascii=False, indent=2), encoding="utf-8")


def rotation() -> list[str]:
    return sorted(n for n, m in library().items() if m.get("enabled") and m.get("commercial"))


def pick() -> Path | None:
    pool = rotation()
    if not pool:
        return None
    try:
        last = json.loads(STATE.read_text()).get("last")
    except (OSError, ValueError):
        last = None
    choices = [p for p in pool if p != last] or pool
    name = random.choice(choices)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"last": name}))
    return DIR / name
