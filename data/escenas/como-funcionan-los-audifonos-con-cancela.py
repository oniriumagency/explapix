"""Día 3 — Audífonos con cancelación de ruido (interferencia destructiva, kit v3)."""
import numpy as np
from explapix.kit import *  # noqa: F401,F403

CUP = "#3D46B8"


def wave(y, x0, x1, phase, amp=0.45, k=3.0, color=SUN, width=8):
    xs = np.linspace(x0, x1, 80)
    pts = [np.array([x, y + amp * np.sin(k * x - phase), 0]) for x in xs]
    return VMobject(stroke_color=color, stroke_width=width).set_points_smoothly(pts)


def make_headphones():
    band = Arc(radius=2.0, start_angle=0.15, angle=PI - 0.3, color=shade(CUP, 0.2), stroke_width=26)
    cups = VGroup(*[blob(1.2, 1.9, CUP, r=0.5).move_to([x, -0.2, 0]) for x in (-2.0, 2.0)])
    pads = VGroup(*[RoundedRectangle(corner_radius=0.2, width=0.35, height=1.5, stroke_width=0,
                                     fill_color=VIOLET, fill_opacity=1).move_to([x, -0.2, 0])
                    for x in (-1.35, 1.35)])
    f = face(1.3, "feliz", eye_color=INK).move_to([0, 0.4, 0])
    g = VGroup(band, pads, cups, f)
    g.face, g.cups = f, cups
    return g


class Video(ExplapixScene):
    def construct(self):
        self.cam_sway(1.2, 7)
        title = title_text("Audífonos que borran\nruido con ruido", 54).move_to([0, 6.7, 0])
        hp = make_headphones().move_to([0, 1.2, 0])

        # 0. Gancho
        with self.segment(0, mood="energia") as d:
            stars = particles("estrellas", [0, 0.5, 0], 8.5, 10, 20)
            self.add(stars)
            self.play(pop_in(title, anchor=ORIGIN, run_time=0.6))
            self.play(pop_in(hp, run_time=0.7))
            auto_blink(hp.face)
            noise = VGroup(*[VMobject(stroke_color=c, stroke_width=6).set_points_as_corners(
                [np.array([x0 + 0.25 * i, y + (0.35 if i % 2 else -0.35), 0]) for i in range(7)])
                for x0, y, c in ((-4.0, 3.6, CORAL), (2.4, 3.4, PINK), (-4.0, -1.8, SUN), (2.4, -2.0, CORAL))])
            self.play(cascade(*noise, anim=lambda m: pop_in(m, anchor=ORIGIN, run_time=0.35), lag=0.1,
                              run_time=0.6))
            for nz in noise:
                idle_wiggle(nz, 10, 0.35)
            lbl = pill("Ruido + ruido = silencio", MINT, 30).move_to([0, -4.0, 0])
            self.play(pop_in(lbl, anchor=ORIGIN, run_time=0.45), jelly(hp, 0.08, run_time=0.6))
            idle_wiggle(lbl, 3, 1.2)

        # 1. El sonido es una onda de presión
        with self.segment(1, mood="noche") as d:
            stop_idle(lbl, *noise, hp.face)
            self.play(exit_out(lbl), *[exit_out(n) for n in noise],
                      hp.animate(rate_func=EASE).scale(0.55).move_to([0, 3.9, 0]), run_time=0.6)
            auto_blink(hp.face)
            st = {"ph": 0.0}
            w1 = wave(0.4, -4.0, 4.0, 0)

            def run1(m, dt):
                st["ph"] += dt * 5
                m.become(wave(0.4, -4.0, 4.0, st["ph"]))
            w1.add_updater(run1)
            air = VGroup(*[Dot(radius=0.07, color=INK).move_to([x, -2.0 + 0.35 * (j - 1), 0])
                           for x in np.linspace(-3.8, 3.8, 22) for j in range(3)])
            base = [d_.get_center().copy() for d_ in air]

            def squeeze(m, dt):
                for d_, b in zip(m, base):
                    d_.move_to(b + RIGHT * 0.22 * np.sin(3.0 * b[0] - st["ph"]))
            air.add_updater(squeeze)
            self.play(Create(w1, run_time=0.8), FadeIn(air, run_time=0.6))
            pres = pill("El aire se aprieta y se afloja", SUN, 26).move_to([0, -4.0, 0])
            self.play(pop_in(pres, anchor=ORIGIN, run_time=0.45))
            idle_wiggle(pres, 3, 1.3)

        # 2. El micrófono escucha (avión)
        with self.segment(2, mood="energia") as d:
            stop_idle(pres)
            air.clear_updaters()
            self.play(exit_out(pres), exit_out(air), run_time=0.4)
            plane = VGroup(blob(2.2, 0.7, INK, r=0.3),
                           Polygon([-0.2, 0, 0], [0.5, 0, 0], [-0.4, 1.0, 0], fill_color=MUTED, fill_opacity=1,
                                   stroke_width=0).shift(DOWN * 0.1),
                           Polygon([-1.1, 0.1, 0], [-0.7, 0.1, 0], [-1.2, 0.7, 0], fill_color=MUTED,
                                   fill_opacity=1, stroke_width=0)).move_to([-2.6, -2.6, 0])
            mic = VGroup(ball(0.35, CYAN), face(0.45, eye_color=BG)).move_to([2.6, 1.6, 0])
            self.play(pop_in(plane, run_time=0.5), pop_in(mic, anchor=ORIGIN, run_time=0.5))
            idle_float(plane, 0.12, 1.4)
            hum = particles("polvo", plane.get_center(), 2.5, 1.5, 20, colors=[SUN, CORAL], follow=plane)
            self.add(hum)
            self.cam_to(mic, zoom=1.5, angle=-6, dur=1.2)
            mlbl = pill("Micrófono", CYAN, 28).next_to(mic, DOWN, buff=0.3)
            self.play(pop_in(mlbl, anchor=ORIGIN, run_time=0.4), emphasize(mic, 1.3, run_time=0.6))
            idle_pulse(mic, 0.1, 0.4)

        # 3. El chip crea la onda contraria
        with self.segment(3, mood="magia") as d:
            stop_idle(mic)
            self.cam_reset(dur=1.0)
            chip = VGroup(blob(1.2, 1.2, VIOLET, r=0.2),
                          *[Line([x, 0.75, 0], [x, -0.75, 0], color=MUTED, stroke_width=5).set_z_index(-1)
                            for x in (-0.35, 0, 0.35)]).move_to([2.6, -1.4, 0])
            self.play(exit_out(mlbl, run_time=0.3), pop_in(chip, run_time=0.5))
            spark = particles("chispas", chip.get_center(), 1, 1, 22, follow=chip)
            self.add(spark)
            w2 = wave(-1.0, -4.0, 4.0, PI, color=PINK)

            def run2(m, dt):
                m.become(wave(-1.0, -4.0, 4.0, st["ph"] + PI, color=PINK))
            w2.add_updater(run2)
            self.play(Create(w2, run_time=0.9))
            inv = pill("La onda al revés", PINK, 28, text_color=INK).move_to([-1.8, -2.6, 0])
            self.play(pop_in(inv, anchor=ORIGIN, run_time=0.45))
            idle_wiggle(inv, 3, 1.0)

        # 4. Se suman y se anulan
        with self.segment(4, mood="frio") as d:
            stop_idle(inv, plane)
            for m in (spark, hum):
                m.clear_updaters()
            self.play(exit_out(inv), exit_out(chip), exit_out(spark), exit_out(plane), exit_out(hum),
                      exit_out(mic), run_time=0.45)
            mix = {"a": 0.0}
            w1.clear_updaters()
            w2.clear_updaters()

            def merge1(m, dt):
                st["ph"] += dt * 5
                m.become(wave(0.4 - 0.7 * mix["a"], -4.0, 4.0, st["ph"], amp=0.45 * (1 - mix["a"])))

            def merge2(m, dt):
                m.become(wave(-1.0 + 0.7 * mix["a"], -4.0, 4.0, st["ph"] + PI, amp=0.45 * (1 - mix["a"]),
                              color=PINK))
            w1.add_updater(merge1)
            w2.add_updater(merge2)
            self.tween(lambda a: mix.__setitem__("a", a), 1.6, EASE)
            self.wait(1.6)
            flat = Line([-4.0, -0.3, 0], [4.0, -0.3, 0], color=MINT, stroke_width=10)
            self.play(FadeIn(flat, run_time=0.3))
            calm = particles("burbujas", [0, -0.3, 0], 8, 3, 14, colors=[MINT, INK])
            self.add(calm)
            dest = pill("Interferencia destructiva", MINT, 28).move_to([0, -3.6, 0])
            self.play(pop_in(dest, anchor=ORIGIN, run_time=0.45), emphasize(hp, 1.15, run_time=0.6))
            idle_wiggle(dest, 3, 1.3)

        # 5. Graves sí, agudos menos
        with self.segment(5, mood="calor") as d:
            stop_idle(dest)
            for m in (w1, w2, calm):
                m.clear_updaters()
            self.play(exit_out(w1), exit_out(w2), exit_out(flat), exit_out(calm), exit_out(dest),
                      run_time=0.4)
            low = wave(1.2, -3.8, 3.8, 0, amp=0.5, k=1.6, color=SUN)
            high = wave(-2.0, -3.8, 3.8, 0, amp=0.3, k=9.0, color=CORAL, width=6)
            self.play(Create(low, run_time=0.6), Create(high, run_time=0.6))
            ok = pill("Graves constantes: ✓", MINT, 28).move_to([0, 2.5, 0])
            meh = pill("Agudos y golpes: menos", CORAL, 28).move_to([0, -0.7, 0])
            self.play(cascade(ok, meh, anim=lambda m: pop_in(m, anchor=ORIGIN, run_time=0.45), lag=0.4,
                              run_time=0.9))
            self.play(low.animate(rate_func=EASE, run_time=0.8).set_stroke(opacity=0.15),
                      jelly(high, 0.2, anchor=ORIGIN, run_time=0.8))
            idle_wiggle(ok, 3, 1.2)
            idle_wiggle(meh, 3, 1.0)

        # 6. Silencio + cierre
        with self.segment(6, mood="noche") as d:
            stop_idle(ok, meh)
            self.play(exit_out(low), exit_out(high), exit_out(ok), exit_out(meh),
                      hp.animate(rate_func=EASE).scale(1.5).move_to([0, 1.0, 0]), run_time=0.6)
            zz = particles("estrellas", [1.8, 3.4, 0], 2.5, 2, 10)
            self.add(zz)
            alive(hp)
            quiet = pill("Silencio hecho con física", VIOLET, 30, text_color=INK).move_to([0, -2.6, 0])
            self.play(pop_in(quiet, anchor=ORIGIN, run_time=0.45))
            self.wait(0.6)
            self.clear_stage(run_time=0.6)
            self.outro()
