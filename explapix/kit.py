"""Explapix kit: estilo visual común + base de escena sincronizada con la voz.

Las escenas (escritas a mano o generadas por Claude) heredan de ExplapixScene,
y dividen el video en segmentos cuya duración viene del audio de narración:

    class Video(ExplapixScene):
        def construct(self):
            with self.segment(0):      # dura exactamente lo que dura el audio 0
                ...animaciones...
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager

from manim import *  # noqa: F401,F403

# ---------- Paleta y tipografía ----------
BG = "#0F1226"
INK = "#F4F1EA"
MUTED = "#8D93B8"
ACCENT = "#FFB703"   # amarillo
HOT = "#FB5607"      # caliente
COLD = "#3A86FF"     # frío
GOOD = "#38D39F"
PINK = "#FF5D8F"
FONT = os.environ.get("EXPLAPIX_FONT", "DejaVu Sans")

config.background_color = BG
# Formato vertical 9:16 (Reels/Shorts/TikTok). EXPLAPIX_VERTICAL=0 para 16:9.
if os.environ.get("EXPLAPIX_VERTICAL", "1") == "1":
    config.frame_height = 16.0
    config.frame_width = 9.0


def T(txt: str, size: float = 40, color=INK, weight=BOLD, **kw) -> Text:
    return Text(txt, font=FONT, font_size=size, color=color, weight=weight, **kw)


def pill(txt: str, color=ACCENT, size: float = 30) -> VGroup:
    """Etiqueta redondeada (para nombrar partes)."""
    label = T(txt, size, BG)
    box = RoundedRectangle(corner_radius=0.18, width=label.width + 0.5,
                           height=label.height + 0.3, fill_color=color,
                           fill_opacity=1, stroke_width=0)
    return VGroup(box, label.move_to(box))


def card(w: float, h: float, color=MUTED, fill=None, r: float = 0.25) -> RoundedRectangle:
    return RoundedRectangle(corner_radius=r, width=w, height=h, stroke_color=color,
                            stroke_width=6, fill_color=fill or BG,
                            fill_opacity=1 if fill else 0)


def flow_dots(path: VMobject, n: int = 8, color=COLD, radius: float = 0.07,
              speed: float = 0.12, color_fn=None) -> VGroup:
    """Puntos que recorren un camino en bucle (fluido, electricidad, aire...).

    color_fn(p) -> color, opcional: colorea cada punto según su posición p∈[0,1).
    Se puede cambiar después con dots.color_fn = ...
    """
    dots = VGroup(*[Dot(radius=radius, color=color) for _ in range(n)])
    dots.color_fn = color_fn
    state = {"t": 0.0}

    def upd(group, dt):
        state["t"] = (state["t"] + dt * speed) % 1
        for i, d in enumerate(group):
            p = (state["t"] + i / n) % 1
            d.move_to(path.point_from_proportion(p))
            if group.color_fn is not None:
                d.set_color(group.color_fn(p))

    dots.add_updater(upd)
    upd(dots, 0)
    return dots


def color_lerp(a, b, alpha):
    return interpolate_color(ManimColor(a), ManimColor(b), alpha)


class ExplapixScene(Scene):
    """Base: carga tiempos de narración y muestra subtítulos por segmento."""

    timing_file = os.environ.get("EXPLAPIX_TIMING", "timing.json")
    show_captions = True

    def setup(self):
        with open(self.timing_file, encoding="utf-8") as f:
            data = json.load(f)
        self.durations = [s["duration"] for s in data["segments"]]
        self.captions = [s["text"] for s in data["segments"]]
        self._caption = None

    # Subtítulos estilo reel: bloques cortos (máx. 2 líneas) que van cambiando
    @staticmethod
    def _chunks(text: str, per_line: int = 24, lines_per_chunk: int = 2) -> list[list[str]]:
        words, lines, cur = text.split(), [], ""
        for w in words:
            if cur and len(cur) + len(w) + 1 > per_line:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            lines.append(cur)
        return [lines[i:i + lines_per_chunk] for i in range(0, len(lines), lines_per_chunk)]

    def _caption_block(self, lines: list[str]) -> VGroup:
        g = VGroup(*[T(l, 34, INK) for l in lines]).arrange(DOWN, buff=0.12)
        bg = RoundedRectangle(corner_radius=0.2, width=g.width + 0.5, height=g.height + 0.35,
                              fill_color=BLACK, fill_opacity=0.6, stroke_width=0)
        return VGroup(bg, g.move_to(bg)).to_edge(DOWN, buff=0.9)

    def _start_caption(self, text: str, duration: float):
        if self._caption is not None:
            self._caption.clear_updaters()
            self.remove(self._caption)
        chunks = self._chunks(text)
        weights = [sum(len(l) for l in c) for c in chunks]
        total = sum(weights) or 1
        bounds, acc = [], 0.0
        for w in weights:
            acc += duration * w / total
            bounds.append(acc)
        blocks = [self._caption_block(c) for c in chunks]
        holder = VGroup(blocks[0].copy())
        state = {"t": 0.0, "idx": 0}

        def upd(m, dt):
            state["t"] += dt
            idx = next((k for k, b in enumerate(bounds) if state["t"] < b), len(blocks) - 1)
            if idx != state["idx"]:
                state["idx"] = idx
                m.become(VGroup(blocks[idx].copy()))

        holder.add_updater(upd)
        self.add_foreground_mobject(holder)
        self._caption = holder

    @contextmanager
    def segment(self, i: int):
        start = self.renderer.time
        if self.show_captions:
            self._start_caption(self.captions[i], self.durations[i])
        yield self.durations[i]
        remaining = start + self.durations[i] - self.renderer.time
        if remaining > 1 / config.frame_rate:
            self.wait(remaining)
