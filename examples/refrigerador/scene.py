"""Ejemplo de escena Explapix (kit v2): ¿Cómo funciona un refrigerador?

Este archivo es el tipo de código que Claude genera en cada video (llm.scene_code).
Muestra el estilo (toon, glow, caritas, fondo vivo) y los principios de animación
(pop_in, squash_bounce, jelly, emphasize, anticipate_move, move_along_arc, focus, cascade,
idle_breathe/auto_blink, exit_out).
"""
import numpy as np
from explapix.kit import *  # noqa: F401,F403

FRIDGE = "#6F8BFF"


class Video(ExplapixScene):
    def construct(self):
        # ---------- Personaje: el refri ----------
        body = blob(4.2, 9.6, FRIDGE, r=0.6, floor_shadow=True).move_to([-1.5, -0.2, 0])
        panel = RoundedRectangle(corner_radius=0.4, width=3.5, height=8.9, stroke_width=0,
                                 fill_color="#141A52", fill_opacity=1).move_to([-1.6, -0.2, 0])
        cold_air = panel.copy().set_fill(CYAN, 0.0)
        handle = blob(0.22, 1.5, INK, r=0.1).move_to([0.25, 1.4, 0])
        shelf = Line([-3.2, -1.0, 0], [0.0, -1.0, 0], color=shade(FRIDGE, -0.2), stroke_width=6)
        fc = face(1.6, "feliz", eye_color=INK).move_to([-1.6, 1.0, 0])
        fridge = VGroup(body, panel, cold_air, shelf, handle, fc)
        title = title_text("¿Cómo funciona\nun refri?", 62).move_to([0, 6.6, 0])

        # ---------- Circuito de refrigerante ----------
        pts = [(2.0, -4.2), (3.6, -4.2), (3.6, 3.6), (1.9, 3.6), (0.2, 3.6), (-2.9, 3.6),
               (-2.9, 2.8), (1.0, 2.8), (1.0, -4.2), (2.0, -4.2)]
        P = [np.array([x, y, 0.0]) for x, y in pts]
        pipe = tube(pts, MUTED, width=14)
        seg_len = [np.linalg.norm(P[i + 1] - P[i]) for i in range(len(P) - 1)]
        cum = np.concatenate([[0], np.cumsum(seg_len)]) / sum(seg_len)
        f_cond_end, f_valve, f_evap_end = cum[2], cum[3], cum[7]

        def refrig_color(p):
            if p < f_cond_end:                       # compresor -> condensador: caliente
                return color_lerp(HOT, SUN, p / f_cond_end)
            if p < f_valve:                          # líquido tibio hacia la válvula
                return SUN
            if p < f_evap_end:                       # después de la válvula: muy frío
                return color_lerp(CYAN, "#B8F3FF", (p - f_valve) / (f_evap_end - f_valve))
            return color_lerp("#B8F3FF", PINK, (p - f_evap_end) / (1 - f_evap_end))

        comp_body = blob(1.5, 1.15, VIOLET, r=0.35, floor_shadow=True)
        compressor = VGroup(comp_body, face(0.8, "serio", eye_color=INK).move_to(comp_body)
                            ).move_to([1.7, -4.25, 0])
        zig = [(3.6 + (0.38 if i % 2 else -0.38), -3.5 + i * 0.58) for i in range(12)]
        condenser = tube(zig, shade(CORAL, -0.1), width=12)
        valve = VGroup(
            Triangle(fill_color=SUN, fill_opacity=1, stroke_width=0).scale(0.3).rotate(-PI / 2),
            Triangle(fill_color=SUN, fill_opacity=1, stroke_width=0).scale(0.3).rotate(PI / 2),
        ).arrange(RIGHT, buff=0).move_to(P[3])
        evap = tube([p[:2] for p in P[4:8]], CYAN, width=18)

        # ---------- 0. Gancho: el refri no fabrica frío ----------
        with self.segment(0) as d:
            self.play(pop_in(title, anchor=ORIGIN, run_time=0.7))
            self.play(pop_in(fridge, run_time=0.8))
            idle_breathe(body, amp=0.012)
            auto_blink(fc)
            no = pill("No fabrica frío", PINK, 32).move_to([-1.5, -2.9, 0])
            self.play(pop_in(no, anchor=ORIGIN, run_time=0.5))
            self.play(emphasize(no, run_time=0.5))
            heat = VGroup(*[glow(Dot(), CORAL, radius=0.32, layers=5, opacity=0.35)
                            .add(ball(0.2, CORAL)).move_to([-1.5 + dx, y, 0])
                            for dx, y in ((-0.6, 2.2), (0.4, 0.4), (-0.3, -1.6))])
            self.play(cascade(*heat, lag=0.2, run_time=0.6))
            self.play(LaggedStart(*[move_along_arc(h, [3.3, 4.6 - k * 1.6, 0], angle=-PI / 3,
                                                   run_time=0.9) for k, h in enumerate(heat)],
                                  lag_ratio=0.2))
            yes = pill("Saca el calor", HOT, 32).move_to([2.0, 4.9, 0])
            self.play(pop_in(yes, anchor=ORIGIN, run_time=0.5), FadeOut(heat, run_time=0.4))

        # ---------- 1. Refrigerante ----------
        with self.segment(1) as d:
            self.play(exit_out(no), exit_out(yes),
                      title.animate(rate_func=EASE).scale(0.7).move_to([0, 6.9, 0]), run_time=0.6)
            self.bring_to_back(pipe)
            self.bring_to_back(self.bg)
            self.play(draw_in(pipe, run_time=1.6))
            dots = flow_dots(pipe.path, n=22, color=INK, radius=0.085, speed=0.07)
            self.add(dots)
            lbl = pill("Refrigerante", CYAN, 30).move_to([-1.0, -2.7, 0])
            self.play(pop_in(lbl, anchor=ORIGIN, run_time=0.5))
            self.play(emphasize(lbl, 1.15, run_time=0.5))

        # ---------- 2. Compresor: aprieta y calienta ----------
        with self.segment(2) as d:
            self.play(exit_out(lbl, run_time=0.3), pop_in(compressor, run_time=0.6))
            c_lbl = pill("Compresor", VIOLET, 30, text_color=INK).move_to([1.9, -2.6, 0])
            self.play(pop_in(c_lbl, anchor=ORIGIN, run_time=0.4))
            dots.color_fn = lambda p: HOT if p < f_cond_end else INK
            for _ in range(2):  # anticipación + squash: aprieta el gas
                self.play(squash_bounce(compressor, height=0.25, run_time=0.55))
            hot = T("¡Muy caliente!", 34, HOT).next_to(c_lbl, UP, buff=0.3)
            self.play(pop_in(hot, anchor=ORIGIN, run_time=0.45))

        # ---------- 3. Condensador: suelta el calor atrás ----------
        with self.segment(3) as d:
            self.play(exit_out(c_lbl), exit_out(hot), draw_in(condenser, run_time=0.9))
            k_lbl = pill("Condensador", SUN, 28).rotate(PI / 2).move_to([2.35, 0.2, 0])
            self.play(pop_in(k_lbl, anchor=ORIGIN, run_time=0.4))
            dots.color_fn = lambda p: refrig_color(p) if p < f_valve else INK
            self.play(self.focus([2.6, 0.2, 0], zoom=1.45, run_time=0.8))
            waves = VGroup(*[Arc(radius=0.3 + 0.22 * k, start_angle=-PI / 4, angle=PI / 2,
                                 color=HOT, stroke_width=7).move_arc_center_to([3.9, y, 0])
                             for y in (-2.0, 0.5, 3.0) for k in range(3)])
            self.play(LaggedStart(*[Create(w, rate_func=SNAP) for w in waves], lag_ratio=0.08),
                      run_time=1.0)
            self.play(waves.animate(rate_func=EASE).shift(RIGHT * 0.5).set_opacity(0),
                      self.reset_camera(run_time=0.9), run_time=0.9)
            self.remove(waves)

        # ---------- 4. Válvula de expansión: ¡frío de golpe! ----------
        with self.segment(4) as d:
            self.play(exit_out(k_lbl), pop_in(valve, anchor=ORIGIN, run_time=0.5))
            self.play(self.focus(valve, zoom=1.7, run_time=0.7))
            v_lbl = pill("Válvula", SUN, 28).next_to(valve, UP, buff=0.3)
            self.play(pop_in(v_lbl, anchor=ORIGIN, run_time=0.4),
                      Flash(valve, color=CYAN, line_length=0.35, num_lines=12, run_time=0.6))
            dots.color_fn = lambda p: refrig_color(p) if p < f_evap_end else INK
            cold = pill("-20 °C", CYAN, 34).move_to([1.2, 5.2, 0])
            self.play(pop_in(cold, anchor=ORIGIN, run_time=0.5), jelly(valve, run_time=0.6))
            self.play(self.reset_camera(run_time=0.8))

        # ---------- 5. Evaporador: absorbe el calor de la comida ----------
        with self.segment(5) as d:
            self.play(exit_out(v_lbl), exit_out(cold), draw_in(evap, run_time=0.7))
            e_lbl = pill("Evaporador", CYAN, 28).move_to([-1.4, 2.0, 0])
            self.play(pop_in(e_lbl, anchor=ORIGIN, run_time=0.4))
            apple = VGroup(ball(0.42, PINK), face(0.5).move_to(UP * 0.05))
            milk = VGroup(blob(0.7, 1.15, INK, r=0.15), face(0.45, eye_color=BG))
            cheese = VGroup(blob(1.0, 0.65, SUN, r=0.12), face(0.4))
            food = VGroup(apple, milk, cheese).arrange(RIGHT, buff=0.3, aligned_edge=DOWN)
            food.next_to(shelf, UP, buff=0.02)
            self.play(cascade(*food, lag=0.2, run_time=0.9))
            for f in food:
                auto_blink(f[1], every=2.4)
            heat = VGroup(*[ball(0.12, CORAL).move_to(f.get_top() + UP * 0.2) for f in food])
            self.add(heat)
            self.play(LaggedStart(*[h.animate(rate_func=EASE).move_to([h.get_x(), 2.85, 0])
                                    .set_color(CYAN) for h in heat], lag_ratio=0.15,
                                  run_time=1.1))
            self.remove(heat, *heat)
            dots.color_fn = refrig_color
            self.play(cold_air.animate(rate_func=EASE).set_fill(CYAN, 0.22),
                      emphasize(fc, 1.2), run_time=0.8)

        # ---------- 6. Cierre ----------
        with self.segment(6) as d:
            self.play(exit_out(e_lbl, run_time=0.3))
            back = pill("Atrás: ~45 °C", HOT, 30).move_to([2.1, 4.9, 0])
            front = pill("Adentro: 4 °C", CYAN, 30).move_to([-1.5, -2.7, 0])
            self.play(cascade(back, front, anim=lambda m: pop_in(m, anchor=ORIGIN), lag=0.3,
                              run_time=0.8))
            self.play(squash_bounce(fridge, height=0.4, run_time=0.8))
            stop_idle(body, fc, *[f[1] for f in food])
            self.clear_stage(run_time=0.7)
            self.outro()
