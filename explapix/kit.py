"""Kit v3 de Factos Didácticos (paquete interno: explapix): estilo, principios de animación,
cámara dinámica, partículas y base sincronizada con la voz.

Las escenas (escritas a mano o generadas por Claude) heredan de ExplapixScene y dividen el
video en segmentos cuya duración viene del audio de narración:

    class Video(ExplapixScene):
        def construct(self):
            with self.segment(0) as d:      # dura exactamente lo que dura el audio 0
                ...animaciones...

ESTILO (lenguaje visual de Factos Didácticos)
  - Fondo oscuro azul-violeta con degradado, brillo radial y polvo de estrellas de colores que
    deriva lento (profundidad por capas: lo lejano es pequeño, tenue y lento).
  - Formas planas redondeadas, SIN contorno blanco: relleno sólido + sombra tonal (media luna
    más oscura abajo-derecha) + borde de luz arriba-izquierda (toon()).
  - Colores saturados tipo neón sobre el fondo oscuro; lo importante brilla (glow()).
  - Objetos con carita (face()) cuando ayuda a la historia: ojos que parpadean, mejillas.
  - Tipografía redondeada: Fredoka (títulos/etiquetas) y Nunito (subtítulos), fuentes OFL.

PRINCIPIOS DE ANIMACIÓN -> AYUDANTES
  1 Squash & stretch ........ pop_in, squash_bounce, jelly, idle_breathe
  2 Anticipación ............ anticipate_move, exit_out (crece un poco antes de irse), squash_bounce
  3 Staging (puesta en escena) self.focus()/self.reset_camera() (zoom), self.dim_others(), rays()
  4 Pose a pose ............. Deform(fn) define poses clave como funciones del tiempo
  5 Follow-through/overlap .. pop_in con rebote, cascade(), jelly, LaggedStart con lag < 1
  6 Slow in / slow out ...... EASE, POP, SNAP (nunca rate lineal salvo flujos continuos)
  7 Arcos ................... move_along_arc (los objetos viajan en curva, no en recta)
  8 Acción secundaria ....... idle_breathe, idle_float, auto_blink, deriva del fondo
  9 Timing .................. TEMPO: rápido (0.25 s) para golpes, lento (1.2 s) para ideas
 10 Exageración ............. emphasize (escala 1.25 con resorte), squash marcado
 11 Dibujo sólido ........... toon(): volumen con sombra tonal + luz de borde + sombra al piso
 12 Appeal .................. caritas, formas redondeadas, paleta coherente

DINAMISMO (v3)
  - Fondo que cambia de color por segmento: self.mood("calor"|"frio"|"energia"|...) o
    with self.segment(i, mood="calor"). Transición suave sin bloquear otras animaciones.
  - Cámara viva: self.cam_to(center, zoom, angle) se mueve EN PARALELO a las animaciones
    (no usa self.play); self.cam_sway() balanceo suave constante. Los subtítulos quedan fijos.
  - Partículas: particles("chispas"|"burbujas"|"calor"|"estrellas"|"confeti"|"frio"|"orbita"|
    "polvo", center, w, h, n). Siempre vivas; follow=obj para que sigan a un objeto.
  - Vida constante: alive(obj) = flotar + pulso o balanceo; idle_wiggle, idle_pulse, idle_spin.
"""
from __future__ import annotations

import json
import os
import random
from contextlib import contextmanager
from pathlib import Path

import manimpango
import numpy as np
from manim import *  # noqa: F401,F403

# ---------- Fuentes (OFL, en ./fonts) ----------
_FONTS = Path(__file__).resolve().parent.parent / "fonts"
for _f in ("Fredoka.ttf", "Nunito.ttf"):
    if (_FONTS / _f).exists():
        manimpango.register_font(str(_FONTS / _f))
FONT = os.environ.get("EXPLAPIX_FONT", "Fredoka")
CAPTION_FONT = os.environ.get("EXPLAPIX_CAPTION_FONT", "Nunito")

# ---------- Paleta ----------
BG = "#0B0D26"        # fondo base (azul noche)
BG2 = "#26145A"       # fondo degradado (violeta)
INK = "#FFF8EE"       # texto / blanco cálido
MUTED = "#7E86C9"     # secundario
BLUE = "#2F6BFF"
CYAN = "#46E0FF"
VIOLET = "#8B5CFF"
PINK = "#FF4FA3"
CORAL = "#FF7A45"
SUN = "#FFC93C"
MINT = "#2EE6A8"
# alias semánticos (compatibles con el kit v1)
ACCENT = SUN
HOT = CORAL
COLD = CYAN
GOOD = MINT
PALETTE = [BLUE, CYAN, VIOLET, PINK, CORAL, SUN, MINT]

config.background_color = BG
# Formato vertical 9:16 (Reels/Shorts/TikTok). EXPLAPIX_VERTICAL=0 para 16:9.
if os.environ.get("EXPLAPIX_VERTICAL", "1") == "1":
    config.frame_height = 16.0
    config.frame_width = 9.0

# ---------- Curvas de tiempo (slow in/out, anticipación, overshoot) ----------
EASE = rate_functions.ease_in_out_cubic      # movimiento normal
POP = rate_functions.ease_out_back           # llega pasándose y regresa (overshoot)
SNAP = rate_functions.ease_out_expo          # golpe rápido que frena suave
WINDUP = rate_functions.ease_in_back         # se echa para atrás antes de salir


def anticipate_overshoot(t: float, tension: float = 2.2) -> float:
    """Retrocede un poco, sale disparado, se pasa del destino y se asienta."""
    a = lambda x: x * x * ((tension + 1) * x - tension)  # noqa: E731
    o = lambda x: x * x * ((tension + 1) * x + tension)  # noqa: E731
    return 0.5 * a(2 * t) if t < 0.5 else 0.5 * (o(2 * t - 2) + 2)


# ---------- Zona segura de Reels / Shorts / TikTok ----------
# Fracciones de la pantalla que la interfaz tapa: 12 % arriba, 20 % abajo, 15 % a la derecha y un
# margen de 5 % a la izquierda. Las escenas se diseñan en la caja de siempre (DESIGN_BOX) y el kit
# las encuadra solas dentro de la zona segura, dejando debajo una franja para los subtítulos.
SAFE_ZONE = {"top": 0.12, "bottom": 0.20, "right": 0.15, "left": 0.05}
CAPTION_BAND = 1.75            # alto de la franja de subtítulos (unidades de pantalla, 16 = alto)
DESIGN_BOX = (-4.3, 4.3, -5.0, 7.3)   # x0, x1, y0, y1 donde va TODO lo importante de la escena


def _safe_framing():
    W, H = config.frame_width, config.frame_height
    sx0 = -W / 2 + SAFE_ZONE["left"] * W
    sx1 = W / 2 - SAFE_ZONE["right"] * W
    sy1 = H / 2 - SAFE_ZONE["top"] * H
    sy0 = -H / 2 + SAFE_ZONE["bottom"] * H
    cy0 = sy0 + CAPTION_BAND                   # el contenido queda arriba de los subtítulos
    x0, x1, y0, y1 = DESIGN_BOX
    s = min((sx1 - sx0) / (x1 - x0), (sy1 - cy0) / (y1 - y0))
    screen_c = np.array([(sx0 + sx1) / 2, (cy0 + sy1) / 2, 0])
    world_c = np.array([(x0 + x1) / 2, (y0 + y1) / 2, 0])
    return {"scale": s, "center": world_c - screen_c / s, "height": H / s,
            "caption": np.array([(sx0 + sx1) / 2, sy0 + CAPTION_BAND / 2, 0]),
            "safe": (sx0, sx1, sy0, sy1), "content_center": screen_c}


BUTTONS_HEIGHT = 0.65   # fracción desde arriba donde suelen estar los botones de acción (columna derecha)

TEMPO = {"golpe": 0.25, "rapido": 0.45, "normal": 0.8, "lento": 1.2}


def shade(color, k: float) -> ManimColor:
    """k<0 oscurece hacia el fondo, k>0 aclara hacia blanco."""
    c = ManimColor(color)
    return interpolate_color(c, ManimColor(BG), -k) if k < 0 else interpolate_color(c, WHITE, k)


def color_lerp(a, b, alpha):
    return interpolate_color(ManimColor(a), ManimColor(b), alpha)


# ---------- Texto ----------
def T(txt: str, size: float = 40, color=INK, weight=BOLD, font: str | None = None, **kw) -> Text:
    return Text(txt, font=font or FONT, font_size=size, color=color, weight=weight, **kw)


def title_text(txt: str, size: float = 60, color=INK, max_width: float = 8.2) -> VGroup:
    """Título grande en mayúsculas (admite \\n) con sombra suave."""
    t = T(txt.upper(), size, color, line_spacing=0.8)
    if t.width > max_width:
        t.scale_to_fit_width(max_width)
    sh = t.copy().set_color(BLACK).set_opacity(0.35).shift(DOWN * 0.07 + RIGHT * 0.05)
    return VGroup(sh, t)


# ---------- Formas con volumen (dibujo sólido) ----------
def toon(shape: VMobject, color, depth: float = 0.14, rim: bool = True,
         floor_shadow: bool = False) -> VGroup:
    """Forma plana con sombra tonal (abajo-der.) y luz de borde (arriba-izq.).

    Devuelve VGroup(base, sombra, luz); .base es la forma principal para recolorear.
    """
    base = shape.copy().set_fill(color, 1).set_stroke(width=0)
    size = max(min(shape.width, shape.height), 0.2)
    d = depth * size
    parts = [base]
    try:
        sh = Difference(base, base.copy().shift(UL * d), fill_color=shade(color, -0.32),
                        fill_opacity=1, stroke_width=0)
        parts.append(sh)
        if rim:
            li = Difference(base, base.copy().shift(DR * d * 0.3), fill_color=shade(color, 0.5),
                            fill_opacity=0.9, stroke_width=0)
            parts.append(li)
    except Exception:  # formas abiertas o degeneradas: sin sombreado
        pass
    g = VGroup(*parts)
    if floor_shadow:
        fs = Ellipse(width=shape.width * 0.95, height=max(shape.width * 0.14, 0.12),
                     fill_color=BLACK, fill_opacity=0.35, stroke_width=0)
        fs.move_to(shape.get_bottom() + DOWN * 0.04)
        g.add_to_back(fs)
    g.base = base
    return g


def blob(w: float, h: float, color, r: float | None = None, **kw) -> VGroup:
    """Caja redondeada con volumen (el ladrillo básico de casi todo)."""
    r = min(w, h) * 0.22 if r is None else r
    return toon(RoundedRectangle(corner_radius=r, width=w, height=h), color, **kw)


def ball(radius: float, color, **kw) -> VGroup:
    return toon(Circle(radius=radius), color, **kw)


def glow(mob, color=None, radius: float | None = None, layers: int = 7,
         opacity: float = 0.2) -> VGroup:
    """Halo de luz detrás de un objeto (lo importante brilla). Ponlo antes del objeto."""
    color = color or CYAN
    radius = radius or max(mob.width, mob.height) * 0.75
    return VGroup(*[Circle(radius=radius * (1 + 0.18 * i), fill_color=color,
                           fill_opacity=opacity * (1 - i / layers) ** 2, stroke_width=0)
                    for i in range(layers)]).move_to(mob)


def rays(center=ORIGIN, color=BLUE, n: int = 14, length: float = 9, width: float = 0.6,
         opacity: float = 0.16, seed: int = 3) -> VGroup:
    """Rayos radiales detrás de un protagonista (puesta en escena)."""
    rng = random.Random(seed)
    g = VGroup()
    for i in range(n):
        ang = TAU * i / n + rng.uniform(-0.1, 0.1)
        L = length * rng.uniform(0.6, 1.0)
        g.add(Polygon(ORIGIN, rotate_vector(RIGHT * L, ang - width / L),
                      rotate_vector(RIGHT * L, ang + width / L), fill_color=color,
                      fill_opacity=opacity, stroke_width=0))
    return g.shift(np.array(center, dtype=float))


def pill(txt: str, color=ACCENT, size: float = 30, text_color=None) -> VGroup:
    """Etiqueta redondeada con volumen y sombra (para nombrar partes)."""
    label = T(txt, size, text_color or BG)
    box = RoundedRectangle(corner_radius=(label.height + 0.34) / 2, width=label.width + 0.6,
                           height=label.height + 0.34)
    body = toon(box, color, depth=0.1)
    drop = box.copy().set_fill(BLACK, 0.35).set_stroke(width=0).shift(DOWN * 0.08 + RIGHT * 0.04)
    return VGroup(drop, body, label.move_to(box))


def card(w: float, h: float, color=MUTED, fill=None, r: float = 0.25) -> VGroup:
    """Compatibilidad v1: ahora es un blob con volumen."""
    return blob(w, h, fill or color, r=r)


def tube(points, color=MUTED, width: float = 14) -> VGroup:
    """Tubo con volumen: trazo oscuro grueso + trazo claro fino encima."""
    P = [np.array([*p[:2], 0.0], dtype=float) for p in points]
    back = VMobject(stroke_color=shade(color, -0.35), stroke_width=width).set_points_as_corners(P)
    front = VMobject(stroke_color=color, stroke_width=width * 0.55).set_points_as_corners(P)
    front.shift(UL * 0.015)
    g = VGroup(back, front)
    g.path = back
    return g


def sparkle(size: float = 0.25, color=INK) -> VMobject:
    """Destello de 4 puntas."""
    pts = [rotate_vector(UP * (size if i % 2 == 0 else size * 0.22), i * TAU / 8) for i in range(8)]
    return Polygon(*pts, fill_color=color, fill_opacity=1, stroke_width=0)


# ---------- Íconos de llamados a la acción ----------
def cta_icon(kind: str, size: float = 0.9) -> VGroup:
    s = size
    if kind in ("save", "guardar"):
        g = Polygon([-0.32, 0.45, 0], [0.32, 0.45, 0], [0.32, -0.45, 0], [0, -0.2, 0], [-0.32, -0.45, 0],
                    fill_color=SUN, fill_opacity=1, stroke_width=0)
    elif kind in ("comment", "comentar"):
        bub = RoundedRectangle(corner_radius=0.22, width=0.95, height=0.7, fill_color=CYAN, fill_opacity=1,
                               stroke_width=0)
        tail = Polygon([-0.25, -0.3, 0], [-0.05, -0.3, 0], [-0.35, -0.55, 0], fill_color=CYAN, fill_opacity=1,
                       stroke_width=0)
        dots = VGroup(*[Dot(radius=0.06, color=BG).move_to([x, 0.02, 0]) for x in (-0.22, 0, 0.22)])
        g = VGroup(bub, tail, dots)
    elif kind in ("share", "compartir"):
        g = VGroup(Polygon([-0.45, -0.35, 0], [0.1, 0.05, 0], [0.1, -0.15, 0], fill_color=MINT, fill_opacity=1,
                           stroke_width=0),
                   Polygon([0.05, 0.35, 0], [0.5, 0, 0], [0.05, -0.35, 0], fill_color=MINT, fill_opacity=1,
                           stroke_width=0),
                   Rectangle(width=0.5, height=0.2, fill_color=MINT, fill_opacity=1, stroke_width=0)
                   .rotate(0.6).move_to([-0.15, -0.05, 0]))
    elif kind in ("like",):
        g = VGroup(Circle(0.22, fill_color=PINK, fill_opacity=1, stroke_width=0).move_to([-0.17, 0.12, 0]),
                   Circle(0.22, fill_color=PINK, fill_opacity=1, stroke_width=0).move_to([0.17, 0.12, 0]),
                   Polygon([-0.38, 0.05, 0], [0.38, 0.05, 0], [0, -0.4, 0], fill_color=PINK, fill_opacity=1,
                           stroke_width=0))
    else:  # follow / seguir: campana
        g = VGroup(Arc(radius=0.3, start_angle=0, angle=PI, color=VIOLET, stroke_width=0).set_fill(VIOLET, 1),
                   Rectangle(width=0.6, height=0.35, fill_color=VIOLET, fill_opacity=1, stroke_width=0)
                   .move_to([0, -0.15, 0]),
                   RoundedRectangle(corner_radius=0.06, width=0.85, height=0.13, fill_color=VIOLET,
                                    fill_opacity=1, stroke_width=0).move_to([0, -0.36, 0]),
                   Dot(radius=0.09, color=VIOLET).move_to([0, -0.5, 0]))
    return g.scale(s)


CTA_TEXT = {"save": "Guarda este video", "guardar": "Guarda este video", "comment": "Comenta", "comentar": "Comenta",
            "share": "Compártelo", "compartir": "Compártelo", "follow": "Síguenos", "seguir": "Síguenos",
            "like": "Dale like"}


# ---------- Caritas (appeal) ----------
def face(width: float = 1.0, mood: str = "feliz", eye_color=BG) -> VGroup:
    """Ojos + boca + mejillas. mood: feliz | sorpresa | dormido | serio.

    face.eyes es el grupo para parpadear. Colócala con .move_to(obj).
    """
    s = width
    eyes = VGroup()
    for x in (-0.28, 0.28):
        if mood == "dormido":
            e = Arc(radius=0.12 * s, start_angle=PI, angle=PI, color=eye_color, stroke_width=7 * s)
        else:
            h = 0.32 if mood == "sorpresa" else 0.26
            e = VGroup(Ellipse(width=0.17 * s, height=h * s, fill_color=eye_color, fill_opacity=1,
                               stroke_width=0),
                       Dot(radius=0.035 * s, color=WHITE).shift(UP * 0.06 * s + RIGHT * 0.03 * s))
        eyes.add(e.move_to(RIGHT * x * s))
    if mood == "sorpresa":
        mouth = Ellipse(width=0.16 * s, height=0.2 * s, fill_color=eye_color, fill_opacity=1,
                        stroke_width=0)
    elif mood == "serio":
        mouth = Line(LEFT * 0.1 * s, RIGHT * 0.1 * s, color=eye_color, stroke_width=7 * s)
    else:
        mouth = Arc(radius=0.13 * s, start_angle=PI + 0.5, angle=PI - 1.0, color=eye_color,
                    stroke_width=7 * s)
    mouth.shift(DOWN * 0.22 * s)
    cheeks = VGroup(*[Ellipse(width=0.2 * s, height=0.11 * s, fill_color=PINK, fill_opacity=0.6,
                              stroke_width=0).move_to(RIGHT * x * s + DOWN * 0.16 * s)
                      for x in (-0.45, 0.45)])
    g = VGroup(cheeks, eyes, mouth)
    g.eyes, g.mouth = eyes, mouth
    return g


# ---------- Animaciones con principios ----------
class Deform(Animation):
    """Deforma un objeto con fn(t)->(sx, sy, dy) anclado en `anchor` (DOWN = se apoya en el piso).

    Es la base de squash & stretch: sx*sy≈1 conserva el volumen. Pausa los updaters del objeto
    mientras dura (no combinar con idle_* sobre el mismo objeto en la misma animación).
    """

    def __init__(self, mobject, fn, anchor=DOWN, **kw):
        self.fn, self.anchor = fn, anchor
        super().__init__(mobject, **kw)

    def interpolate_mobject(self, alpha: float) -> None:
        sx, sy, dy = self.fn(self.rate_func(alpha))
        m = self.mobject
        m.become(self.starting_mobject)
        p = self.starting_mobject.get_critical_point(self.anchor)
        m.stretch(max(sx, 1e-3), 0, about_point=p).stretch(max(sy, 1e-3), 1, about_point=p)
        if dy:
            m.shift(UP * dy)


def _spring(t, freq=10.0, damp=6.0):
    return np.exp(-damp * t) * np.sin(freq * t)


def pop_in(mob, run_time: float = 0.6, anchor=DOWN, squash: float = 0.35, **kw) -> Animation:
    """Aparece creciendo desde 0, se pasa de tamaño y rebota como gelatina
    (squash/stretch + overshoot + follow-through). Úsalo en vez de FadeIn/Create para objetos."""
    def fn(t):
        s = 1 - np.exp(-6 * t) * np.cos(10 * t)
        v = squash * _spring(t)
        return s * (1 + v), s * (1 - v), 0
    a = Deform(mob, fn, anchor=anchor, run_time=run_time, rate_func=linear, introducer=True, **kw)
    a.sfx = "blip" if _has_text(mob) else "pop"
    return a


def _has_text(mob) -> bool:
    return any(isinstance(m, (Text, MarkupText)) for m in mob.get_family())


def _tag(anim, kind, at: float = 0.0, gain: float = 1.0):
    """Marca una animación con un efecto de sonido (at = fracción de su duración)."""
    anim.sfx, anim.sfx_at, anim.sfx_gain = kind, at, gain
    return anim


def squash_bounce(mob, height: float = 0.8, run_time: float = 0.9, **kw) -> Animation:
    """Salto completo: se agacha (anticipación), se estira al subir, se aplasta al caer."""
    def fn(t):
        if t < 0.18:                      # anticipación: se aplasta
            k = np.sin(np.pi * t / 0.36)
            return 1 + 0.18 * k, 1 - 0.22 * k, 0
        if t < 0.82:                      # en el aire (arco parabólico) + estiramiento
            u = (t - 0.18) / 0.64
            st = 0.15 * (1 - abs(2 * u - 1))
            return 1 - st * 0.6, 1 + st, height * 4 * u * (1 - u)
        u = (t - 0.82) / 0.18              # aterrizaje: aplasta y se asienta
        k = np.sin(np.pi * u) * (1 - u * 0.5)
        return 1 + 0.2 * k, 1 - 0.25 * k, 0
    return _tag(Deform(mob, fn, anchor=DOWN, run_time=run_time, rate_func=linear, **kw), "thud", 0.82)


def jelly(mob, amount: float = 0.18, run_time: float = 0.8, anchor=DOWN, **kw) -> Animation:
    """Tiembla como gelatina y se calma (follow-through después de un golpe)."""
    def fn(t):
        v = amount * np.exp(-4 * t) * np.sin(16 * t)
        return 1 + v, 1 - v, 0
    return _tag(Deform(mob, fn, anchor=anchor, run_time=run_time, rate_func=linear, **kw), "thud", 0, 0.5)


def emphasize(mob, scale: float = 1.25, run_time: float = 0.7, **kw) -> Animation:
    """Exageración: crece rápido y regresa con resorte."""
    def fn(t):
        if t < 0.3:
            s = 1 + (scale - 1) * SNAP(t / 0.3)
        else:
            u = (t - 0.3) / 0.7
            s = 1 + (scale - 1) * np.exp(-5 * u) * np.cos(9 * u)
        return s, s, 0
    return _tag(Deform(mob, fn, anchor=ORIGIN, run_time=run_time, rate_func=linear, **kw), "blip")


def exit_out(mob, run_time: float = 0.45, **kw) -> Animation:
    """Salida con anticipación: se infla un poquito y luego se encoge a nada (y se quita)."""
    def fn(t):
        if t < 0.25:
            s = 1 + 0.12 * np.sin(np.pi * t / 0.5)
        else:
            s = 1.12 * (1 - WINDUP((t - 0.25) / 0.75))
        return s, s, 0
    return _tag(Deform(mob, fn, anchor=ORIGIN, run_time=run_time, rate_func=linear, remover=True, **kw),
                "woosh", 0.1, 0.45)


def anticipate_move(mob, target, run_time: float = 0.9, **kw):
    """Mover con anticipación (retrocede) y overshoot (se pasa y vuelve)."""
    target = target.get_center() if isinstance(target, Mobject) else np.array(target, dtype=float)
    return _tag(mob.animate(run_time=run_time, rate_func=anticipate_overshoot, **kw).move_to(target).build(),
                "woosh", 0.3)


def move_along_arc(mob, target, angle: float = PI / 3, run_time: float = 0.9,
                   rate_func=EASE, **kw):
    """Viaja en arco (los movimientos naturales nunca son rectos)."""
    target = target.get_center() if isinstance(target, Mobject) else np.array(target, dtype=float)
    path = ArcBetweenPoints(mob.get_center(), target, angle=angle)
    return _tag(MoveAlongPath(mob, path, run_time=run_time, rate_func=rate_func, **kw), "woosh", 0.05)


def cascade(*mobs, anim=None, lag: float = 0.15, run_time: float | None = None) -> Animation:
    """Entradas escalonadas que se traslapan (overlapping action). anim(mob)->Animation."""
    anim = anim or (lambda m: pop_in(m))
    kw = {"run_time": run_time} if run_time else {}
    return LaggedStart(*[anim(m) for m in mobs], lag_ratio=lag, **kw)


def draw_in(mob, run_time: float = 1.0) -> Animation:
    """Trazo con slow in/out (para tubos, cables, caminos)."""
    return _tag(Create(mob, run_time=run_time, rate_func=EASE), "woosh", 0, 0.5)


# ---------- Acción secundaria (updaters que dan vida) ----------
def idle_breathe(mob, amp: float = 0.03, period: float = 2.6):
    """Respira: se estira y aplasta suavemente, apoyado en su base."""
    st = {"t": random.uniform(0, period), "f": 1.0}

    def upd(m, dt):
        st["t"] += dt
        f = 1 + amp * np.sin(TAU * st["t"] / period)
        p = m.get_bottom()
        m.stretch(f / st["f"], 1, about_point=p).stretch((st["f"] / f) ** 0.5, 0, about_point=p)
        st["f"] = f
    mob._idle = getattr(mob, "_idle", []) + [upd]
    mob.add_updater(upd)
    return mob


def idle_float(mob, amp: float = 0.08, period: float = 3.2):
    """Flota arriba-abajo (cosas ligeras: burbujas, átomos, nubes)."""
    st = {"t": random.uniform(0, period), "y": 0.0}

    def upd(m, dt):
        st["t"] += dt
        y = amp * np.sin(TAU * st["t"] / period)
        m.shift(UP * (y - st["y"]))
        st["y"] = y
    mob._idle = getattr(mob, "_idle", []) + [upd]
    mob.add_updater(upd)
    return mob


def auto_blink(fc: VGroup, every: float = 3.0):
    """Parpadeo automático de una carita (face())."""
    st = {"t": random.uniform(0, every), "f": 1.0}

    def upd(m, dt):
        st["t"] = (st["t"] + dt) % every
        b = st["t"] / 0.16
        f = max(1 - 0.9 * np.sin(np.pi * b), 0.1) if b < 1 else 1.0
        for e in m.eyes:
            e.stretch(f / st["f"], 1)
        st["f"] = f
    fc._idle = getattr(fc, "_idle", []) + [upd]
    fc.add_updater(upd)
    return fc


def stop_idle(*mobs):
    for m in mobs:
        for u in getattr(m, "_idle", []):
            m.remove_updater(u)
        m._idle = []


def flow_dots(path: VMobject, n: int = 8, color=COLD, radius: float = 0.07,
              speed: float = 0.12, color_fn=None, halo: bool = True) -> VGroup:
    """Puntos brillantes que recorren un camino en bucle (fluido, electricidad, aire...).

    color_fn(p) -> color, opcional: colorea cada punto según su posición p∈[0,1).
    Se puede cambiar después con dots.color_fn = ...
    """
    def make():
        d = Dot(radius=radius, color=color)
        if halo:
            return VGroup(Circle(radius=radius * 2.3, fill_color=color, fill_opacity=0.28,
                                 stroke_width=0), d)
        return VGroup(d)
    dots = VGroup(*[make() for _ in range(n)])
    dots.color_fn = color_fn
    state = {"t": 0.0}

    def upd(group, dt):
        state["t"] = (state["t"] + dt * speed) % 1
        for i, d in enumerate(group):
            p = (state["t"] + i / n) % 1
            d.move_to(path.point_from_proportion(p))
            if group.color_fn is not None:
                c = group.color_fn(p)
                d[-1].set_fill(c, 1)
                if len(d) > 1:
                    d[0].set_fill(c, 0.28)

    dots.add_updater(upd)
    upd(dots, 0)
    return dots


# ---------- Vida constante (acción secundaria) ----------
def idle_wiggle(mob, deg: float = 4, period: float = 1.8):
    """Se balancea de lado a lado (rotación pequeña de ida y vuelta)."""
    st = {"t": random.uniform(0, period), "a": 0.0}

    def upd(m, dt):
        st["t"] += dt
        a = np.deg2rad(deg) * np.sin(TAU * st["t"] / period)
        m.rotate(a - st["a"], about_point=m.get_center())
        st["a"] = a
    mob._idle = getattr(mob, "_idle", []) + [upd]
    mob.add_updater(upd)
    return mob


def idle_pulse(mob, amp: float = 0.05, period: float = 1.4):
    """Late: crece y se encoge un poquito (cosas con energía)."""
    st = {"t": random.uniform(0, period), "f": 1.0}

    def upd(m, dt):
        st["t"] += dt
        f = 1 + amp * np.sin(TAU * st["t"] / period)
        m.scale(f / st["f"])
        st["f"] = f
    mob._idle = getattr(mob, "_idle", []) + [upd]
    mob.add_updater(upd)
    return mob


def idle_spin(mob, turns_per_s: float = 0.25):
    """Gira sin parar (engranes, platos, ventiladores, moléculas)."""
    def upd(m, dt):
        m.rotate(TAU * turns_per_s * dt)
    mob._idle = getattr(mob, "_idle", []) + [upd]
    mob.add_updater(upd)
    return mob


def alive(mob, style: str = "float"):
    """Atajo de vida constante. style: float (flota+pulso) | wiggle | breathe | spin."""
    if style == "wiggle":
        return idle_wiggle(mob)
    if style == "breathe":
        return idle_breathe(mob)
    if style == "spin":
        return idle_spin(mob)
    idle_float(mob, amp=0.07, period=random.uniform(2.6, 3.6))
    return idle_pulse(mob, amp=0.025, period=random.uniform(1.6, 2.4))


# ---------- Partículas ----------
class Particles(VGroup):
    """Sistema de partículas vivo (se actualiza solo en cada fotograma).

    kind: chispas | burbujas | calor | estrellas | confeti | frio | orbita | polvo
    center/w/h: zona donde nacen. follow=obj: la zona sigue a ese objeto.
    rate: velocidad global (1 = normal). colors: lista de colores opcional.
    """

    DEFAULT_COLORS = {"chispas": [SUN, CORAL, INK], "burbujas": [CYAN, INK], "calor": [CORAL, SUN, PINK],
                      "estrellas": [INK, SUN, CYAN], "confeti": PALETTE, "frio": [CYAN, INK, BLUE],
                      "orbita": [CYAN, VIOLET, MINT], "polvo": [INK, MUTED, VIOLET]}

    def __init__(self, kind: str = "polvo", center=ORIGIN, w: float = 4, h: float = 4, n: int = 30,
                 colors=None, follow: Mobject | None = None, rate: float = 1.0, size: float = 1.0,
                 seed: int | None = None):
        super().__init__()
        self.kind, self.w, self.h, self.n, self.rate, self.size = kind, w, h, n, rate, size
        self.center0 = np.array(center, dtype=float)
        self.follow = follow
        self.colors = colors or self.DEFAULT_COLORS.get(kind, PALETTE)
        self.rng = np.random.default_rng(seed if seed is not None else random.randint(0, 10**6))
        self.pos = np.zeros((n, 2))
        self.vel = np.zeros((n, 2))
        self.age = np.zeros(n)
        self.life = np.ones(n)
        self.phase = self.rng.uniform(0, TAU, n)
        for i in range(n):
            self.add(self._make(i))
            self._spawn(i, initial=True)
        self.add_updater(lambda m, dt: m._step(dt))
        self._step(0)

    def _c(self):
        return self.colors[self.rng.integers(len(self.colors))]

    def _make(self, i):
        k, s = self.kind, self.size
        r = self.rng.uniform
        if k == "burbujas":
            return Circle(radius=r(0.06, 0.16) * s, stroke_color=self._c(), stroke_width=3,
                          fill_color=CYAN, fill_opacity=0.12)
        if k == "estrellas":
            return sparkle(r(0.06, 0.16) * s, self._c())
        if k == "confeti":
            return Rectangle(width=0.09 * s, height=0.18 * s, fill_color=self._c(), fill_opacity=1,
                             stroke_width=0).rotate(r(0, PI))
        rad = {"chispas": (0.03, 0.06), "calor": (0.04, 0.09), "frio": (0.03, 0.07),
               "orbita": (0.05, 0.09), "polvo": (0.015, 0.04)}.get(k, (0.03, 0.06))
        return Dot(radius=r(*rad) * s, color=self._c())

    def _origin(self):
        return self.follow.get_center() if self.follow is not None else self.center0

    def _spawn(self, i, initial=False):
        k, r = self.kind, self.rng.uniform
        w, h = self.w / 2, self.h / 2
        if k == "chispas":
            ang = r(0, TAU)
            sp = r(1.8, 4.0)
            self.pos[i] = [r(-0.15, 0.15), r(-0.15, 0.15)]
            self.vel[i] = [np.cos(ang) * sp, np.sin(ang) * sp + 1.0]
            self.life[i] = r(0.4, 0.9)
        elif k in ("burbujas", "calor"):
            self.pos[i] = [r(-w, w), -h]
            self.vel[i] = [0, r(0.6, 1.3) if k == "burbujas" else r(0.8, 1.6)]
            self.life[i] = self.h / self.vel[i][1]
        elif k in ("confeti", "frio"):
            self.pos[i] = [r(-w, w), h]
            self.vel[i] = [r(-0.4, 0.4), -(r(1.6, 3.0) if k == "confeti" else r(0.4, 0.9))]
            self.life[i] = self.h / -self.vel[i][1]
        elif k == "orbita":
            self.pos[i] = [r(0.5, 1.0), r(0, TAU)]          # (radio relativo, ángulo)
            self.vel[i] = [0, r(0.8, 2.0) * self.rng.choice([-1, 1])]
            self.life[i] = 1e9
        else:  # estrellas, polvo: posiciones fijas o deriva lenta
            self.pos[i] = [r(-w, w), r(-h, h)]
            self.vel[i] = [r(-0.1, 0.1), r(0.05, 0.25)] if k == "polvo" else [0, 0]
            self.life[i] = r(2, 5) if k == "polvo" else 1e9
        self.age[i] = r(0, self.life[i]) if initial and self.life[i] < 1e8 else 0.0

    def _step(self, dt):
        dt *= self.rate
        o = self._origin()
        k = self.kind
        for i, m in enumerate(self.submobjects):
            self.age[i] += dt
            if self.age[i] >= self.life[i]:
                self._spawn(i)
            a, fr = self.age[i], min(self.age[i] / self.life[i], 1.0)
            if k == "chispas":
                self.vel[i][1] -= 4.0 * dt
                self.pos[i] += self.vel[i] * dt
                op = 1 - fr
            elif k == "orbita":
                self.pos[i][1] += self.vel[i][1] * dt
                rad = self.pos[i][0] * min(self.w, self.h) / 2
                xy = [rad * np.cos(self.pos[i][1]), rad * np.sin(self.pos[i][1]) * 0.55]
                m.move_to(o + np.array([*xy, 0]))
                m.set_opacity(0.9)
                continue
            elif k == "estrellas":
                op = 0.25 + 0.75 * abs(np.sin(a * 1.7 + self.phase[i]))
            else:
                self.pos[i] += self.vel[i] * dt
                if k in ("burbujas", "calor", "frio", "polvo"):
                    self.pos[i][0] += 0.25 * np.sin(a * 3 + self.phase[i]) * dt
                op = np.sin(np.pi * fr) if k != "confeti" else (1 if fr < 0.85 else (1 - fr) / 0.15)
            m.move_to(o + np.array([*self.pos[i], 0]))
            if k == "confeti":
                m.rotate(3 * dt * (1 if i % 2 else -1))
            if k == "burbujas":
                m.set_stroke(opacity=op).set_fill(opacity=0.12 * op)
            else:
                m.set_opacity(max(op, 0))


def particles(kind: str = "polvo", center=ORIGIN, w: float = 4, h: float = 4, n: int = 30,
              **kw) -> Particles:
    """Atajo: self.add(particles("chispas", obj.get_center(), 1, 1, 25, follow=obj))."""
    return Particles(kind, center, w, h, n, **kw)


# ---------- Fondo vivo ----------
MOODS = {  # (abajo, medio, arriba, halo)
    "noche": ("#0B0D26", "#0B0D26", "#26145A", VIOLET),
    "energia": ("#0D0B2E", "#1B0F4D", "#4A1A7A", VIOLET),
    "calor": ("#1F0A1E", "#3A0F24", "#6B1E2A", CORAL),
    "frio": ("#06142E", "#0A2450", "#0F3A6E", CYAN),
    "naturaleza": ("#061F1E", "#0A3330", "#11524A", MINT),
    "sol": ("#1E1206", "#3A2208", "#6A3A0C", SUN),
    "magia": ("#1A0726", "#33104A", "#5E1A6E", PINK),
}


def backdrop(w: float = 30, h: float = 48, n: int = 110, seed: int = 7) -> VGroup:
    """Degradado + brillo + polvo de estrellas en 3 capas que derivan (parallax)."""
    rng = random.Random(seed)
    grad = Rectangle(width=w, height=h, stroke_width=0)
    lo, mid, hi, hc = MOODS["noche"]
    grad.set_fill(color=[lo, mid, hi], opacity=1).set_sheen_direction(UP)
    halo = glow(Dot(), hc, radius=3.5, layers=8, opacity=0.07).shift(UP * 1.5)
    layers = VGroup()
    specs = [(n // 2, 0.015, 0.035, 0.35, 0.02), (n // 3, 0.035, 0.06, 0.55, 0.045),
             (n // 6, 0.06, 0.1, 0.8, 0.08)]
    for depth, (cnt, rmin, rmax, op, spd) in enumerate(specs):
        layer = VGroup()
        for _ in range(cnt):
            c = rng.choice(PALETTE + [INK, INK])
            x, y = rng.uniform(-w / 2, w / 2), rng.uniform(-h / 2, h / 2)
            layer.add(Dot([x, y, 0], radius=rng.uniform(rmin, rmax), color=c, fill_opacity=op))
        for _ in range(2 + depth):
            layer.add(sparkle(rng.uniform(0.07, 0.14), INK).set_opacity(op).move_to(
                [rng.uniform(-4.2, 4.2), rng.uniform(-7.5, 7.5), 0]))
        layer.add_updater(lambda m, dt, spd=spd: m.shift(UP * spd * dt))
        layers.add(layer)
    g = VGroup(grad, halo, layers)
    g.grad, g.halo = grad, halo
    return g


class RotatingCamera(MovingCamera):
    """MovingCamera que además puede girar: rota todo al dibujar alrededor del centro del cuadro."""

    def transform_points_pre_display(self, mobject, points):
        points = super().transform_points_pre_display(mobject, points)
        ang = getattr(self.frame, "cam_angle", 0.0)
        if not ang or len(points) == 0:
            return points
        c = self.frame.get_center()
        ca, sa = np.cos(-ang), np.sin(-ang)
        p = points - c
        x = p[:, 0] * ca - p[:, 1] * sa
        y = p[:, 0] * sa + p[:, 1] * ca
        out = np.array(points, dtype=float)
        out[:, 0], out[:, 1] = x + c[0], y + c[1]
        return out


class ExplapixScene(MovingCameraScene):
    """Base: fondo vivo con moods, cámara que gira/paneo/zoom, subtítulos fijos sincronizados."""

    timing_file = os.environ.get("EXPLAPIX_TIMING", "timing.json")
    show_captions = True
    show_backdrop = True

    def __init__(self, **kw):
        kw.setdefault("camera_class", RotatingCamera)
        super().__init__(**kw)

    def setup(self):
        super().setup()
        with open(self.timing_file, encoding="utf-8") as f:
            data = json.load(f)
        self.durations = [s["duration"] for s in data["segments"]]
        self.captions = [s["text"] for s in data["segments"]]
        self.ctas = [""] * len(self.captions)
        sbp = os.environ.get("EXPLAPIX_STORYBOARD")
        if sbp and os.path.exists(sbp):
            try:
                with open(sbp, encoding="utf-8") as f:
                    segs = json.load(f).get("segments", [])
                self.ctas = [(s_.get("cta") or "") for s_ in segs][:len(self.captions)]
                self.ctas += [""] * (len(self.captions) - len(self.ctas))
            except (OSError, ValueError):
                pass
        self._caption = None
        self._tweens: list[dict] = []
        self._clock = 0.0
        self._angle = 0.0
        self._sway = {"amp": 0.0, "period": 7.0}
        self.frame.cam_angle = 0.0
        self._sfx_events: list[dict] = []
        sf = _safe_framing() if os.environ.get("EXPLAPIX_SAFE", "1") == "1" else None
        self._base_center = sf["center"] if sf else ORIGIN.copy()
        self._base_height = sf["height"] if sf else config.frame_height
        self._caption_pos = sf["caption"] if sf else DOWN * 6.3
        self._content_screen = sf["content_center"] if sf else ORIGIN.copy()
        self.frame.move_to(self._base_center).set(height=self._base_height)
        self._sfx_events.append({"t": 0.0, "kind": "layout_safe" if sf else "layout_full", "gain": 0})
        self.bg = backdrop() if self.show_backdrop else VGroup()
        self.add(self.bg)
        ticker = VMobject()          # motor de tweens no bloqueantes (cámara, color de fondo)
        ticker.add_updater(lambda m, dt: self._tick(dt))
        self._ticker = ticker
        self.add(ticker)
        if os.environ.get("EXPLAPIX_SAFE_DEBUG") == "1":
            self._add_safe_debug()

    def _add_safe_debug(self):
        """Dibuja la zona segura (verde), la franja de subtítulos (amarillo) y lo que tapa la interfaz."""
        sx0, sx1, sy0, sy1 = _safe_framing()["safe"]
        frame = self.frame
        guide = VGroup()

        def build(m, dt=0):
            k = frame.height / config.frame_height
            c = frame.get_center()
            safe = Rectangle(width=(sx1 - sx0) * k, height=(sy1 - sy0) * k, stroke_color=GREEN,
                             stroke_width=4).move_to(c + np.array([(sx0 + sx1) / 2, (sy0 + sy1) / 2, 0]) * k)
            band = Rectangle(width=(sx1 - sx0) * k, height=CAPTION_BAND * k, stroke_color=YELLOW,
                             stroke_width=3).move_to(c + self._caption_pos * k)
            g = VGroup(safe, band)
            ang = getattr(frame, "cam_angle", 0.0)
            if ang:
                g.rotate(ang, about_point=c)
            m.become(g)
        guide.add_updater(build)
        build(guide)
        self._guide = guide
        self.add_foreground_mobject(guide)

    # ----- efectos de sonido -----
    def sfx(self, kind: str = "pop", delay: float = 0.0, gain: float = 1.0):
        """Agrega un efecto en el momento actual (+delay s): pop | woosh | blip | shimmer | thud."""
        self._sfx_events.append({"t": round(self.renderer.time + delay, 3), "kind": kind,
                                 "gain": gain})

    def _collect_sfx(self, anim, t0: float, scale: float = 1.0):
        rt = anim.get_run_time() * scale
        if getattr(anim, "sfx", None):
            self._sfx_events.append({"t": round(t0 + rt * getattr(anim, "sfx_at", 0.0), 3),
                                     "kind": anim.sfx, "gain": getattr(anim, "sfx_gain", 1.0)})
        timings = getattr(anim, "anims_with_timings", None)
        if timings is not None and len(timings):
            total = max(float(getattr(anim, "max_end_time", 0)) or 1e-6, 1e-6)
            k = rt / total
            for sub, start, _end in timings:
                self._collect_sfx(sub, t0 + float(start) * k, k)

    def play(self, *args, **kwargs):
        t0 = self.renderer.time
        try:
            anims = [a for a in args if isinstance(a, Animation)]
            rt = kwargs.get("run_time")
            for a in anims:
                if rt is not None:
                    a.run_time = rt
                self._collect_sfx(a, t0)
        except Exception:  # noqa: BLE001  (los efectos nunca deben romper el render)
            pass
        return super().play(*args, **kwargs)

    def add(self, *mobjects):
        for m in mobjects:
            if isinstance(m, Particles) and m.kind in ("chispas", "confeti", "estrellas", "orbita") \
                    and hasattr(self, "_sfx_events") and hasattr(self, "renderer"):
                self.sfx("shimmer", gain=0.7)
        return super().add(*mobjects)

    def tear_down(self):
        path = os.environ.get("EXPLAPIX_SFX_EVENTS")
        if path and hasattr(self, "_sfx_events"):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sorted(self._sfx_events, key=lambda e: e["t"]), f)
        super().tear_down()

    def get_moving_mobjects(self, *animations):
        # La cámara puede girar/moverse por tweens en cualquier momento: redibujar todo siempre.
        return list(self.mobjects)

    # ----- tweens no bloqueantes -----
    def _tick(self, dt):
        self._clock += dt
        for tw in list(self._tweens):
            u = min((self._clock - tw["t0"]) / tw["dur"], 1.0)
            tw["fn"](tw["rate"](u))
            if u >= 1:
                self._tweens.remove(tw)
        pc = getattr(self, "_pending_cta", None)
        if pc and self.renderer.time >= pc[0]:
            self._pending_cta = None
            self.cta(pc[1], dur=min(2.8, max(1.8, pc[2] * 0.6)))
        sway = self._sway["amp"] * np.sin(TAU * self._clock / self._sway["period"])
        self.frame.cam_angle = self._angle + sway

    def tween(self, fn, dur: float = 1.0, rate=EASE):
        """Ejecuta fn(alpha) durante dur segundos en paralelo a lo que se esté animando."""
        self._tweens.append({"fn": fn, "t0": self._clock, "dur": max(dur, 1e-3), "rate": rate})

    # ----- cámara (staging) -----
    @property
    def frame(self):
        return self.camera.frame

    def cam_to(self, center=None, zoom: float | None = None, angle: float | None = None,
               dur: float = 1.2, rate=EASE):
        """Mueve la cámara SIN bloquear: centro (punto u objeto), zoom (1 = normal) y giro en grados
        (usa giros suaves: entre -12 y 12). Ej.: self.cam_to(motor, zoom=1.5, angle=-6)."""
        c0 = self.frame.get_center().copy()
        h0 = self.frame.height
        a0 = self._angle
        c1 = (center.get_center() if isinstance(center, Mobject) else np.array(center, dtype=float)) \
            if center is not None else c0
        if center is not None and not (isinstance(center, np.ndarray) and center is self._base_center):
            c1 = self._focus_center(c1, zoom or (self._base_height / h0))
        h1 = self._base_height / zoom if zoom else h0
        a1 = np.deg2rad(angle) if angle is not None else a0

        if hasattr(self, "_sfx_events"):
            self.sfx("woosh", gain=0.8)

        def fn(a):
            self.frame.move_to(c0 + (c1 - c0) * a)
            self.frame.set(height=h0 + (h1 - h0) * a)
            self._angle = a0 + (a1 - a0) * a
        self.tween(fn, dur, rate)

    def cam_reset(self, dur: float = 1.0):
        self.cam_to(self._base_center, 1.0, 0.0, dur)

    def _focus_center(self, p, zoom):
        """Centro del cuadro para que p quede en el centro de la zona segura con ese zoom."""
        k = self._base_height / zoom / config.frame_height
        return np.array(p, dtype=float) - self._content_screen * k

    def cam_sway(self, amp_deg: float = 1.5, period: float = 7.0):
        """Balanceo suave y constante de la cámara (0 para apagarlo)."""
        self._sway = {"amp": np.deg2rad(amp_deg), "period": period}

    def focus(self, target, zoom: float = 1.5, run_time: float = 1.0, rate_func=EASE):
        """Acerca la cámara a algo (bloqueante, para usar dentro de self.play)."""
        p = target.get_center() if isinstance(target, Mobject) else np.array(target, dtype=float)
        return self.frame.animate(run_time=run_time, rate_func=rate_func).move_to(
            self._focus_center(p, zoom)).set(height=self._base_height / zoom)

    def reset_camera(self, run_time: float = 0.9, rate_func=EASE):
        a0 = self._angle
        self.tween(lambda a: setattr(self, "_angle", a0 * (1 - a)), run_time, rate_func)
        return self.frame.animate(run_time=run_time, rate_func=rate_func).move_to(self._base_center).set(
            height=self._base_height)

    # ----- color del fondo -----
    def mood(self, name="noche", dur: float = 1.2):
        """Cambia el color del fondo suavemente (sin bloquear). name: clave de MOODS o
        tupla (abajo, medio, arriba, halo)."""
        if not self.show_backdrop:
            return
        lo, mid, hi, hc = MOODS[name] if isinstance(name, str) else name
        grad, halo = self.bg.grad, self.bg.halo
        start = [ManimColor(c) for c in grad.get_fill_colors()][:3]
        while len(start) < 3:
            start.append(start[-1])
        end = [ManimColor(c) for c in (lo, mid, hi)]
        if hasattr(self, "_sfx_events"):
            self.sfx("shimmer", gain=0.6)
        h0 = ManimColor(halo[0].get_fill_color())
        h1 = ManimColor(hc)

        def fn(a):
            grad.set_fill(color=[interpolate_color(s, e, a) for s, e in zip(start, end)], opacity=1)
            for c in halo:
                c.set_fill(interpolate_color(h0, h1, a))
        self.tween(fn, dur, EASE)

    # ----- escenario -----
    def stage(self) -> list:
        """Todo lo que está en escena excepto fondo, motor y subtítulos."""
        return [m for m in self.mobjects if isinstance(m, VMobject) and m is not self.bg
                and m is not self._caption and m is not self.frame and m is not self._ticker
                and m is not getattr(self, "_guide", None)]

    def dim_others(self, *keep, opacity: float = 0.2, run_time: float = 0.5):
        """Apaga todo menos lo que importa (staging). Devuelve una animación."""
        others = [m for m in self.stage() if m not in keep]
        return AnimationGroup(*[m.animate(run_time=run_time).set_opacity(opacity) for m in others])

    def clear_stage(self, run_time: float = 0.7):
        """Saca todo con anticipación y en cascada."""
        ms = self.stage()
        for m in ms:
            m.clear_updaters()
        if ms:
            self.play(LaggedStart(*[exit_out(m) for m in ms], lag_ratio=0.05, run_time=run_time))

    def cta(self, kind: str, text: str | None = None, dur: float = 2.6):
        """Ícono de llamado a la acción (save|comment|share|follow|like) sobre los subtítulos, dentro de la
        zona segura. No bloquea: corre en paralelo a las animaciones del segmento."""
        icon = cta_icon(kind)
        label = T(text or CTA_TEXT.get(kind, kind), 32, INK, weight=HEAVY, font=CAPTION_FONT)
        label.set_stroke(BLACK, width=7, background=True)
        badge = VGroup(icon, label).arrange(RIGHT, buff=0.25)
        bg = RoundedRectangle(corner_radius=0.35, width=badge.width + 0.6, height=badge.height + 0.35,
                              fill_color=BLACK, fill_opacity=0.45, stroke_width=0)
        base = VGroup(bg, badge.move_to(bg))
        # flecha hacia la columna de botones de la derecha (guardar, comentar, compartir)
        point = kind in ("save", "guardar", "comment", "comentar", "share", "compartir", "like")
        arrow = Arrow(LEFT * 0.7, RIGHT * 0.7, buff=0, color=SUN, stroke_width=16,
                      max_tip_length_to_length_ratio=0.3, max_stroke_width_to_length_ratio=12) if point else VGroup()
        holder = VGroup(base.copy())
        frame, st = self.frame, {"t": 0.0}
        pos = self._caption_pos + UP * (CAPTION_BAND / 2 + 0.55)
        W, H = config.frame_width, config.frame_height
        btn_y = H / 2 - BUTTONS_HEIGHT * H                      # altura de los botones de acción
        sx1 = W / 2 - SAFE_ZONE["right"] * W
        arrow_end = np.array([W / 2 - 0.55, btn_y, 0])   # entra a la columna de botones
        self._sfx_events.append({"t": round(self.renderer.time, 3), "kind": f"cta_{kind}", "gain": 0})

        def upd(m, dt):
            st["t"] += dt
            t = st["t"]
            if t > dur:
                m.clear_updaters()
                self.remove(m)
                return
            s_in = 1 - np.exp(-7 * t) * np.cos(11 * t)               # pop con rebote
            s_out = 1 if t < dur - 0.3 else max(0.0, (dur - t) / 0.3)
            wig = 0.12 * np.sin(t * 9) * np.exp(-t * 2) if t < 1.2 else 0.0
            k = frame.height / config.frame_height
            c = frame.get_center()
            b = base.copy().scale(max(s_in * s_out, 0.01) * k).rotate(wig).move_to(c + pos * k)
            g = VGroup(b)
            if point and t > 0.25:
                # anticipación (retrocede), disparo con rebote y empujoncitos hacia los botones
                u = t - 0.25
                nudge = 0.25 * np.sin(u * 7) * np.exp(-u * 0.6) if u > 0.6 else 0.0
                start = np.array([b.get_right()[0] / k - c[0] / k + 0.15, (pos[1] + btn_y) / 2, 0])
                end = arrow_end + RIGHT * nudge
                prog = anticipate_overshoot(min(u / 0.6, 1.0))
                tip = start + (end - start) * prog
                ar = arrow.copy().put_start_and_end_on(start * k + c, tip * k + c + 1e-3 * RIGHT)
                ar.set_opacity(s_out)
                g.add(ar)
            ang = getattr(frame, "cam_angle", 0.0)
            if ang:
                g.rotate(ang, about_point=c)
            m.become(g)
        holder.add_updater(upd)
        upd(holder, 0)
        self.sfx("pop")
        self.sfx("blip", 0.15)
        self.add_foreground_mobject(holder)

    def chapter(self, title: str, color=None):
        """Mini-título de capítulo (videos largos): entra con pop, se queda ~0.6 s y sale (≈1.1 s)."""
        kf = self.frame.height / config.frame_height
        c = self.frame.get_center() + self._content_screen * kf + UP * 2.2 * kf
        card = pill(title, color or VIOLET, 40, text_color=INK).scale(kf).move_to(c)
        self.sfx("blip")
        self.play(pop_in(card, anchor=ORIGIN, run_time=0.45))
        self.wait(0.35)
        self.play(exit_out(card, run_time=0.3))

    def outro(self):
        """Cierre de marca con confeti (≈1.2 s)."""
        kf = self.frame.height / config.frame_height
        c = self.frame.get_center() + self._content_screen * kf
        l1 = T("FACTOS", 92, INK)
        l2 = T("DIDÁCTICOS", 64, SUN)
        logo = VGroup(l1, l2).arrange(DOWN, buff=0.05)
        sub = T("ciencia de todos los días", 30, MUTED, weight=NORMAL).next_to(logo, DOWN, buff=0.3)
        halo = glow(logo, VIOLET, radius=3.2, opacity=0.18).move_to(c)
        VGroup(logo, sub).scale(kf).move_to(c)
        halo.scale(kf).move_to(c)
        conf = particles("confeti", c + UP * 2 * kf, 9 * kf, 12 * kf, 60)
        self.add(conf)
        self.sfx("pop", 0.1)
        self.sfx("pop", 0.35, 0.8)
        self.play(FadeIn(halo, run_time=0.3), pop_in(l1, run_time=0.8, anchor=ORIGIN),
                  Succession(Wait(0.15), pop_in(l2, run_time=0.7, anchor=ORIGIN)),
                  FadeIn(sub, shift=UP * 0.2, run_time=0.6))
        idle_pulse(logo, amp=0.02, period=1.6)
        return VGroup(halo, logo, sub, conf)

    # ----- subtítulos estilo reel (fijos aunque la cámara gire) -----
    @staticmethod
    def _chunks(text: str, per_line: int = 22, lines_per_chunk: int = 2) -> list[list[str]]:
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
        g = VGroup(*[T(l, 40, INK, weight=HEAVY, font=CAPTION_FONT) for l in lines]).arrange(
            DOWN, buff=0.14)
        g.set_stroke(BLACK, width=9, background=True)
        sx0, sx1, _, _ = _safe_framing()["safe"]
        if g.width > (sx1 - sx0) * 0.96:
            g.scale_to_fit_width((sx1 - sx0) * 0.96)
        return g.move_to(ORIGIN)

    def _start_caption(self, text: str, duration: float):
        if self._caption is not None:
            self._caption.clear_updaters()
            self.remove(self._caption)
        chunks = self._chunks(text)
        weights = [sum(len(l) for l in c) + 6 for c in chunks]
        total = sum(weights) or 1
        bounds, acc = [], 0.0
        for w in weights:
            acc += duration * w / total
            bounds.append(acc)
        blocks = [self._caption_block(c) for c in chunks]
        state = {"t": 0.0, "idx": -1, "since": 0.0}
        frame = self.frame
        holder = VGroup(blocks[0].copy())

        def upd(m, dt):
            state["t"] += dt
            state["since"] += dt
            idx = next((k for k, b in enumerate(bounds) if state["t"] < b), len(blocks) - 1)
            if idx != state["idx"]:
                state["idx"], state["since"] = idx, 0.0
            s = 0.88 + 0.12 * POP(min(state["since"] / 0.2, 1))   # pop al cambiar de bloque
            k = frame.height / config.frame_height                  # sigue al zoom
            c = frame.get_center()
            b = blocks[state["idx"]].copy().scale(s * k).move_to(c + self._caption_pos * k)
            ang = getattr(frame, "cam_angle", 0.0)
            if ang:
                b.rotate(ang, about_point=c)                         # compensa el giro de cámara
            m.become(VGroup(b))

        holder.add_updater(upd)
        upd(holder, 0)
        self.add_foreground_mobject(holder)
        self._caption = holder

    @contextmanager
    def segment(self, i: int, mood: str | None = None):
        start = self.renderer.time
        if mood:
            self.mood(mood)
        if self.show_captions:
            self._start_caption(self.captions[i], self.durations[i])
        kind = self.ctas[i] if i < len(getattr(self, "ctas", [])) else ""
        if kind:   # el ícono aparece cuando se empieza a decir el CTA (aprox. a mitad del segmento)
            d = self.durations[i]
            self._pending_cta = (self.renderer.time + max(d * 0.35, 0.3), kind, d)
        yield self.durations[i]
        remaining = start + self.durations[i] - self.renderer.time
        if remaining > 1 / config.frame_rate:
            self.wait(remaining)
