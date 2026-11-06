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
    main_v2()


# ====================================================================== estilos variados (v2)
def saw(f, dur, vel=0.2, cutoff=2500, a=0.3, r=0.6):
    n = int(SR * (dur + r))
    t = np.arange(n) / SR
    x = sum(((f * d * t) % 1) * 2 - 1 for d in (0.996, 1.0, 1.004)) / 3      # 3 voces desafinadas
    return lowpass(x, cutoff) * env(n, a, 1.0, 0.8, r, dur) * vel


def marimba(f, vel=0.4):
    n = int(SR * 0.9)
    t = np.arange(n) / SR
    x = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t / 0.05)
         + 0.1 * np.sin(2 * np.pi * f * 10 * t) * np.exp(-t / 0.015))
    return x * np.exp(-t / 0.25) * vel


def square8(f, dur, vel=0.18, duty=0.5):
    n = int(SR * dur)
    t = np.arange(n) / SR
    ph = (f * t) % 1
    x = np.where(ph < duty, 1.0, -1.0)
    return x * env(n, 0.002, 0.08, 0.7, 0.01, dur) * vel


def noise8(rng, dur, vel=0.12, decay=0.03):
    n = int(SR * dur)
    t = np.arange(n) / SR
    # ruido "8 bits": muestras repetidas
    x = np.repeat(rng.uniform(-1, 1, n // 8 + 1), 8)[:n]
    return x * np.exp(-t / decay) * vel


def pad(f, dur, vel=0.12):
    n = int(SR * (dur + 1.5))
    t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * k * t + k) / k for k in (1, 2, 3)) * (1 + 0.2 * np.sin(2 * np.pi * 0.2 * t))
    return lowpass(x, 1800) * env(n, 1.2, 2.0, 0.85, 1.5, dur) * vel


def _chords(prog, octave=48):
    return [[octave + NOTE[r] + i for i in QUAL[q]] for r, q in prog]


def style_chiptune(seed=11, bpm=118, bars=72):
    """8 bits saltarín: pulso cuadrado, arpegios rápidos, batería de ruido, sin filtro lofi."""
    rng = np.random.default_rng(seed)
    beat, prog = 60 / bpm, _chords([("C", "maj7"), ("E", "m7"), ("F", "maj7"), ("G", "7")], 48)
    bar = beat * 4
    n = int(SR * (bars * bar + 1))
    out = np.zeros(n)
    mel_scale = [0, 2, 4, 7, 9, 12, 14, 16]
    motif = rng.integers(0, len(mel_scale), 16)
    for b in range(bars):
        t0, ch = b * bar, prog[b % 4]
        for i in range(16):                                    # arpegio en semicorcheas
            m = ch[i % 4] + 12 + (12 if (i // 4) % 2 and b % 8 >= 4 else 0)
            place(out, square8(hz(m), beat / 4 * 0.9, 0.05, 0.125), t0 + i * beat / 4)
        for i in range(8):                                     # bajo en corcheas (octavas)
            place(out, square8(hz(ch[0] - 12 + (12 if i % 2 else 0)), beat / 2 * 0.8, 0.09, 0.5), t0 + i * beat / 2)
        if b >= 4:
            for i in range(4):
                place(out, noise8(rng, 0.08, 0.16 if i % 2 else 0.22, 0.02 if i % 2 else 0.05), t0 + i * beat)
            for i in range(8):
                place(out, noise8(rng, 0.03, 0.05, 0.008), t0 + i * beat / 2 + beat / 4)
        if (b // 8) % 2 == 1:                                  # melodía en secciones B
            for i in range(8):
                if rng.random() < 0.8:
                    m = 72 + mel_scale[(motif[i + 8 * (b % 2)] + b) % len(mel_scale)]
                    place(out, square8(hz(m), beat / 2 * 0.85, 0.07, 0.25), t0 + i * beat / 2)
    return out


def style_synthwave(seed=12, bpm=100, bars=64):
    """Synthwave suave: colchones de sierra, bajo en octavas, bombo a negras, caja con eco."""
    rng = np.random.default_rng(seed)
    beat, prog = 60 / bpm, _chords([("A", "m7"), ("F", "maj7"), ("D", "m7"), ("E", "7")], 48)
    bar = beat * 4
    n = int(SR * (bars * bar + 2))
    pads, bass, drums, lead = (np.zeros(n) for _ in range(4))
    for b in range(bars):
        t0, ch = b * bar, prog[(b // 2) % 4]
        if b % 2 == 0:
            for m in ch:
                place(pads, saw(hz(m + 12), bar * 2, 0.05, 1600, 0.6, 1.0), t0)
        if b >= 2:
            for i in range(8):
                place(bass, saw(hz(ch[0] - 12 + (12 if i % 2 else 0)), beat / 2 * 0.7, 0.12, 700, 0.005, 0.05), t0 + i * beat / 2)
        if b >= 4:
            for i in range(4):
                place(drums, kick(0.55), t0 + i * beat)
            for i in (1, 3):
                sn = snare(rng, 0.2)
                place(drums, sn, t0 + i * beat)
                place(drums, sn * 0.35, t0 + i * beat + beat * 0.75)   # eco
        if 16 <= b % 32 < 30:
            for i, step in enumerate([0, 2, 3, 2, 0, -2, 0, None]):
                if step is not None:
                    place(lead, saw(hz(ch[0] + 24 + step), beat * 0.45, 0.045, 3000, 0.02, 0.2), t0 + i * beat / 2)
    return pads + bass + drums * 0.8 + lead


def style_marimba(seed=13, bpm=96, bars=64):
    """Marimba curiosa: juguetona, mayor, tipo video explicativo; shaker y bajo pizzicato."""
    rng = np.random.default_rng(seed)
    beat, prog = 60 / bpm, _chords([("F", "maj7"), ("G", "6"), ("E", "m7"), ("A", "m7")], 60)
    bar = beat * 4
    n = int(SR * (bars * bar + 1))
    out = np.zeros(n)
    pattern = [0, 2, 1, 3, 2, 1, 3, 0]
    for b in range(bars):
        t0, ch = b * bar, prog[b % 4]
        for i, k in enumerate(pattern):
            if (b >= 2 or i % 2 == 0) and rng.random() < 0.92:
                tt = t0 + i * beat / 2 + (0.06 * beat if i % 2 else 0)
                place(out, marimba(hz(ch[k] + (12 if b % 8 >= 6 and i > 4 else 0)), 0.32), tt)
        if b >= 4:
            for i in (0, 1.5, 2, 3):
                place(out, marimba(hz(ch[0] - 24), 0.45) * np.exp(-np.arange(int(SR * 0.9)) / SR / 0.1)[:int(SR * 0.9)],
                      t0 + i * beat)
            for i in range(8):
                place(out, hat(rng, 0.05 if i % 2 else 0.035), t0 + i * beat / 2)
            place(out, kick(0.35), t0)
        if (b // 8) % 2 == 1:
            for i in range(4):
                if rng.random() < 0.6:
                    place(out, bell(hz(ch[rng.integers(4)] + 24), beat * 0.3, 0.05), t0 + i * beat + beat / 2)
    return out


def style_espacial(seed=14, bpm=70, bars=44):
    """Ambiente espacial: colchones lentos, campanitas aleatorias, pulso grave, sin batería."""
    rng = np.random.default_rng(seed)
    beat, prog = 60 / bpm, _chords([("D", "maj9"), ("B", "m9"), ("G", "maj7"), ("A", "6")], 48)
    bar = beat * 4
    n = int(SR * (bars * bar + 3))
    out = np.zeros(n)
    for b in range(0, bars, 2):
        t0, ch = b * bar, prog[(b // 2) % 4]
        for m in ch:
            place(out, pad(hz(m + 12), bar * 2, 0.06), t0)
        place(out, pad(hz(ch[0] - 12), bar * 2, 0.08), t0)
    for _ in range(int(bars * 2.2)):
        t = rng.uniform(2, bars * bar - 1)
        ch = prog[int(t // (bar * 2)) % 4]
        place(out, bell(hz(ch[rng.integers(len(ch))] + 24), 0.5, rng.uniform(0.02, 0.05)), t)
    for b in range(4, bars):
        place(out, kick(0.18) * np.hanning(int(SR * 0.3)), b * bar)
    return out


STYLES_V2 = [
    ("factos-chiptune-saltarin.wav", "Chiptune saltarín", 118, style_chiptune),
    ("factos-synthwave-suave.wav", "Synthwave suave", 100, style_synthwave),
    ("factos-marimba-curiosa.wav", "Marimba curiosa", 96, style_marimba),
    ("factos-ambiente-espacial.wav", "Ambiente espacial", 70, style_espacial),
]


def main_v2(only=None, enabled=False):
    from explapix import music  # noqa: PLC0415
    lib = music.library()
    for fname, title, bpm, fn in STYLES_V2:
        if only and fname not in only:
            continue
        mono = fn()
        d = int(0.011 * SR)
        st = np.stack([mono, np.concatenate([np.zeros(d), mono[:-d]]) * 0.9 + mono * 0.1], 1)
        st /= np.max(np.abs(st)) or 1
        p = OUT / fname
        write_wav(p, st * 0.85)
        mp3 = p.with_suffix(".mp3")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(p), "-af",
                        "areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                        "loudnorm=I=-16:TP=-1.5", "-b:a", "192k", str(mp3)], check=True)
        p.unlink()
        lib[mp3.name] = {"title": title, "source": "Generada por código (explapix/musicgen.py, estilos v2)",
                         "license": "Propia (síntesis por código). Uso comercial libre.",
                         "enabled": enabled, "commercial": True, "bpm": bpm}
        print(mp3.relative_to(ROOT), bpm, "BPM")
    music.save(lib)


def style_funk(seed=15, bpm=104, bars=64):
    """Funk de laboratorio: bajo slap sintético, clavinet con wah, groove de semicorcheas, dórico."""
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    bar = beat * 4
    n = int(SR * (bars * bar + 1))
    out = np.zeros(n)
    root = 50  # D dórico: Dm7 - G7
    prog = [[root, root + 3, root + 7, root + 10], [root + 5, root + 9, root + 12, root + 15]]
    bass_pat = [(0, 0, 0.9), (0.75, 0, 0.5), (1.5, 12, 0.8), (2, 10, 0.6), (2.5, 7, 0.7), (3.25, 5, 0.6), (3.5, 3, 0.5)]
    for b in range(bars):
        t0, ch = b * bar, prog[(b // 2) % 2]
        for pos, iv, v in bass_pat:                       # slap: pulso con ataque brillante
            f = hz(ch[0] - 12 + iv)
            nn = int(SR * beat * 0.35)
            t = np.arange(nn) / SR
            x = (np.sign(np.sin(2 * np.pi * f * t)) * 0.4 + np.sin(2 * np.pi * f * t)) * np.exp(-t / 0.12)
            x[:int(SR * 0.004)] += rng.uniform(-1, 1, int(SR * 0.004)) * 0.6
            place(out, lowpass(x, 2200) * 0.32 * v, t0 + pos * beat)
        for i in range(16):                               # clavinet en contratiempos
            if i % 4 in (1, 3) or (i % 8 == 6 and rng.random() < 0.7):
                for m in ch[1:]:
                    nn = int(SR * 0.12)
                    t = np.arange(nn) / SR
                    wah = 900 + 1500 * (0.5 + 0.5 * np.sin(2 * np.pi * (b * 16 + i) / 32))
                    x = (((hz(m + 12) * t) % 1) * 2 - 1) * np.exp(-t / 0.05)
                    place(out, lowpass(x, wah) * 0.05, t0 + i * beat / 4)
        if b >= 2:
            place(out, kick(0.6), t0)
            place(out, kick(0.45), t0 + 2.75 * beat)
            for i in (1, 3):
                place(out, snare(rng, 0.24), t0 + i * beat)
            for i in range(16):
                place(out, hat(rng, 0.05 if i % 2 else 0.03), t0 + i * beat / 4)
        if (b // 8) % 2 == 1 and b % 2 == 0:              # vientos sintéticos de respuesta
            for k, iv in enumerate([10, 12, 15, 12]):
                place(out, saw(hz(ch[0] + 12 + iv), beat * 0.4, 0.04, 2500, 0.01, 0.1), t0 + (2 + k * 0.5) * beat)
    return out


STYLES_V2.append(("factos-funk-laboratorio.wav", "Funk de laboratorio", 104, style_funk))
