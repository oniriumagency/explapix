"""Worker de voz para motores pesados (Kokoro, Chatterbox), que viven en su propio venv
(dependen de versiones de PyTorch distintas a las de Manim).

Uso (lo llama explapix/tts.py; carga el modelo una sola vez por video):
    <venv>/bin/python explapix/tts_worker.py <motor> jobs.json
jobs.json = [{"text": "...", "out": "seg_00.wav"}, ...]

Variables:
  EXPLAPIX_KOKORO_VOICE   em_alex | ef_dora | em_santa       (default em_alex)
  EXPLAPIX_KOKORO_SPEED   1.0
  EXPLAPIX_VOICE_REF      wav de referencia para clonar timbre en Chatterbox (5-20 s, una voz
                          de la que tengas derechos: la tuya, o una muestra Kokoro/Apache-2.0)
  EXPLAPIX_CB_EXAGGERATION  0.25-1.0, emoción/énfasis (default 0.6)
  EXPLAPIX_CB_CFG           0.2-0.7, menor = más pausado y natural (default 0.4)
"""
from __future__ import annotations

import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")


def kokoro(jobs):
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    voice = os.environ.get("EXPLAPIX_KOKORO_VOICE", "em_alex")
    speed = float(os.environ.get("EXPLAPIX_KOKORO_SPEED", "1.0"))
    pipe = KPipeline(lang_code="e", repo_id="hexgrad/Kokoro-82M")
    for j in jobs:
        audio = np.concatenate([r.audio.numpy() for r in pipe(j["text"], voice=voice, speed=speed)])
        sf.write(j["out"], audio, 24000)


def chatterbox(jobs):
    import torch
    import torchaudio as ta
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = ChatterboxMultilingualTTS.from_pretrained(device=dev)
    ref = os.environ.get("EXPLAPIX_VOICE_REF") or None
    if ref and not os.path.exists(ref):
        print(f"aviso: no existe {ref}, uso la voz por defecto", file=sys.stderr)
        ref = None
    ex = float(os.environ.get("EXPLAPIX_CB_EXAGGERATION", "0.6"))
    cfg = float(os.environ.get("EXPLAPIX_CB_CFG", "0.4"))
    if ref:
        model.prepare_conditionals(ref, exaggeration=ex)
    for j in jobs:
        wav = model.generate(j["text"], language_id="es", exaggeration=ex, cfg_weight=cfg)
        ta.save(j["out"], wav, model.sr)


if __name__ == "__main__":
    engine, jobs_file = sys.argv[1], sys.argv[2]
    with open(jobs_file, encoding="utf-8") as f:
        jobs = json.load(f)
    {"kokoro": kokoro, "chatterbox": chatterbox}[engine](jobs)
