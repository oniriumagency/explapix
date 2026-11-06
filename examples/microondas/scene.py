"""Ejemplo kit v3 (Factos Didácticos): ¿Cómo calienta la comida un microondas?

Muestra lo dinámico del kit v3: mood() cambia el color del fondo por segmento, cam_to() mueve,
acerca y gira la cámara en paralelo, cam_sway() la balancea suave, particles() (chispas, calor,
estrellas, burbujas, confeti) y vida constante en cada elemento (alive, idle_wiggle, idle_spin).
"""
import numpy as np
from explapix.kit import *  # noqa: F401,F403

OVEN = "#4F5BD5"


def water(scale=1.0, mood="feliz", charges=False):
    """Molécula de agua: O grande + 2 H a 104,5° (con carita y cargas opcionales)."""
    o = VGroup(ball(0.9 * scale, CORAL), face(1.0 * scale, mood, eye_color=BG))
    hs = VGroup()
    for sgn in (-1, 1):
        ang = -PI / 2 + sgn * np.deg2rad(104.5 / 2)
        hs.add(ball(0.5 * scale, INK).move_to(rotate_vector(RIGHT * 1.15 * scale, ang)))
    m = VGroup(hs, o)
    if charges:
        neg = VGroup(Circle(0.28 * scale, fill_color=BLUE, fill_opacity=1, stroke_width=0),
                     T("−", 40 * scale, INK)).move_to(UP * 1.25 * scale)
        pos = VGroup(*[VGroup(Circle(0.24 * scale, fill_color=PINK, fill_opacity=1, stroke_width=0),
                              T("+", 34 * scale, INK)).move_to(h.get_center() * 1.55)
                       for h in hs])
        m.charges = VGroup(neg, pos)
    return m


def make_oven():
    body = blob(7.4, 5.0, OVEN, r=0.55, floor_shadow=True).move_to([0, 0.6, 0])
    window = RoundedRectangle(corner_radius=0.35, width=4.6, height=3.8, stroke_width=0,
                              fill_color="#10143F", fill_opacity=1).move_to([-1.0, 0.6, 0])
    shine = Line([-3.0, 2.2, 0], [-2.2, 2.2, 0], color=INK, stroke_width=6).set_opacity(0.35)
    plate = Ellipse(width=3.6, height=0.55, fill_color=MUTED, fill_opacity=1,
                    stroke_width=0).move_to([-1.0, -0.95, 0])
    bowl = VGroup(blob(1.7, 0.85, CORAL, r=0.35),
                  face(0.6, eye_color=BG).move_to(UP * 0.02)).move_to([-1.0, -0.35, 0])
    oven_face = face(1.3, "feliz", eye_color=INK).move_to([2.55, 2.1, 0])
    dial = VGroup(ball(0.42, SUN), Line(ORIGIN, UP * 0.3, color=BG, stroke_width=6))
    dial.move_to([2.55, 0.65, 0])
    buttons = VGroup(*[blob(0.95, 0.32, c, r=0.12) for c in (MINT, PINK)]).arrange(
        DOWN, buff=0.22).move_to([2.55, -0.6, 0])
    oven = VGroup(body, window, shine, plate, bowl, oven_face, dial, buttons)
    oven.bowl, oven.face, oven.dial = bowl, oven_face, dial
    return oven


def wave_curve(y, x0, x1, phase, amp=0.18, k=5.0, color=SUN):
    xs = np.linspace(x0, x1, 60)
    pts = [np.array([x, y + amp * np.sin(k * x - phase), 0]) for x in xs]
    return VMobject(stroke_color=color, stroke_width=7).set_points_smoothly(pts)


class Video(ExplapixScene):
    def construct(self):
        self.cam_sway(1.2, 7)

        # ---------- Personaje: el microondas ----------
        oven = make_oven()
        oven_face, dial = oven.face, oven.dial
        title = title_text("¿Cómo calienta\nel microondas?", 60).move_to([0, 6.6, 0])

        # ---------- 0. Gancho: no es fuego, es baile ----------
        with self.segment(0, mood="energia") as d:
            stars = particles("estrellas", [0, 1.0, 0], 8.5, 9, 22)
            self.add(stars)
            self.play(pop_in(title, anchor=ORIGIN, run_time=0.6))
            self.play(pop_in(oven, run_time=0.7))
            auto_blink(oven_face)
            idle_wiggle(dial, deg=8, period=1.2)
            flame = VGroup(Triangle(fill_color=CORAL, fill_opacity=1, stroke_width=0).scale(0.7),
                           Triangle(fill_color=SUN, fill_opacity=1, stroke_width=0).scale(0.38)
                           .shift(DOWN * 0.15)).move_to([-1.0, 4.4, 0])
            cross = VGroup(Line(UL, DR), Line(UR, DL)).scale(0.75).set_stroke(PINK, 14).move_to(flame)
            self.play(pop_in(flame, run_time=0.45))
            self.play(Create(cross, rate_func=SNAP, run_time=0.3), jelly(flame, run_time=0.5))
            self.play(exit_out(flame), exit_out(cross))
            dancers = VGroup(*[water(0.32) for _ in range(3)]).arrange(RIGHT, buff=0.45)
            dancers.move_to([0, -3.4, 0])
            self.play(cascade(*dancers, lag=0.15, run_time=0.7))
            for k, m in enumerate(dancers):
                idle_wiggle(m, deg=25, period=0.5 + 0.1 * k)
                idle_float(m, amp=0.12, period=0.9 + 0.2 * k)
            sparks = particles("chispas", dancers.get_center(), 1, 1, 26)
            self.add(sparks)
            dance = pill("¡A bailar!", SUN, 34).move_to([1.6, 4.4, 0])
            self.play(pop_in(dance, anchor=ORIGIN, run_time=0.5))
            idle_wiggle(dance, deg=5, period=1.0)

        # ---------- 1. Magnetrón ----------
        with self.segment(1, mood="magia") as d:
            stop_idle(dance, *dancers)
            sparks.clear_updaters()
            self.play(exit_out(dance), *[exit_out(m) for m in dancers], exit_out(sparks),
                      run_time=0.5)
            mag = VGroup(blob(1.5, 1.2, VIOLET, r=0.35), face(0.8, "serio", eye_color=INK))
            mag.move_to([2.55, -3.0, 0])
            self.cam_to([1.6, -2.0, 0], zoom=1.6, angle=-7, dur=1.3)
            cable = tube([(4.2, -4.6), (3.6, -4.6), (3.6, -3.0), (3.3, -3.0)], MUTED, width=12)
            self.play(draw_in(cable, run_time=0.6), pop_in(mag, run_time=0.7))
            elec = flow_dots(cable.path, n=8, color=SUN, radius=0.07, speed=0.6)
            zap = particles("chispas", mag.get_center(), 1, 1, 30, follow=mag)
            self.add(elec, zap)
            idle_pulse(mag, amp=0.06, period=0.5)
            m_lbl = pill("Magnetrón", VIOLET, 30, text_color=INK).move_to([1.6, -1.6, 0])
            self.play(pop_in(m_lbl, anchor=ORIGIN, run_time=0.45))
            wifi = VGroup(*[Arc(radius=0.25 + 0.25 * k, start_angle=PI / 4, angle=PI / 2,
                                color=CYAN, stroke_width=9) for k in range(3)],
                          Dot(radius=0.09, color=CYAN)).move_to([0.2, -3.0, 0])
            wifi[-1].move_to(wifi[0].get_arc_center())
            self.play(cascade(*wifi, anim=lambda m: pop_in(m, anchor=ORIGIN, run_time=0.4),
                              lag=0.2, run_time=0.8))
            w_lbl = pill("Como el wifi", CYAN, 28).next_to(wifi, DOWN, buff=0.25)
            self.play(pop_in(w_lbl, anchor=ORIGIN, run_time=0.4), emphasize(mag, 1.2, run_time=0.6))
            self.cam_reset(dur=1.1)

        # ---------- 2. Ondas que rebotan ----------
        with self.segment(2, mood="energia") as d:
            self.play(exit_out(m_lbl), exit_out(wifi), exit_out(w_lbl), run_time=0.4)
            guide = tube([(2.55, -2.3), (2.55, -1.8), (1.4, -1.8), (1.4, 1.6), (1.3, 1.6)],
                         SUN, width=10)
            self.play(draw_in(guide, run_time=0.6))
            st = {"ph": 0.0}
            waves = VGroup(*[wave_curve(y, -3.1, 1.1, 0) for y in (1.9, 1.1, 0.3)])

            def run_waves(m, dt):
                st["ph"] += dt * 9
                for k, (y, c) in enumerate(((1.9, SUN), (1.1, CYAN), (0.3, PINK))):
                    m[k].become(wave_curve(y, -3.1, 1.1, st["ph"] * (1 if k % 2 == 0 else -1),
                                           color=c))
            waves.add_updater(run_waves)
            self.play(FadeIn(waves, run_time=0.4))
            hits = VGroup(*[sparkle(0.3, INK).move_to([x, y, 0]) for y in (1.9, 1.1, 0.3)
                            for x in (-3.2, 1.2)])
            self.play(LaggedStart(*[Succession(pop_in(h, anchor=ORIGIN, run_time=0.3),
                                               exit_out(h, run_time=0.3)) for h in hits],
                                  lag_ratio=0.15, run_time=1.5))
            b_lbl = pill("Rebotan en el metal", SUN, 30).move_to([-0.6, 4.4, 0])
            self.play(pop_in(b_lbl, anchor=ORIGIN, run_time=0.45))
            idle_wiggle(b_lbl, deg=3, period=1.3)
            self.cam_to(angle=4, zoom=1.08, dur=1.5)

        # ---------- 3. La molécula de agua ----------
        with self.segment(3, mood="frio") as d:
            stop_idle(b_lbl, oven_face, dial)
            for m in (waves, elec, zap, mag):
                m.clear_updaters()
            gone = [oven, waves, guide, cable, elec, zap, mag, b_lbl, stars]
            for m in gone:
                m.clear_updaters()
            self.play(LaggedStart(*[exit_out(m) for m in gone], lag_ratio=0.05, run_time=0.7))
            self.cam_reset(dur=0.9)
            big = water(1.25, "feliz", charges=True).move_to([0, 0.6, 0])
            beam = rays([0, 0.6, 0], CYAN, n=16, length=8, opacity=0.12)
            bubbles = particles("burbujas", [0, -1.0, 0], 8, 9, 22)
            self.add(beam, bubbles)
            self.bring_to_back(beam)
            self.bring_to_back(self.bg)
            self.play(pop_in(big, run_time=0.8), FadeIn(beam, run_time=0.5))
            idle_spin(beam, 0.03)
            ch = big.charges
            self.play(cascade(ch[0], *ch[1], anim=lambda m: pop_in(m, anchor=ORIGIN, run_time=0.45),
                              lag=0.2, run_time=0.9))
            self.remove(big, ch[0], *ch[1])
            big = VGroup(big, ch)
            self.add(big)
            auto_blink(big[0][1][1])
            self.play(jelly(big, run_time=0.6))
            c_lbl = pill("Una punta + y otra −", CYAN, 30).move_to([0, 4.4, 0])
            self.play(pop_in(c_lbl, anchor=ORIGIN, run_time=0.45))
            alive(big, "float")

        # ---------- 4. El campo cambia y las moléculas giran ----------
        with self.segment(4, mood="magia") as d:
            stop_idle(big)
            self.play(exit_out(c_lbl, run_time=0.3),
                      big.animate(rate_func=EASE, run_time=0.6).scale(0.75).move_to([0, 1.3, 0]))
            field = Arrow([-3.4, -2.2, 0], [3.4, -2.2, 0], color=SUN, stroke_width=14, buff=0,
                          max_tip_length_to_length_ratio=0.12)
            f_lbl = T("campo", 30, SUN).next_to(field, DOWN, buff=0.15)
            minis = VGroup(*[water(0.3) for _ in range(4)]).arrange(RIGHT, buff=1.1).move_to([0, -3.7, 0])
            self.play(GrowArrow(field, run_time=0.5), FadeIn(f_lbl, run_time=0.4),
                      cascade(*minis, lag=0.12, run_time=0.7))
            for k in range(4):
                self.cam_to(angle=5 if k % 2 == 0 else -5, dur=0.55)
                self.play(Rotate(field, PI, about_point=field.get_center()),
                          Rotate(big, PI), *[Rotate(m, PI) for m in minis],
                          run_time=0.55, rate_func=anticipate_overshoot)
            rate = pill("¡~5.000 millones por segundo!", PINK, 28, text_color=INK).move_to([0, 4.5, 0])
            self.play(pop_in(rate, anchor=ORIGIN, run_time=0.45))
            self.play(emphasize(rate, 1.2, run_time=0.6))
            self.cam_reset(dur=0.8)
            spin_dirs = [0.9, -1.1, 1.3, -0.8]
            for m, sp in zip(minis, spin_dirs):
                idle_spin(m, sp)

        # ---------- 5. Choques = calor ----------
        with self.segment(5, mood="calor") as d:
            for m in minis:
                stop_idle(m)
            beam.clear_updaters()
            bubbles.clear_updaters()
            self.play(exit_out(field), exit_out(f_lbl), exit_out(rate), exit_out(big),
                      exit_out(beam), FadeOut(bubbles), *[exit_out(m) for m in minis],
                      run_time=0.45)
            rng = np.random.default_rng(4)
            crowd = VGroup(*[water(0.28).rotate(rng.uniform(0, TAU)).move_to(
                [rng.uniform(-3.2, 1.8), rng.uniform(-3.8, 3.2), 0]) for _ in range(14)])
            self.play(cascade(*crowd, lag=0.05, run_time=0.8))
            jit = {"t": 0.0}
            vel = rng.uniform(-1, 1, (len(crowd), 2)) * 2.2

            def jitter(g, dt):
                jit["t"] += dt
                for i, m in enumerate(g):
                    p = m.get_center()
                    for ax, lo, hi in ((0, -3.4, 2.0), (1, -4.0, 3.4)):
                        if not lo < p[ax] < hi:
                            vel[i][ax] = -np.sign(p[ax] - (lo + hi) / 2) * abs(vel[i][ax])
                    m.shift(np.array([*vel[i], 0]) * dt)
                    m.rotate(dt * 6 * (1 if i % 2 else -1))
            crowd.add_updater(jitter)
            heat = particles("calor", [-0.7, -0.3, 0], 6, 8, 36)
            self.add(heat)
            thermo_tube = RoundedRectangle(corner_radius=0.25, width=0.5, height=5.0, stroke_width=0,
                                           fill_color="#2A1530", fill_opacity=1).move_to([3.5, 0.0, 0])
            bulb = ball(0.5, CORAL).move_to([3.5, -2.7, 0])
            level = Rectangle(width=0.3, height=0.6, stroke_width=0, fill_color=CORAL,
                              fill_opacity=1).move_to([3.5, -2.2, 0], aligned_edge=DOWN)
            self.play(pop_in(VGroup(thermo_tube, level, bulb), run_time=0.5))
            self.play(level.animate(rate_func=EASE, run_time=1.3).stretch_to_fit_height(4.3,
                      about_edge=DOWN), jelly(bulb, run_time=0.8))
            h_lbl = pill("Agitación = calor", CORAL, 30).move_to([-0.6, 4.6, 0])
            self.play(pop_in(h_lbl, anchor=ORIGIN, run_time=0.45))
            idle_wiggle(h_lbl, deg=4, period=0.9)

        # ---------- 6. El plato gira + cierre ----------
        with self.segment(6, mood="energia") as d:
            crowd.clear_updaters()
            stop_idle(h_lbl)
            self.play(LaggedStart(*[exit_out(m) for m in [*crowd, heat, thermo_tube, level, bulb,
                                                          h_lbl]], lag_ratio=0.03, run_time=0.5))
            oven2 = make_oven()
            bowl = oven2.bowl
            self.play(pop_in(oven2, run_time=0.6))
            auto_blink(oven2.face)
            turn = Arc(radius=1.0, start_angle=0, angle=1.6 * PI, color=MINT,
                       stroke_width=9).add_tip(tip_length=0.3).move_to(bowl)
            steam = particles("calor", bowl.get_top() + UP * 0.9, 1.4, 1.8, 16, colors=[INK])
            self.add(steam)
            self.play(pop_in(turn, anchor=ORIGIN, run_time=0.4))
            idle_spin(turn, 0.6)
            t_lbl = pill("Gira para repartir", MINT, 30).move_to([-0.4, 4.4, 0])
            self.play(pop_in(t_lbl, anchor=ORIGIN, run_time=0.4), squash_bounce(bowl, 0.3, run_time=0.7))
            self.wait(0.6)
            self.clear_stage(run_time=0.6)
            self.outro()
