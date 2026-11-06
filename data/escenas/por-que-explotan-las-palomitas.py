"""Día 1 — ¿Por qué explotan las palomitas? (kit v3, estándar microondas)."""
import numpy as np
from explapix.kit import *  # noqa: F401,F403

CORN = "#F4B740"
CREAM = "#FFF1D0"


def kernel(scale=1.0, mood="feliz"):
    body = toon(Ellipse(width=1.7 * scale, height=2.1 * scale), CORN)
    tip = Polygon([-0.35 * scale, -0.75 * scale, 0], [0.35 * scale, -0.75 * scale, 0],
                  [0, -1.25 * scale, 0], fill_color=shade(CORN, -0.25), fill_opacity=1,
                  stroke_width=0)
    f = face(1.0 * scale, mood, eye_color=BG).move_to(UP * 0.15 * scale)
    g = VGroup(tip, body, f)
    g.face = f
    return g


def popcorn(scale=1.0):
    rng = np.random.default_rng(3)
    puffs = VGroup(*[ball(r * scale, c) for r, c in
                     [(0.62, CREAM), (0.5, INK), (0.55, CREAM), (0.45, INK), (0.5, CREAM), (0.4, INK)]])
    offs = [(0, 0), (-0.6, 0.35), (0.6, 0.3), (-0.35, -0.45), (0.45, -0.4), (0.05, 0.7)]
    for p, (x, y) in zip(puffs, offs):
        p.move_to(np.array([x, y, 0]) * scale + rng.uniform(-0.05, 0.05, 3) * [1, 1, 0])
    f = face(0.8 * scale, "feliz", eye_color=BG).move_to(UP * 0.05 * scale)
    g = VGroup(puffs, f)
    g.face = f
    return g


class Video(ExplapixScene):
    def construct(self):
        self.cam_sway(1.2, 7)
        title = title_text("¿Por qué explotan\nlas palomitas?", 58).move_to([0, 6.6, 0])
        k = kernel(1.5).move_to([0, 0.6, 0])

        # 0. Gancho
        with self.segment(0, mood="energia") as d:
            stars = particles("estrellas", [0, 0.8, 0], 8.5, 9, 24)
            self.add(stars)
            self.play(pop_in(title, anchor=ORIGIN, run_time=0.6))
            self.play(pop_in(k, run_time=0.7))
            auto_blink(k.face)
            olla = pill("Mini olla de presión", CORAL, 32).move_to([0, 3.9, 0])
            self.play(pop_in(olla, anchor=ORIGIN, run_time=0.45))
            idle_wiggle(olla, 4, 1.2)
            self.play(Rotate(k, TAU, rate_func=anticipate_overshoot, run_time=1.0))
            self.play(squash_bounce(k, 0.5, run_time=0.8))

        # 1. Por dentro: cáscara, almidón, agua
        with self.segment(1, mood="noche") as d:
            stop_idle(olla)
            self.play(exit_out(olla, run_time=0.35))
            self.cam_to(k, zoom=1.35, angle=-5, dur=1.2)
            shell = k[1]
            starch = toon(Ellipse(width=1.9, height=2.4), CREAM).move_to(k[1])
            drop = VGroup(ball(0.32, CYAN), face(0.42, eye_color=BG)).move_to(k[1].get_center() + DOWN * 0.55)
            self.play(shell.animate(rate_func=EASE, run_time=0.6).set_opacity(0.35),
                      k.face.animate(run_time=0.4).set_opacity(0))
            self.play(pop_in(starch, anchor=ORIGIN, run_time=0.6))
            self.remove(k, starch)
            ks = VGroup(k, starch)
            self.add(ks)
            self.play(pop_in(drop, anchor=ORIGIN, run_time=0.5))
            idle_float(drop, 0.06, 1.4)
            labels = VGroup(pill("Cáscara dura", CORN, 26).move_to([2.6, 2.9, 0]),
                            pill("Almidón", CREAM, 26).move_to([-2.6, 1.8, 0]),
                            pill("Agua", CYAN, 26).move_to([2.6, -1.6, 0]))
            self.play(cascade(*labels, anim=lambda m: pop_in(m, anchor=ORIGIN, run_time=0.4),
                              lag=0.25, run_time=0.9))
            for lb in labels:
                idle_wiggle(lb, 3, 1.5)

        # 2. Calor: el agua se vuelve vapor
        with self.segment(2, mood="calor") as d:
            stop_idle(drop, *labels)
            self.play(LaggedStart(*[exit_out(lb) for lb in labels], lag_ratio=0.1, run_time=0.45))
            self.cam_reset(dur=1.0)
            flames = VGroup(*[VGroup(Triangle(fill_color=CORAL, fill_opacity=1, stroke_width=0).scale(0.55),
                                     Triangle(fill_color=SUN, fill_opacity=1, stroke_width=0).scale(0.28)
                                     .shift(DOWN * 0.12)).move_to([x, -2.7, 0]) for x in (-1.4, 0, 1.4)])
            self.play(cascade(*flames, lag=0.15, run_time=0.6))
            for f in flames:
                idle_wiggle(f, 8, 0.5)
            heat = particles("calor", [0, -1.4, 0], 4, 3.5, 26)
            self.add(heat)
            self.play(exit_out(drop, run_time=0.4))
            steam = particles("burbujas", k[1].get_center(), 1.6, 2.0, 18, colors=[INK, CYAN], size=0.8)
            self.add(steam)
            vap = pill("¡Vapor atrapado!", CORAL, 30).move_to([0, 3.9, 0])
            self.play(pop_in(vap, anchor=ORIGIN, run_time=0.45), jelly(ks, 0.12, run_time=0.8))
            idle_wiggle(vap, 4, 0.9)

        # 3. La presión sube 9 veces
        with self.segment(3, mood="magia") as d:
            stop_idle(vap)
            self.play(exit_out(vap, run_time=0.3))
            dial = VGroup(Circle(0.9, fill_color="#1B1F55", fill_opacity=1, stroke_color=INK, stroke_width=6),
                          *[Line(ORIGIN, UP * 0.18, color=INK, stroke_width=4).shift(UP * 0.7)
                            .rotate(a, about_point=ORIGIN) for a in np.linspace(2.2, -2.2, 10)])
            needle = Line(ORIGIN, UP * 0.7, color=CORAL, stroke_width=8)
            needle.rotate(2.2, about_point=ORIGIN)
            gauge = VGroup(dial, needle, Dot(radius=0.08, color=INK)).move_to([2.9, 3.4, 0])
            self.play(pop_in(gauge, anchor=ORIGIN, run_time=0.5))
            self.cam_to([1.2, 1.6, 0], zoom=1.2, angle=4, dur=1.4)
            self.play(Rotate(needle, -4.4, about_point=gauge[0][0].get_center(), rate_func=EASE),
                      ks.animate(rate_func=EASE).scale(1.18), run_time=1.4)
            x9 = pill("9× la presión del aire", PINK, 28, text_color=INK).move_to([0, 4.6, 0])
            self.play(pop_in(x9, anchor=ORIGIN, run_time=0.45), jelly(ks, 0.2, run_time=0.8))
            idle_pulse(gauge, 0.04, 0.4)

        # 4. ¡POP!
        with self.segment(4, mood="energia") as d:
            stop_idle(gauge)
            temp = pill("~180 °C", CORAL, 32).move_to([-2.4, 3.4, 0])
            self.play(pop_in(temp, anchor=ORIGIN, run_time=0.4), exit_out(x9, run_time=0.4))
            for a in (6, -6, 4, 0):
                self.cam_to(angle=a, dur=0.15)
                self.play(emphasize(ks, 1.08, run_time=0.18))
            steam.clear_updaters()
            self.play(exit_out(ks, run_time=0.3), FadeOut(steam, run_time=0.2))
            boom = particles("chispas", [0, 0.8, 0], 1, 1, 50, size=1.6)
            flakes = particles("confeti", [0, 3.0, 0], 7, 8, 30, colors=[INK, CREAM, SUN])
            self.add(boom, flakes)
            pc = popcorn(1.4).move_to([0, 0.8, 0])
            pop = T("¡POP!", 90, SUN).move_to([0, 3.6, 0])
            self.play(pop_in(pc, anchor=ORIGIN, run_time=0.7), pop_in(pop, anchor=ORIGIN, run_time=0.6))
            auto_blink(pc.face)
            idle_wiggle(pop, 6, 0.6)
            self.cam_reset(dur=0.6)

        # 5. Se enfría y queda enorme
        with self.segment(5, mood="sol") as d:
            stop_idle(pop, pc.face)
            for m in (boom, flakes):
                m.clear_updaters()
            self.play(exit_out(pop), exit_out(temp), exit_out(gauge), exit_out(boom), FadeOut(flakes),
                      run_time=0.45)
            small = kernel(0.35).move_to([-2.6, -1.6, 0])
            self.play(pc.animate(rate_func=POP, run_time=0.9).scale(1.45).move_to([0.8, 0.9, 0]),
                      pop_in(small, run_time=0.6))
            auto_blink(pc.face)
            x40 = pill("¡Hasta 40× más grande!", SUN, 30).move_to([0, 4.6, 0])
            crunchy = pill("Crujiente", CREAM, 28).move_to([2.4, -2.2, 0])
            self.play(cascade(x40, crunchy, anim=lambda m: pop_in(m, anchor=ORIGIN, run_time=0.45),
                              lag=0.3, run_time=0.8))
            alive(pc)
            idle_wiggle(x40, 3, 1.1)
            sparkles = particles("estrellas", pc.get_center(), 4.5, 4.5, 14)
            self.add(sparkles)

        # 6. Grano seco + cierre
        with self.segment(6, mood="noche") as d:
            stop_idle(pc, x40, pc.face)
            for m in (heat, sparkles, *flames):
                m.clear_updaters()
            self.play(exit_out(pc), exit_out(x40), exit_out(crunchy), exit_out(small), exit_out(heat),
                      exit_out(sparkles), *[exit_out(f) for f in flames], run_time=0.5)
            dry = kernel(1.1, "serio").move_to([0, 0.8, 0])
            self.play(pop_in(dry, run_time=0.6))
            seco = pill("Muy seco = no truena", MUTED, 30, text_color=INK).move_to([0, 3.4, 0])
            self.play(pop_in(seco, anchor=ORIGIN, run_time=0.45), jelly(dry, 0.1, run_time=0.6))
            self.wait(0.5)
            self.clear_stage(run_time=0.6)
            self.outro()
