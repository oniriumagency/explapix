"""Efectos de sonido propios (generados con numpy, libres de derechos) y pista de efectos.

Tipos (2-3 variantes cada uno, en assets/sfx/<tipo>_<n>.wav):
  pop      objetos que aparecen o rebotan (pop_in)
  woosh    movimientos, cámara, salidas (move_along_arc, anticipate_move, cam_to, exit_out)
  blip     texto, etiquetas y datos (pills, títulos, emphasize)
  shimmer  partículas, brillos, cambio de color de fondo, cierre
  thud     golpes suaves (aterrizajes de squash_bounce, jelly)

Generar/actualizar la biblioteca:  python -m explapix.sfx
"""
from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SFX_DIR = ROOT / "assets" / "sfx"
SR = 44100
KINDS = ("pop", "woosh", "blip", "shimmer", "thud")
GAIN = {"pop": 0.75, "woosh": 0.55, "blip": 0.55, "shimmer": 0.45, "thud": 0.8}
MIN_GAP = {"pop": 0.07, "woosh": 0.25, "blip": 0.08, "shimmer": 0.6, "thud": 0.15}


def _t(dur):
    return np.arange(int(SR * dur)) / SR


def _env(n, attack=0.004, decay=0.08):
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-np.maximum(t - attack, 0) / decay)


def _norm(x, peak=0.5):
    m = np.max(np.abs(x)) or 1
    return x / m * peak


def make_pop(v):
    f0, f1, dur = [(820, 360, 0.11), (1000, 420, 0.09), (680, 300, 0.13)][v]
    t = _t(dur)
    f = f1 + (f0 - f1) * np.exp(-t / 0.025)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.002, dur / 3.5)
    x += 0.15 * np.sin(4 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.002, dur / 6)
    return _norm(x)


def make_woosh(v, rng):
    dur, lo, hi = [(0.45, 300, 2400), (0.35, 500, 3200), (0.55, 200, 1800)][v]
    n = int(SR * dur)
    noise = rng.standard_normal(n)
    spec = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    out = np.zeros(n)
    win = 2048
    hop = win // 2
    for start in range(0, n - win, hop):   # barrido de banda: filtrado por bloques (STFT)
        seg = noise[start:start + win] * np.hanning(win)
        S = np.fft.rfft(seg)
        p = start / n
        fc = lo * (hi / lo) ** np.sin(np.pi * p)  # sube y baja
        fr = np.fft.rfftfreq(win, 1 / SR)
        S *= np.exp(-((np.log(fr + 1) - np.log(fc)) ** 2) / 0.35)
        out[start:start + win] += np.fft.irfft(S, win)
    t = np.arange(n) / n
    out *= np.sin(np.pi * t) ** 1.5
    del spec, freqs
    return _norm(out, 0.45)


def make_blip(v):
    notes = [(1320, 1760), (1568, 2093, 2637), (1175,)][v]
    parts = []
    for f in notes:
        t = _t(0.045)
        sq = np.sign(np.sin(2 * np.pi * f * t)) * 0.35 + np.sin(2 * np.pi * f * t) * 0.65
        parts.append(sq * _env(len(t), 0.002, 0.02))
        parts.append(np.zeros(int(SR * 0.012)))
    return _norm(np.concatenate(parts), 0.4)


def make_shimmer(v, rng):
    dur = [0.9, 0.7, 1.1][v]
    n = int(SR * dur)
    x = np.zeros(n)
    base = [2093, 2637, 3136, 3520, 4186]
    for k in range(9):
        f = rng.choice(base) * rng.uniform(0.99, 1.01)
        start = int(rng.uniform(0, 0.45) * n)
        t = np.arange(n - start) / SR
        x[start:] += np.sin(2 * np.pi * f * t) * np.exp(-t / 0.18) * rng.uniform(0.3, 1)
    x *= np.minimum(1, np.arange(n) / (0.01 * SR))
    return _norm(x, 0.35)


def make_thud(v):
    f0, dur = [(120, 0.18), (95, 0.22), (140, 0.15)][v]
    t = _t(dur)
    f = 45 + (f0 - 45) * np.exp(-t / 0.04)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.002, dur / 3)
    click = np.random.default_rng(v).standard_normal(int(SR * 0.006)) * 0.3
    x[:len(click)] += click * np.linspace(1, 0, len(click))
    return _norm(x, 0.6)


def _write(path: Path, x: np.ndarray):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def _read(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32767


def generate(force: bool = False) -> list[Path]:
    rng = np.random.default_rng(42)
    made = []
    makers = {"pop": lambda v: make_pop(v), "woosh": lambda v: make_woosh(v, rng),
              "blip": lambda v: make_blip(v), "shimmer": lambda v: make_shimmer(v, rng),
              "thud": lambda v: make_thud(v)}
    for kind, mk in makers.items():
        for v in range(3):
            p = SFX_DIR / f"{kind}_{v + 1}.wav"
            if force or not p.exists():
                _write(p, mk(v))
                made.append(p)
    return made


def library() -> dict[str, list[np.ndarray]]:
    generate()
    return {k: [_read(p) for p in sorted(SFX_DIR.glob(f"{k}_*.wav"))] for k in KINDS}


def build_track(events: list[dict], duration: float, out_wav: Path, seed: int = 7) -> int:
    """Coloca los efectos en una pista mono del largo del video. Devuelve cuántos se usaron."""
    lib = library()
    rng = np.random.default_rng(seed)
    buf = np.zeros(int(SR * (duration + 1.5)), dtype=np.float32)
    last: dict[str, float] = {}
    used, recent = 0, []
    for ev in sorted(events, key=lambda e: e["t"]):
        k, t = ev.get("kind"), float(ev.get("t", 0))
        if k not in lib or not lib[k] or t < 0 or t > duration:
            continue
        if t - last.get(k, -9) < MIN_GAP[k]:
            continue
        recent = [x for x in recent if t - x < 1.0]
        if len(recent) >= 5:          # no más de 5 efectos por segundo
            continue
        snd = lib[k][rng.integers(len(lib[k]))] * GAIN[k] * float(ev.get("gain", 1.0))
        i = int(t * SR)
        buf[i:i + len(snd)] += snd[:len(buf) - i]
        last[k] = t
        recent.append(t)
        used += 1
    _write(out_wav, buf[:int(SR * duration)])
    return used


def load_events(path: Path) -> list[dict]:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return []


if __name__ == "__main__":
    for p in generate(force=True):
        print(p.relative_to(ROOT))
