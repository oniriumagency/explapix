"""Voz en off local. Por defecto Piper (gratis, CPU, voces en español).

Motores:
  piper   -> voces neuronales offline (recomendado). Modelo .onnx en EXPLAPIX_PIPER_MODEL
  espeak  -> respaldo robótico, solo para pruebas
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True).stdout
    return float(json.loads(out)["format"]["duration"])


def synth(text: str, out_wav: Path, engine: str | None = None) -> float:
    engine = engine or os.environ.get("EXPLAPIX_TTS", "piper")
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if engine == "piper":
        model = os.environ.get("EXPLAPIX_PIPER_MODEL", "voices/es_MX-claude-high.onnx")
        speed = os.environ.get("EXPLAPIX_PIPER_LENGTH", "0.95")  # <1 = más rápido
        cmd = [shutil.which("piper") or "piper", "-m", model, "-f", str(out_wav),
               "--length-scale", speed, "--sentence-silence", "0.15"]
        subprocess.run(cmd, input=text, text=True, check=True, capture_output=True)
    elif engine == "espeak":
        voice = os.environ.get("EXPLAPIX_ESPEAK_VOICE", "es-419")
        subprocess.run(["espeak-ng", "-v", voice, "-s", "165", "-w", str(out_wav), text],
                       check=True, capture_output=True)
    else:
        raise ValueError(f"Motor TTS desconocido: {engine}")
    return _duration(out_wav)


def narrate(segments: list[str], workdir: Path, pad: float = 0.35) -> dict:
    """Genera un wav por segmento + narration.wav concatenado + timing.json."""
    workdir.mkdir(parents=True, exist_ok=True)
    timing, parts = [], []
    for i, text in enumerate(segments):
        wav = workdir / f"seg_{i:02d}.wav"
        dur = synth(text, wav)
        # pequeño silencio al final de cada segmento para respirar
        padded = workdir / f"seg_{i:02d}_p.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-af",
                        f"apad=pad_dur={pad}", "-ar", "44100", "-ac", "1", str(padded)], check=True)
        timing.append({"text": text, "duration": round(dur + pad, 3)})
        parts.append(padded)
    lst = workdir / "concat.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(workdir / "narration.wav")], check=True)
    data = {"segments": timing, "total": round(sum(t["duration"] for t in timing), 3)}
    (workdir / "timing.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return data
