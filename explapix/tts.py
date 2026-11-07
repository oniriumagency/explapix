"""Voz en off local (gratis, en el servidor).

Motores (EXPLAPIX_TTS):
  chatterbox -> Chatterbox Multilingual (MIT, GPU). El más natural y expresivo; puede clonar
                el timbre de una referencia (EXPLAPIX_VOICE_REF). Venv propio: .venv-tts
  kokoro     -> Kokoro-82M (Apache-2.0). Rápido, voces em_alex / ef_dora / em_santa. Venv: .venv-kokoro
  piper      -> Piper (CPU). Muy rápido pero más robótico. Modelo .onnx en EXPLAPIX_PIPER_MODEL
  espeak     -> respaldo robótico, solo para pruebas
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKER = Path(__file__).resolve().parent / "tts_worker.py"
VENVS = {"chatterbox": os.environ.get("EXPLAPIX_CHATTERBOX_PYTHON", str(ROOT / ".venv-tts/bin/python")),
         "kokoro": os.environ.get("EXPLAPIX_KOKORO_PYTHON", str(ROOT / ".venv-kokoro/bin/python"))}
DEFAULT_ENGINE = "chatterbox"


def engine_name() -> str:
    from explapix import config
    return config.env_or("EXPLAPIX_TTS", "voz.motor", DEFAULT_ENGINE)


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True).stdout
    return float(json.loads(out)["format"]["duration"])


def _ref_default() -> str:
    """Referencia de timbre para Chatterbox: EXPLAPIX_VOICE_REF o voices/ref.wav si existe."""
    ref = os.environ.get("EXPLAPIX_VOICE_REF")
    if ref:
        return str((ROOT / ref) if not os.path.isabs(ref) else ref)
    cand = ROOT / "voices" / "ref.wav"
    return str(cand) if cand.exists() else ""


def synth_many(texts: list[str], outs: list[Path], engine: str | None = None) -> None:
    """Sintetiza varios textos de una vez (el modelo se carga una sola vez)."""
    engine = engine or engine_name()
    for o in outs:
        o.parent.mkdir(parents=True, exist_ok=True)
    if engine in VENVS:
        jobs = [{"text": t, "out": str(o.resolve())} for t, o in zip(texts, outs)]
        jf = outs[0].parent / f"jobs_{engine}.json"
        jf.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        from explapix import config
        env = dict(os.environ)
        env["EXPLAPIX_CB_EXAGGERATION"] = config.env_or("EXPLAPIX_CB_EXAGGERATION", "voz.emocion", "0.6")
        env["EXPLAPIX_CB_CFG"] = config.env_or("EXPLAPIX_CB_CFG", "voz.ritmo", "0.4")
        env["EXPLAPIX_KOKORO_VOICE"] = config.env_or("EXPLAPIX_KOKORO_VOICE", "voz.kokoro_voz", "em_alex")
        if engine == "chatterbox":
            env["EXPLAPIX_VOICE_REF"] = _ref_default()
        p = subprocess.run([VENVS[engine], str(WORKER), engine, str(jf)], env=env,
                           capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"TTS {engine} falló:\n{p.stderr[-3000:]}")
        return
    for t, o in zip(texts, outs):
        if engine == "piper":
            model = os.environ.get("EXPLAPIX_PIPER_MODEL", "voices/es_MX-claude-high.onnx")
            speed = os.environ.get("EXPLAPIX_PIPER_LENGTH", "0.95")  # <1 = más rápido
            exe = shutil.which("piper") or str(Path(sys.executable).parent / "piper")
            cmd = [exe, "-m", model, "-f", str(o),
                   "--length-scale", speed, "--sentence-silence", "0.15"]
            subprocess.run(cmd, input=t, text=True, check=True, capture_output=True)
        elif engine == "espeak":
            voice = os.environ.get("EXPLAPIX_ESPEAK_VOICE", "es-419")
            subprocess.run(["espeak-ng", "-v", voice, "-s", "165", "-w", str(o), t],
                           check=True, capture_output=True)
        else:
            raise ValueError(f"Motor TTS desconocido: {engine}")


def synth(text: str, out_wav: Path, engine: str | None = None) -> float:
    synth_many([text], [out_wav], engine)
    return _duration(out_wav)


# recorta silencios del principio/final (los modelos neuronales a veces dejan colas)
_TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03,areverse,"
         "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse")
SR_OUT = 44100


def _load_trimmed(path: Path) -> "np.ndarray":
    import numpy as np  # noqa: PLC0415
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-af", _TRIM, "-ac", "1", "-ar",
                          str(SR_OUT), "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768


def _write_wav(path: Path, x) -> None:
    import wave  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR_OUT)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def narrate(segments: list[str], workdir: Path, pad: float | None = None, by_phrase: bool | None = None) -> dict:
    """Voz por segmento: normaliza el texto, sintetiza frase por frase, recorta y mete pausas según
    la puntuación (coma ~0,18 s, punto/;/: ~0,35 s, ¿?/¡! ~0,45 s, fin de segmento ~0,5 s).
    Devuelve timing.json con la duración REAL de cada segmento (la animación se sincroniza con eso)."""
    import numpy as np  # noqa: PLC0415
    from explapix import config, textnorm  # noqa: PLC0415
    workdir.mkdir(parents=True, exist_ok=True)
    by_phrase = config.get("voz.por_frases", True) if by_phrase is None else by_phrase
    plan: list[list[tuple[str, float]]] = []
    for text in segments:
        if by_phrase:
            plan.append(textnorm.chunks(text))
        else:
            plan.append([(textnorm.normalize(text), textnorm.END_PAUSE if pad is None else pad)])
    texts, outs = [], []
    for i, ch in enumerate(plan):
        for k, (t, _) in enumerate(ch):
            texts.append(t)
            outs.append(workdir / f"seg_{i:02d}_{k:02d}.wav")
    synth_many(texts, outs)
    timing, full = [], []
    idx = 0
    for i, (text, ch) in enumerate(zip(segments, plan)):
        parts = []
        for _t, pause in ch:
            parts.append(_load_trimmed(outs[idx]))
            parts.append(np.zeros(int(SR_OUT * pause), dtype=np.float32))
            idx += 1
        seg = np.concatenate(parts) if parts else np.zeros(int(SR_OUT * 0.5), dtype=np.float32)
        _write_wav(workdir / f"seg_{i:02d}_p.wav", seg)
        timing.append({"text": text, "spoken": " ".join(t for t, _ in ch),
                       "duration": round(len(seg) / SR_OUT, 3)})
        full.append(seg)
    _write_wav(workdir / "narration.wav", np.concatenate(full))
    data = {"engine": engine_name(), "segments": timing,
            "total": round(sum(t["duration"] for t in timing), 3)}
    (workdir / "timing.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return data


REF_TEXT = ("Hola, bienvenidos a Explapix. Hoy vamos a descubrir cómo funcionan las cosas que usamos "
            "todos los días. Es más sorprendente de lo que parece, así que quédate conmigo hasta el final.")

if __name__ == "__main__":
    # python -m explapix.tts ref  -> crea voices/ref.wav (timbre de referencia con Kokoro em_alex)
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["ref", "say"])
    ap.add_argument("text", nargs="?", default=REF_TEXT)
    ap.add_argument("-o", "--out", type=Path, default=ROOT / "voices" / "ref.wav")
    ap.add_argument("-e", "--engine", default=None)
    a = ap.parse_args()
    eng = "kokoro" if a.cmd == "ref" and not a.engine else a.engine
    print(f"{a.out}: {synth(a.text, a.out, eng):.1f} s")
