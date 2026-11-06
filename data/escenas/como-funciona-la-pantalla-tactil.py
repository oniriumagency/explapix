"""Día 2 — ¿Cómo sabe tu celular dónde lo tocas? (pantalla táctil capacitiva, kit v3)."""
import numpy as np
from explapix.kit import *  # noqa: F401,F403

SKIN = "#F2A27E"
PHONE = "#2B3080"


def make_phone():
    body = blob(5.0, 9.2, PHONE, r=0.7, floor_shadow=True).move_to([0, -0.2, 0])
    screen = RoundedRectangle(corner_radius=0.45, width=4.4, height=8.4, stroke_width=0,
                              fill_color="#0D1033", fill_opacity=1).move_to([0, -0.2, 0])
    notch = RoundedRectangle(corner_radius=0.1, width=1.1, height=0.22, stroke_width=0,
                             fill_color=PHONE, fill_opacity=1).move_to([0, 3.75, 0])
    f = face(1.6, "feliz", eye_color=INK).move_to([0, 1.8, 0])
    g = VGroup(body, screen, notch, f)
    g.face, g.screen = f, screen
    return g


def finger(angle=0.0):
    tipc = blob(1.0, 2.6, SKIN, r=0.48)
    nail = RoundedRectangle(corner_radius=0.18, width=0.6, height=0.55, stroke_width=0,
                            fill_color="#FFD9C9", fill_opacity=1).move_to(tipc.get_top() + DOWN * 0.45)
    g = VGroup(tipc, nail).rotate(angle)
    g.tip = lambda: tipc.get_critical_point(rotate_vector(DOWN, angle))
    return g


class Video(ExplapixScene):
    def construct(self):
        self.cam_sway(1.2, 7)
        title = title_text("¿Cómo sabe dónde\nlo tocas?", 58).move_to([0, 6.7, 0])
        phone = make_phone()

        # 0. Gancho
        with self.segment(0, mood="energia") as d:
            dust = particles("estrellas", [0, 0, 0], 8.5, 12, 22)
            self.add(dust)
            self.play(pop_in(title, anchor=ORIGIN, run_time=0.6))
            self.play(pop_in(phone, run_time=0.7))
            auto_blink(phone.face)
            f1 = finger().move_to([3.6, -5.0, 0])
            self.play(pop_in(f1, run_time=0.4))
            self.play(move_along_arc(f1, [0.9, -1.6, 0], angle=PI / 4, run_time=0.9))
            zap = particles("chispas", [0.9, -2.85, 0], 1, 1, 26)
            self.add(zap)
            lbl = pill("Tu dedo es parte del circuito", SUN, 28).move_to([0, 4.6, 0])
            self.play(pop_in(lbl, anchor=ORIGIN, run_time=0.45), jelly(phone, 0.06, run_time=0.6))
            idle_wiggle(lbl, 3, 1.2)

        # 1. La rejilla invisible
        with self.segment(1, mood="frio") as d:
            stop_idle(lbl)
            zap.clear_updaters()
            self.play(exit_out(lbl), exit_out(zap), move_along_arc(f1, [3.8, -6.0, 0], angle=-PI / 4),
                      phone.face.animate(run_time=0.4).set_opacity(0), run_time=0.6)
            self.remove(f1)
            self.cam_to([0, -0.2, 0], zoom=1.25, angle=-4, dur=1.2)
            xs, ys = np.linspace(-1.7, 1.7, 5), np.linspace(-3.4, 3.0, 8)
            rows = VGroup(*[Line([-2.0, y, 0], [2.0, y, 0], color=CYAN, stroke_width=5) for y in ys])
            cols = VGroup(*[Line([x, -3.8, 0], [x, 3.4, 0], color=VIOLET, stroke_width=5) for x in xs])
            self.play(LaggedStart(*[Create(r, rate_func=SNAP) for r in rows], lag_ratio=0.1, run_time=1.0))
            self.play(LaggedStart(*[Create(c, rate_func=SNAP) for c in cols], lag_ratio=0.1, run_time=0.8))
            grid_lbl = pill("Líneas transparentes", CYAN, 28).move_to([0, 4.6, 0])
            self.play(pop_in(grid_lbl, anchor=ORIGIN, run_time=0.45))
            idle_wiggle(grid_lbl, 3, 1.4)

        # 2. Cada cruce guarda carga
        with self.segment(2, mood="energia") as d:
            stop_idle(grid_lbl)
            nodes = VGroup(*[VGroup(Circle(0.2, fill_color=SUN, fill_opacity=0.25, stroke_width=0),
                                    Dot(radius=0.08, color=SUN)).move_to([x, y, 0])
                             for y in ys for x in xs])
            self.play(exit_out(grid_lbl, run_time=0.3),
                      LaggedStart(*[pop_in(n, anchor=ORIGIN, run_time=0.3) for n in nodes],
                                  lag_ratio=0.02, run_time=1.2))
            for n in nodes:
                idle_pulse(n, 0.12, np.random.uniform(0.6, 1.1))
            dep = pill("Mini depósitos de carga", SUN, 28).move_to([0, 4.6, 0])
            self.play(pop_in(dep, anchor=ORIGIN, run_time=0.45))
            idle_wiggle(dep, 3, 1.3)
            orb = particles("orbita", [0, -0.2, 0], 5, 9, 18)
            self.add(orb)

        # 3. El dedo roba carga
        with self.segment(3, mood="magia") as d:
            stop_idle(dep)
            self.play(exit_out(dep, run_time=0.3))
            target = np.array([xs[3], ys[2], 0])
            f2 = finger().move_to(target + UP * 1.35 + RIGHT * 0.05)
            f2.shift(RIGHT * 4)
            self.add(f2)
            self.play(anticipate_move(f2, target + UP * 1.35, run_time=0.9))
            near = [n for n in nodes if np.linalg.norm(n.get_center() - target) < 1.2]
            for n in near:
                stop_idle(n)
            steal = particles("chispas", target, 1, 1, 30, colors=[SUN, PINK])
            self.add(steal)
            self.play(*[n.animate(rate_func=EASE).set_opacity(0.12) for n in near], run_time=0.6)
            self.cam_to(target, zoom=1.7, angle=6, dur=1.0)
            rob = pill("¡Te llevas la carga!", PINK, 28, text_color=INK).move_to(target + UP * 3.0 + LEFT * 1.2)
            self.play(pop_in(rob, anchor=ORIGIN, run_time=0.45))
            idle_wiggle(rob, 4, 1.0)

        # 4. El chip escanea y calcula
        with self.segment(4, mood="energia") as d:
            stop_idle(rob)
            self.play(exit_out(rob, run_time=0.3))
            self.cam_reset(dur=0.9)
            bar = Rectangle(width=4.3, height=0.5, stroke_width=0, fill_color=CYAN, fill_opacity=0.35)
            bar.move_to([0, 3.4, 0])
            st = {"t": 0.0}

            def scan(m, dt):
                st["t"] = (st["t"] + dt * 1.6) % 1
                m.move_to([0, 3.4 - st["t"] * 7.2, 0])
            bar.add_updater(scan)
            self.add(bar)
            ring = Circle(0.55, stroke_color=CORAL, stroke_width=10).move_to(target)
            self.wait(0.8)
            self.play(pop_in(ring, anchor=ORIGIN, run_time=0.5))
            idle_pulse(ring, 0.15, 0.5)
            fast = pill("+100 veces por segundo", CYAN, 28).move_to([0, 4.6, 0])
            self.play(pop_in(fast, anchor=ORIGIN, run_time=0.45))
            idle_wiggle(fast, 3, 1.0)

        # 5. Varios dedos: zoom
        with self.segment(5, mood="sol") as d:
            stop_idle(fast, ring, *nodes)
            for m in (bar, steal, orb):
                m.clear_updaters()
            self.play(exit_out(fast), exit_out(ring), exit_out(bar), exit_out(steal), exit_out(f2),
                      exit_out(orb), *[exit_out(n) for n in nodes], run_time=0.5)
            sun = VGroup(ball(0.55, SUN), face(0.6, eye_color=BG)).move_to([0, -0.2, 0])
            self.play(pop_in(sun, anchor=ORIGIN, run_time=0.5))
            fa, fb = finger(0.5).move_to([-0.7, -1.1, 0]), finger(-0.5).move_to([0.7, 0.7, 0])
            self.play(cascade(fa, fb, lag=0.2, run_time=0.6))
            self.play(fa.animate(rate_func=EASE).shift(LEFT * 1.0 + DOWN * 1.2),
                      fb.animate(rate_func=EASE).shift(RIGHT * 1.0 + UP * 1.2),
                      sun.animate(rate_func=POP).scale(2.2), run_time=1.0)
            zoom = pill("Varios puntos a la vez", MINT, 28).move_to([0, 4.6, 0])
            self.play(pop_in(zoom, anchor=ORIGIN, run_time=0.45))
            alive(sun)
            idle_wiggle(zoom, 3, 1.2)

        # 6. Guantes + cierre
        with self.segment(6, mood="frio") as d:
            stop_idle(zoom, sun)
            self.play(exit_out(zoom), exit_out(sun), exit_out(fa), exit_out(fb), run_time=0.45)
            glove = VGroup(blob(1.3, 2.8, MUTED, r=0.55),
                           *[Line([-0.5, y, 0], [0.5, y, 0], color=shade(MUTED, -0.3), stroke_width=6)
                             for y in (-0.6, -0.2, 0.2)]).move_to([0.6, 0.3, 0])
            snow = particles("frio", [0, 2, 0], 8, 10, 24)
            self.add(snow)
            self.play(pop_in(glove, run_time=0.5))
            self.play(squash_bounce(glove, 0.4, run_time=0.7))
            sad = face(1.4, "serio", eye_color=INK).move_to([0, 2.6, 0])
            no = pill("La tela no conduce", PINK, 30, text_color=INK).move_to([0, 4.6, 0])
            self.play(pop_in(no, anchor=ORIGIN, run_time=0.45), FadeIn(sad, run_time=0.3))
            self.wait(0.4)
            self.clear_stage(run_time=0.6)
            self.outro()
