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
MICRO = (Path(__file__).parent.parent / "examples/microondas/scene.py").read_text(encoding="utf-8")

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

STORYBOARD_SYSTEM = """Eres guionista del canal Factos Didácticos: videos verticales cortos (35-55 s) que \
explican cómo funcionan las cosas, en español latino neutro, tono curioso y cercano.
Reglas:
- 6 a 8 segmentos; cada narración de 12 a 24 palabras, frases cortas y fáciles de decir en voz alta.
- El segmento 1 es un gancho con una pregunta o dato sorprendente. El último cierra con una \
consecuencia práctica y "Síguenos para más Factos Didácticos".
- Exactitud científica ante todo; si algo se simplifica, que no sea falso.
- Cada 'visual' describe una escena 2D de formas planas redondeadas con volumen (estilo \
ilustración vectorial sobre fondo oscuro con brillos), animable con Manim, sin fotos. Los objetos \
protagonistas pueden tener carita (ojos, mejillas) y reaccionar: saltar, temblar, sorprenderse. \
Indica qué debe brillar, qué entra rebotando y dónde conviene acercar la cámara.
- title: <= 70 caracteres con un emoji. description: 2-3 frases + 3-5 hashtags (#FactosDidacticos primero).
- tags: 5-10 palabras clave en minúsculas."""

SCENE_SYSTEM = f"""Escribes escenas de Manim Community (v0.22+) para el canal Factos Didácticos.
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

ESTILO VISUAL (obligatorio):
- El fondo vivo ya lo pone ExplapixScene; no pongas fondos propios ni uses background_color.
- Formas con volumen: blob(), ball(), toon(shape, color), tube() para tuberías/cables. Nada de \
contornos blancos ni Rectangle/Circle planos sueltos para objetos principales.
- Colores de la paleta: BLUE, CYAN, VIOLET, PINK, CORAL, SUN, MINT, INK (texto), MUTED. HOT=CORAL, \
COLD=CYAN. Lo importante brilla: glow(obj, color) detrás; rays() para presentar un protagonista.
- Títulos con title_text(), etiquetas con pill(). Textos cortos (máx. 3-4 palabras por etiqueta).
- Personajes: los protagonistas llevan face() encima (mood feliz/sorpresa/serio/dormido) y \
auto_blink(); pon idle_breathe/idle_float a 1-3 objetos para que nada se vea congelado.

PRINCIPIOS DE ANIMACIÓN (aplícalos siempre):
1. Squash & stretch y follow-through: los objetos ENTRAN con pop_in (nunca FadeIn/Create para \
objetos sólidos); golpes y llegadas terminan con jelly().
2. Anticipación: los desplazamientos importantes usan anticipate_move; las salidas usan exit_out \
(nunca FadeOut a secas); los saltos usan squash_bounce.
3. Slow in/slow out: usa rate_func=EASE, POP o SNAP; rate lineal solo para flujos continuos.
4. Arcos: si algo viaja de A a B, usa move_along_arc.
5. Overlapping action: varios objetos entran con cascade(...) o LaggedStart con lag_ratio 0.1-0.25.
6. Staging: en el momento clave de cada idea acerca la cámara con self.play(self.focus(obj, zoom=1.4-1.8)) \
y vuelve con self.play(self.reset_camera()); o apaga el resto con self.play(self.dim_others(obj)).
7. Exageración: el dato sorprendente de cada segmento recibe emphasize().
8. Timing variado: alterna golpes rápidos (0.25-0.45 s) con movimientos lentos (0.8-1.2 s); deja \
0.3-0.8 s de pausa visual tras cada idea (el segment() ya rellena el final).
9. Acción secundaria: flow_dots en circuitos, idle_* en personajes, ondas o destellos (sparkle) de apoyo.
10. Cierre: en el último segmento llama self.clear_stage() y luego self.outro() (≈2 s en total).

DINAMISMO (kit v3, obligatorio):
- Fondo: cada segmento lleva un mood acorde a la idea: `with self.segment(i, mood="calor") as d:`.
  Moods: noche, energia, calor, frio, naturaleza, sol, magia. Cambia de mood al menos 3 veces por video.
- Cámara viva: llama self.cam_sway(1.2, 7) al inicio. En 3-4 momentos clave usa
  self.cam_to(obj_o_punto, zoom=1.3-1.8, angle=-8..8, dur=1.0-1.5) y luego self.cam_reset().
  cam_to NO va dentro de self.play: corre en paralelo a las animaciones. Giros suaves (máx. ±10°).
- Partículas en TODOS los segmentos: particles(kind, centro, ancho, alto, n) con kind en
  chispas, burbujas, calor, estrellas, confeti, frio, orbita, polvo; follow=obj para que sigan a un
  objeto. Añádelas con self.add(...) y quítalas con exit_out (antes .clear_updaters()).
- Nada quieto: cada objeto en pantalla tiene vida constante: alive(obj), idle_wiggle (etiquetas),
  idle_pulse (cosas con energía), idle_spin (engranes, platos, moléculas), idle_float. Antes de
  animar ese objeto con Deform/exit_out llama stop_idle(obj).
- No agregues a un VGroup objetos que ya están en escena (se duplican): anima por separado o
  quítalos con self.remove(...) y añade el grupo.
- Un objeto que salió con exit_out queda reducido a nada: para que vuelva, créalo de nuevo con una
  función (p. ej. make_oven()).

EJEMPLO DINÁMICO (kit v3, microondas) — imita su ritmo:
```python
{MICRO}
```
- No combines en el mismo self.play dos animaciones sobre el mismo objeto.
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
        system=("Respondes comentarios del canal Factos Didácticos (divulgación). Español, cálido, breve "
                "(máx. 2 frases), sin inventar datos; si no sabes, dilo e invita a sugerir el tema. "
                "Marca skip=true para spam, insultos, enlaces sospechosos o comentarios que no "
                "necesitan respuesta."),
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": f"Video: {video_title}\n{video_description}\n\n"
                                              f"Comentario: {comment}"}],
    )
    return json.loads(_text(resp))
