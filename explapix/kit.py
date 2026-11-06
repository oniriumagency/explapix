"""Explapix kit v2: estilo visual + principios de animación + base sincronizada con la voz.

Las escenas (escritas a mano o generadas por Claude) heredan de ExplapixScene y dividen el
video en segmentos cuya duración viene del audio de narración:

    class Video(ExplapixScene):
        def construct(self):
            with self.segment(0) as d:      # dura exactamente lo que dura el audio 0
                ...animaciones...

ESTILO (lenguaje visual Explapix)
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
    return Deform(mob, fn, anchor=anchor, run_time=run_time, rate_func=linear,
                  introducer=True, **kw)


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
    return Deform(mob, fn, anchor=DOWN, run_time=run_time, rate_func=linear, **kw)


def jelly(mob, amount: float = 0.18, run_time: float = 0.8, anchor=DOWN, **kw) -> Animation:
    """Tiembla como gelatina y se calma (follow-through después de un golpe)."""
    def fn(t):
        v = amount * np.exp(-4 * t) * np.sin(16 * t)
        return 1 + v, 1 - v, 0
    return Deform(mob, fn, anchor=anchor, run_time=run_time, rate_func=linear, **kw)


def emphasize(mob, scale: float = 1.25, run_time: float = 0.7, **kw) -> Animation:
    """Exageración: crece rápido y regresa con resorte."""
    def fn(t):
        if t < 0.3:
            s = 1 + (scale - 1) * SNAP(t / 0.3)
        else:
            u = (t - 0.3) / 0.7
            s = 1 + (scale - 1) * np.exp(-5 * u) * np.cos(9 * u)
        return s, s, 0
    return Deform(mob, fn, anchor=ORIGIN, run_time=run_time, rate_func=linear, **kw)


def exit_out(mob, run_time: float = 0.45, **kw) -> Animation:
    """Salida con anticipación: se infla un poquito y luego se encoge a nada (y se quita)."""
    def fn(t):
        if t < 0.25:
            s = 1 + 0.12 * np.sin(np.pi * t / 0.5)
        else:
            s = 1.12 * (1 - WINDUP((t - 0.25) / 0.75))
        return s, s, 0
    return Deform(mob, fn, anchor=ORIGIN, run_time=run_time, rate_func=linear, remover=True, **kw)


def anticipate_move(mob, target, run_time: float = 0.9, **kw):
    """Mover con anticipación (retrocede) y overshoot (se pasa y vuelve)."""
    target = target.get_center() if isinstance(target, Mobject) else np.array(target, dtype=float)
    return mob.animate(run_time=run_time, rate_func=anticipate_overshoot, **kw).move_to(target)


def move_along_arc(mob, target, angle: float = PI / 3, run_time: float = 0.9,
                   rate_func=EASE, **kw):
    """Viaja en arco (los movimientos naturales nunca son rectos)."""
    target = target.get_center() if isinstance(target, Mobject) else np.array(target, dtype=float)
    path = ArcBetweenPoints(mob.get_center(), target, angle=angle)
    return MoveAlongPath(mob, path, run_time=run_time, rate_func=rate_func, **kw)


def cascade(*mobs, anim=None, lag: float = 0.15, run_time: float | None = None) -> Animation:
    """Entradas escalonadas que se traslapan (overlapping action). anim(mob)->Animation."""
    anim = anim or (lambda m: pop_in(m))
    kw = {"run_time": run_time} if run_time else {}
    return LaggedStart(*[anim(m) for m in mobs], lag_ratio=lag, **kw)


def draw_in(mob, run_time: float = 1.0) -> Animation:
    """Trazo con slow in/out (para tubos, cables, caminos)."""
    return Create(mob, run_time=run_time, rate_func=EASE)


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


# ---------- Fondo vivo ----------
def backdrop(w: float = 27, h: float = 48, n: int = 90, seed: int = 7) -> VGroup:
    """Degradado + brillo + polvo de estrellas en 3 capas que derivan (parallax)."""
    rng = random.Random(seed)
    grad = Rectangle(width=w, height=h, stroke_width=0)
    grad.set_fill(color=[BG, BG, BG2], opacity=1).set_sheen_direction(UP)
    halo = glow(Dot(), VIOLET, radius=3.5, layers=8, opacity=0.06).shift(UP * 1.5)
    layers = VGroup()
    specs = [(n // 2, 0.015, 0.035, 0.35, 0.02), (n // 3, 0.035, 0.06, 0.55, 0.045),
             (n // 6, 0.06, 0.1, 0.8, 0.08)]
    for depth, (cnt, rmin, rmax, op, spd) in enumerate(specs):
        layer = VGroup()
        for _ in range(cnt):
            c = rng.choice(PALETTE + [INK, INK])
            x, y = rng.uniform(-w / 2, w / 2), rng.uniform(-h / 2, h / 2)
            layer.add(Dot([x, y, 0], radius=rng.uniform(rmin, rmax), color=c, fill_opacity=op))
        for _ in range(1 + depth):
            layer.add(sparkle(rng.uniform(0.07, 0.14), INK).set_opacity(op).move_to(
                [rng.uniform(-4.2, 4.2), rng.uniform(-7.5, 7.5), 0]))
        layer.add_updater(lambda m, dt, spd=spd: m.shift(UP * spd * dt))
        layers.add(layer)
    return VGroup(grad, halo, layers)


class ExplapixScene(MovingCameraScene):
    """Base: fondo vivo, subtítulos por segmento sincronizados con la voz y cámara."""

    timing_file = os.environ.get("EXPLAPIX_TIMING", "timing.json")
    show_captions = True
    show_backdrop = True

    def setup(self):
        super().setup()
        with open(self.timing_file, encoding="utf-8") as f:
            data = json.load(f)
        self.durations = [s["duration"] for s in data["segments"]]
        self.captions = [s["text"] for s in data["segments"]]
        self._caption = None
        self.bg = backdrop() if self.show_backdrop else VGroup()
        self.add(self.bg)

    # ----- cámara (staging) -----
    @property
    def frame(self):
        return self.camera.frame

    def focus(self, target, zoom: float = 1.5, run_time: float = 1.0, rate_func=EASE):
        """Acerca la cámara a algo para dirigir la mirada. Úsalo con self.play(...)."""
        p = target.get_center() if isinstance(target, Mobject) else np.array(target, dtype=float)
        return self.frame.animate(run_time=run_time, rate_func=rate_func).move_to(p).set(
            height=config.frame_height / zoom)

    def reset_camera(self, run_time: float = 0.9, rate_func=EASE):
        return self.frame.animate(run_time=run_time, rate_func=rate_func).move_to(ORIGIN).set(
            height=config.frame_height)

    def stage(self) -> list:
        """Todo lo que está en escena excepto fondo y subtítulos."""
        return [m for m in self.mobjects if isinstance(m, VMobject) and m is not self.bg
                and m is not self._caption and m is not self.frame]

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

    def outro(self):
        """Cierre de marca: logo con rebote (≈1 s)."""
        logo = VGroup(T("EXPLA", 84, INK), T("PIX", 84, SUN)).arrange(RIGHT, buff=0.06)
        sub = T("cómo funcionan las cosas", 30, MUTED, weight=NORMAL).next_to(logo, DOWN)
        c = self.frame.get_center() + UP * 0.5
        halo = glow(logo, VIOLET, radius=3.0, opacity=0.16).move_to(c)
        VGroup(logo, sub).move_to(c)
        self.play(FadeIn(halo, run_time=0.3), pop_in(logo, run_time=0.8, anchor=ORIGIN),
                  FadeIn(sub, shift=UP * 0.2, run_time=0.5))
        return VGroup(halo, logo, sub)

    # ----- subtítulos estilo reel: bloques cortos, texto con contorno, entrada con pop -----
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
            k = frame.height / config.frame_height                  # sigue a la cámara
            b = blocks[state["idx"]].copy().scale(s * k)
            m.become(VGroup(b.move_to(frame.get_center() + DOWN * 6.3 * k)))

        holder.add_updater(upd)
        upd(holder, 0)
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
