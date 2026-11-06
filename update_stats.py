#!/usr/bin/env python3
"""Actualiza las métricas de YouTube e Instagram de todos los videos publicados (lo usa el panel)."""
from pathlib import Path

from explapix import analytics

if __name__ == "__main__":
    print("[1/1] Métricas", flush=True)
    n = analytics.update_all(Path(__file__).resolve().parent / "out")
    print(f"Métricas actualizadas en {n} video(s)", flush=True)
