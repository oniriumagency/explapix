"""Lee config/estilo.yaml (el estándar del canal). Las variables de entorno tienen prioridad."""
from __future__ import annotations

import functools
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FILE = Path(os.environ.get("EXPLAPIX_STYLE", ROOT / "config" / "estilo.yaml"))


@functools.lru_cache(maxsize=1)
def style() -> dict:
    try:
        return yaml.safe_load(FILE.read_text(encoding="utf-8")) or {}
    except OSError:
        return {}


def get(path: str, default=None):
    """get("voz.motor", "chatterbox")"""
    cur = style()
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def env_or(var: str, path: str, default=None) -> str:
    v = os.environ.get(var)
    if v not in (None, ""):
        return v
    v = get(path, default)
    return "" if v is None else str(v)
