"""Música de fondo propia, generada con código (sin modelos externos): lofi/chiptune retro-arcade.

Todo se sintetiza aquí (osciladores, ruido y envolventes en numpy), así que las pistas son 100 %
nuestras: licencia comercial sin restricciones (pueden monetizarse en YouTube/Instagram).

  python -m explapix.musicgen          # genera las 4 pistas en assets/music/ y las activa
"""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "music"
SR = 44100

NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}
QUAL = {"maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "7": [0, 4, 7, 10], "m9": [0, 3, 7, 10, 14],
        "maj9": [0, 4, 7, 11, 14], "6": [0, 4, 7, 9]}

TRACKS = [
    {"file": "factos-arcade-nocturno.wav", "title": "Arcade nocturno", "bpm": 88, "seed": 1,
     "prog": [("A", "m7"), ("F", "maj7"), ("C", "maj7"), ("G", "7")], "lead": "chip", "swing": 0.12},
    {"file": "factos-laboratorio-lofi.wav", "title": "Laboratorio lofi", "bpm": 82, "seed": 2,
     "prog": [("D", "m9"), ("G", "7"), ("C", "maj9"), ("A", "m7")], "lead": "keys", "swing": 0.18},
    {"file": "factos-pixel-curioso.wav", "title": "Píxel curioso", "bpm": 94, "seed": 3,
     "prog": [("C", "maj7"), ("A", "m7"), ("F", "maj7"), ("G", "6")], "lead": "chip", "swing": 0.08},
    {"file": "factos-orbita-tranquila.wav", "title": "Órbita tranquila", "bpm": 85, "seed": 4,
     "prog": [("E", "m9"), ("C", "maj7"), ("A", "m7"), ("B", "7")], "lead": "bell", "swing": 0.15},
]


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    # filtro de un polo vectorizado por bloques (suficiente para dar calidez lofi)
    from scipy.signal import lfilter  # noqa: PLC0415
    return lfilter([1 - a], [1, -a], x)


def env(n, a=0.01, d=0.3, s=0.6, r=0.2, hold=None):
    t = np.arange(n) / SR
    hold = hold if hold is not None else n / SR
    e = np.where(t < a, t / a, s + (1 - s) * np.exp(-(t - a) / d))
    rel = np.clip((t - hold) / r, 0, 1)
    return e * (1 - rel)


def epiano(f, dur, vel=0.5):
    n = int(SR * (dur + 0.4))
    t = np.arange(n) / SR
    x = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) * np.exp(-t / 0.4)
         + 0.12 * np.sin(6 * np.pi * f * t) * np.exp(-t / 0.2))
    trem = 1 + 0.08 * np.sin(2 * np.pi * 4.5 * t)
    return x * trem * env(n, 0.008, 0.9, 0.35, 0.35, dur) * vel


def pulse(f, dur, vel=0.3, duty=0.25):
    n = int(SR * (dur + 0.05))
    t = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.15, 0, 1)
    ph = (f * vib * t) % 1
    x = np.where(ph < duty, 1.0, -1.0)
    return lowpass(x, 3200) * env(n, 0.004, 0.12, 0.5, 0.05, dur) * vel


def bell(f, dur, vel=0.3):
    n = int(SR * (dur + 0.8))
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * f * t + 1.8 * np.sin(2 * np.pi * f * 3.5 * t) * np.exp(-t / 0.3))
    return x * np.exp(-t / 0.7) * vel


def tri_bass(f, dur, vel=0.5):
    n = int(SR * (dur + 0.05))
    t = np.arange(n) / SR
    ph = (f * t) % 1
    x = 4 * np.abs(ph - 0.5) - 1
    return lowpass(x, 900) * env(n, 0.005, 0.25, 0.7, 0.06, dur) * vel


def kick(vel=0.9):
    n = int(SR * 0.3)
    t = np.arange(n) / SR
    f = 48 + 90 * np.exp(-t / 0.035)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.12) * vel


def snare(rng, vel=0.22):
    n = int(SR * 0.22)
    t = np.arange(n) / SR
    noise = lowpass(rng.standard_normal(n), 5000) - lowpass(rng.standard_normal(n), 900) * 0.3
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)
    return (noise * np.exp(-t / 0.07) * 0.8 + tone * 0.5) * vel


def hat(rng, vel=0.12, open_=False):
    n = int(SR * (0.18 if open_ else 0.05))
    t = np.arange(n) / SR
    x = rng.standard_normal(n)
    x = x - lowpass(x, 6000)
    return x * np.exp(-t / (0.06 if open_ else 0.015)) * vel


def place(buf, snd, t):
    i = int(t * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(snd))
    buf[i:j] += snd[:j - i]


def render(spec: dict, bars: int = 56) -> np.ndarray:
    rng = np.random.default_rng(spec["seed"])
    beat = 60 / spec["bpm"]
    bar = beat * 4
    total = bars * bar
    n = int(SR * (total + 2))
    keys, bass, drums, lead = (np.zeros(n) for _ in range(4))
    prog = spec["prog"]
    sw = spec["swing"]
    # escala menor pentatónica/mayor según el primer acorde para la melodía
    root0 = NOTE[prog[0][0]]
    minor = "m" in prog[0][1]
    scale = [0, 3, 5, 7, 10] if minor else [0, 2, 4, 7, 9]
    motif = rng.choice(len(scale), size=8)
    motif_oct = rng.choice([0, 0, 12], size=8)
    for b in range(bars):
        t0 = b * bar
        sec = (b // 8) % 4                       # secciones de 8 compases
        intro, outro = b < 4, b >= bars - 4
        name, q = prog[b % len(prog)]
        r = 48 + NOTE[name]                      # raíz alrededor de C3
        notes = [r + i for i in QUAL[q]]
        # acordes: piano eléctrico, a veces en dos golpes
        hits = [0.0, 2.5] if sec in (1, 3) else [0.0]
        for h in hits:
            for k, m in enumerate(notes):
                place(keys, epiano(hz(m + 12), bar - h * beat, 0.16), t0 + h * beat + k * 0.012)
        # bajo
        if not intro:
            for pos, off in [(0, 0), (1.5, 7), (2, 0), (3.5, 12 if b % 2 else 7)]:
                place(bass, tri_bass(hz(r - 12 + off), beat * 0.45, 0.42), t0 + pos * beat)
        # batería con swing
        if not intro and not (outro and b == bars - 1):
            for i in range(8):
                tt = t0 + i * beat / 2 + (sw * beat / 2 if i % 2 else 0)
                place(drums, hat(rng, 0.04 if i % 2 else 0.06, open_=(i == 7 and b % 4 == 3)), tt)
            place(drums, kick(), t0)
            place(drums, kick(0.7), t0 + 2.5 * beat if b % 2 else t0 + 2 * beat)
            place(drums, snare(rng), t0 + beat)
            place(drums, snare(rng), t0 + 3 * beat)
        # melodía (secciones B y D), arpegio suave en A/C
        if sec in (1, 3) and not outro:
            for i in range(8):
                if rng.random() < 0.72:
                    deg = scale[(motif[i] + (b % 4)) % len(scale)]
                    m = 72 + root0 + deg + motif_oct[i] - 12
                    tt = t0 + i * beat / 2 + (sw * beat / 2 if i % 2 else 0)
                    snd = (pulse(hz(m), beat * 0.4, 0.07) if spec["lead"] == "chip" else
                           bell(hz(m), beat * 0.4, 0.08) if spec["lead"] == "bell" else
                           epiano(hz(m), beat * 0.45, 0.1))
                    place(lead, snd, tt)
        elif not intro:
            for i, m in enumerate(notes[:4]):
                place(lead, pulse(hz(m + 24), beat * 0.2, 0.025, 0.125), t0 + (2 + i * 0.5) * beat)
    # mezcla lofi: calidez, compresión tipo "pumping", ruido de vinilo, estéreo con retardo
    pump = np.ones(n)
    for b in range(bars):
        for q_ in range(4):
            i = int((b * bar + q_ * beat) * SR)
            k = int(0.18 * SR)
            if i + k < n:
                pump[i:i + k] = np.minimum(pump[i:i + k], 0.6 + 0.4 * np.linspace(0, 1, k))
    music = lowpass(keys * pump * 1.3 + lead + bass * pump, 6000) + lowpass(drums, 9000) * 0.75
    crackle = (rng.random(n) > 0.9993) * rng.uniform(-0.25, 0.25, n)
    music += lowpass(crackle, 3000) * 0.5 + lowpass(rng.standard_normal(n), 1200) * 0.004
    music = music[:int(SR * total)]
    d = int(0.012 * SR)
    left = music
    right = np.concatenate([np.zeros(d), music[:-d]]) * 0.92 + music * 0.08
    st = np.stack([left, right], 1)
    st /= np.max(np.abs(st)) or 1
    return st * 0.85


def write_wav(path: Path, st: np.ndarray):
    data = (np.clip(st, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def main():
    from explapix import music  # noqa: PLC0415
    lib = music.library()
    for spec in TRACKS:
        p = OUT / spec["file"]
        bars = int(round(150 / (240 / spec["bpm"]) / 8) * 8)   # ~2:30, múltiplo de 8 compases
        write_wav(p, render(spec, bars))
        mp3 = p.with_suffix(".mp3")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(p), "-af", "loudnorm=I=-16:TP=-1.5",
                        "-b:a", "192k", str(mp3)], check=True)
        p.unlink()
        lib[mp3.name] = {"title": spec["title"], "source": "Generada por código (explapix/musicgen.py)",
                         "license": "Propia (síntesis por código). Uso comercial libre.",
                         "enabled": True, "commercial": True, "bpm": spec["bpm"]}
        print(mp3.relative_to(ROOT), spec["bpm"], "BPM")
    lib.pop("factos-arcade-nocturno.wav", None)
    music.save({k: v for k, v in lib.items() if (OUT / k).exists()})


if __name__ == "__main__":
    main()
