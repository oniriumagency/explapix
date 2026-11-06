"""Guion (storyboard) y código de animación con Claude.

Costo aproximado por video con claude-opus-5-5 a esfuerzo medio: unos centavos de dólar
(~10k tokens de entrada + ~8k de salida). Cambia EXPLAPIX_MODEL si quieres otro modelo.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import anthropic

MODEL = os.environ.get("EXPLAPIX_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("EXPLAPIX_EFFORT", "medium")
KIT = (Path(__file__).parent / "kit.py").read_text(encoding="utf-8")
EXAMPLE = (Path(__file__).parent.parent / "examples/refrigerador/scene.py").read_text(encoding="utf-8")

client = anthropic.Anthropic()

STORYBOARD_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "segments": {"type": "array", "items": {
            "type": "object",
            "properties": {"narration": {"type": "string"}, "visual": {"type": "string"}},
            "required": ["narration", "visual"], "additionalProperties": False}},
    },
    "required": ["topic", "title", "description", "tags", "segments"],
    "additionalProperties": False,
}

STORYBOARD_SYSTEM = """Eres guionista del canal Explapix: videos verticales cortos (35-55 s) que \
explican cómo funcionan las cosas, en español latino neutro, tono curioso y cercano.
Reglas:
- 6 a 8 segmentos; cada narración de 12 a 24 palabras, frases cortas y fáciles de decir en voz alta.
- El segmento 1 es un gancho con una pregunta o dato sorprendente. El último cierra con una \
consecuencia práctica y "Síguenos para más Explapix".
- Exactitud científica ante todo; si algo se simplifica, que no sea falso.
- Cada 'visual' describe un diagrama 2D sencillo de formas planas (cajas, flechas, puntos que \
fluyen, etiquetas) que se pueda animar con Manim, sin fotos ni personajes.
- title: <= 70 caracteres con un emoji. description: 2-3 frases + 3-5 hashtags (#Explapix primero).
- tags: 5-10 palabras clave en minúsculas."""

SCENE_SYSTEM = f"""Escribes escenas de Manim Community (v0.19+) para el canal Explapix.
Usa SOLO el kit de estilo siguiente (importa con `from explapix.kit import *`). Lienzo vertical \
9x16 unidades: x∈[-4.5,4.5], y∈[-8,8]. Deja libre y<-5.6 (subtítulos) y usa y>6 para el título.
Reglas duras:
- Define `class Video(ExplapixScene)` con `construct`, y un bloque `with self.segment(i) as d:` \
por segmento, en orden, i=0..N-1. Dentro de cada bloque la suma de run_time debe ser <= d - 0.3 \
(d es la duración real del audio, en segundos; abajo te paso cada una).
- Solo Text (la función T del kit), nunca Tex/MathTex (no hay LaTeX instalado). Nada de imágenes \
ni archivos externos. numpy disponible como np.
- Mantén todo dentro del cuadro; no dejes texto encimado. Reutiliza objetos entre segmentos para \
que el diagrama se vaya construyendo.
- Devuelve únicamente el código Python en un bloque ```python.

KIT:
```python
{KIT}
```

EJEMPLO COMPLETO DE REFERENCIA (refrigerador):
```python
{EXAMPLE}
```"""


def _text(resp) -> str:
    if resp.stop_reason == "refusal":
        raise RuntimeError("El modelo rechazó la solicitud")
    return "".join(b.text for b in resp.content if b.type == "text")


def storyboard(topic: str, notes: str = "") -> dict:
    resp = client.messages.create(
        model=MODEL, max_tokens=16000, system=STORYBOARD_SYSTEM,
        output_config={"effort": EFFORT,
                       "format": {"type": "json_schema", "schema": STORYBOARD_SCHEMA}},
        messages=[{"role": "user", "content": f"Tema: {topic}\n{notes}".strip()}],
    )
    return json.loads(_text(resp))


def scene_code(sb: dict, timing: dict, previous: str | None = None, error: str | None = None) -> str:
    segs = "\n".join(f"{i}. ({t['duration']:.2f} s) NARRACIÓN: {s['narration']}\n   VISUAL: {s['visual']}"
                     for i, (s, t) in enumerate(zip(sb["segments"], timing["segments"])))
    messages = [{"role": "user", "content": f"Tema: {sb['topic']}\nSegmentos:\n{segs}"}]
    if previous and error:
        messages += [{"role": "assistant", "content": f"```python\n{previous}\n```"},
                     {"role": "user", "content": f"El render falló con este error. Corrige el "
                      f"código completo:\n```\n{error[-4000:]}\n```"}]
    with client.messages.stream(
        model=MODEL, max_tokens=32000, system=[{"type": "text", "text": SCENE_SYSTEM,
                                                "cache_control": {"type": "ephemeral"}}],
        output_config={"effort": EFFORT}, messages=messages,
    ) as stream:
        resp = stream.get_final_message()
    txt = _text(resp)
    m = re.search(r"```python\n(.*?)```", txt, re.S)
    return (m.group(1) if m else txt).strip() + "\n"


def reply_to_comment(video_title: str, video_description: str, comment: str) -> dict:
    """Propone respuesta a un comentario. skip=True si no conviene responder (spam, odio...)."""
    schema = {"type": "object", "properties": {"skip": {"type": "boolean"},
                                               "reason": {"type": "string"},
                                               "reply": {"type": "string"}},
              "required": ["skip", "reason", "reply"], "additionalProperties": False}
    resp = client.messages.create(
        model=MODEL, max_tokens=2000,
        system=("Respondes comentarios del canal Explapix (divulgación). Español, cálido, breve "
                "(máx. 2 frases), sin inventar datos; si no sabes, dilo e invita a sugerir el tema. "
                "Marca skip=true para spam, insultos, enlaces sospechosos o comentarios que no "
                "necesitan respuesta."),
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": f"Video: {video_title}\n{video_description}\n\n"
                                              f"Comentario: {comment}"}],
    )
    return json.loads(_text(resp))
