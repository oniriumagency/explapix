"""Ejemplo de escena Explapix: ¿Cómo funciona un refrigerador?

Este archivo es el tipo de código que Claude genera en cada video (scenegen.py).
"""
import numpy as np
from explapix.kit import *  # noqa: F401,F403


class Video(ExplapixScene):
    def construct(self):
        # ---------- Geometría ----------
        fridge = card(4.2, 9.6, INK, r=0.35).move_to([-1.5, -0.2, 0])
        inside = RoundedRectangle(corner_radius=0.25, width=3.8, height=9.2, stroke_width=0,
                                  fill_color=COLD, fill_opacity=0.18).move_to(fridge)
        handle = RoundedRectangle(corner_radius=0.08, width=0.18, height=1.6, fill_color=INK,
                                  fill_opacity=1, stroke_width=0).move_to([0.25, 1.2, 0])
        shelf = Line([-3.4, -1.0, 0], [0.4, -1.0, 0], color=MUTED, stroke_width=4)
        title = T("¿Cómo funciona\nun refrigerador?", 52, INK).to_edge(UP, buff=0.7)

        pts = [(2.0, -4.2), (3.6, -4.2), (3.6, 3.6), (1.9, 3.6), (0.2, 3.6), (-2.9, 3.6),
               (-2.9, 2.8), (1.0, 2.8), (1.0, -4.2), (2.0, -4.2)]
        P = [np.array([x, y, 0.0]) for x, y in pts]
        tube = VMobject(stroke_color=MUTED, stroke_width=10).set_points_as_corners(P)
        seg_len = [np.linalg.norm(P[i + 1] - P[i]) for i in range(len(P) - 1)]
        cum = np.concatenate([[0], np.cumsum(seg_len)]) / sum(seg_len)
        f_cond_end, f_valve, f_evap_end = cum[2], cum[3], cum[7]

        def refrig_color(p):
            if p < f_cond_end:                       # compresor -> condensador: caliente
                return color_lerp(HOT, ACCENT, p / f_cond_end)
            if p < f_valve:                          # líquido tibio hacia la válvula
                return ACCENT
            if p < f_evap_end:                       # después de la válvula: muy frío
                return color_lerp(COLD, "#9BD1FF", (p - f_valve) / (f_evap_end - f_valve))
            return color_lerp("#9BD1FF", PINK, (p - f_evap_end) / (1 - f_evap_end))

        compressor = VGroup(
            RoundedRectangle(corner_radius=0.3, width=1.3, height=1.0, fill_color="#2B2F55",
                             fill_opacity=1, stroke_color=INK, stroke_width=5),
            T("C", 36, INK)).move_to([1.6, -4.2, 0])
        zig = [np.array([3.6 + (0.35 if i % 2 else -0.35), -3.6 + i * 0.6, 0]) for i in range(12)]
        condenser = VMobject(stroke_color=INK, stroke_width=7).set_points_as_corners(zig)
        valve = VGroup(Triangle(fill_color=ACCENT, fill_opacity=1, stroke_width=0).scale(0.28).rotate(-PI / 2),
                       Triangle(fill_color=ACCENT, fill_opacity=1, stroke_width=0).scale(0.28).rotate(PI / 2)
                       ).arrange(RIGHT, buff=0).move_to(P[3])
        evap = VMobject(stroke_color=COLD, stroke_width=14).set_points_as_corners(P[4:8])

        # ---------- 0. Gancho ----------
        with self.segment(0) as d:
            self.play(Write(title), run_time=0.8)
            self.play(Create(fridge), FadeIn(inside), FadeIn(handle), Create(shelf), run_time=1.0)
            heat = VGroup(*[Arrow([-1.5, y, 0], [3.8, y + 0.4, 0], color=HOT, stroke_width=8,
                                  buff=0, max_tip_length_to_length_ratio=0.08) for y in (2.0, 0.0, -2.0)])
            no = pill("No fabrica frío", PINK, 32).move_to([-1.5, -3.2, 0])
            self.play(FadeIn(no, scale=1.3), run_time=0.5)
            self.play(LaggedStart(*[GrowArrow(a) for a in heat], lag_ratio=0.25), run_time=1.4)
            yes = pill("Saca el calor", HOT, 32).move_to([2.0, 4.6, 0])
            self.play(FadeIn(yes, shift=DOWN * 0.3), run_time=0.5)

        # ---------- 1. Refrigerante ----------
        with self.segment(1) as d:
            self.play(FadeOut(heat), FadeOut(no), FadeOut(yes), title.animate.scale(0.75).to_edge(UP, buff=0.4),
                      run_time=0.6)
            self.play(Create(tube), run_time=1.6)
            dots = flow_dots(tube, n=22, color=INK, radius=0.09, speed=0.07)
            self.add(dots)
            lbl = pill("Refrigerante", COLD, 30).move_to([-1.0, -2.6, 0])
            self.play(FadeIn(lbl, shift=UP * 0.3), run_time=0.5)

        # ---------- 2. Compresor ----------
        with self.segment(2) as d:
            self.play(FadeOut(lbl), FadeIn(compressor, scale=0.6), run_time=0.6)
            c_lbl = pill("Compresor", HOT, 30).next_to(compressor, UP, buff=0.35).shift(RIGHT * 0.6)
            self.play(FadeIn(c_lbl), run_time=0.4)
            dots.color_fn = lambda p: HOT if p < f_cond_end else INK
            for _ in range(3):
                self.play(compressor.animate.scale(1.15), run_time=0.25)
                self.play(compressor.animate.scale(1 / 1.15), run_time=0.25)
            hot = T("¡Muy caliente!", 30, HOT).next_to(c_lbl, UP, buff=0.25)
            self.play(Write(hot), run_time=0.6)

        # ---------- 3. Condensador ----------
        with self.segment(3) as d:
            self.play(FadeOut(c_lbl), FadeOut(hot), Create(condenser), run_time=0.9)
            k_lbl = pill("Condensador", ACCENT, 28).move_to([2.2, 0.0, 0]).rotate(PI / 2)
            self.play(FadeIn(k_lbl), run_time=0.4)
            dots.color_fn = lambda p: refrig_color(p) if p < f_valve else INK
            waves = VGroup(*[Arc(radius=0.35 + 0.25 * k, start_angle=-PI / 4, angle=PI / 2, color=HOT,
                                 stroke_width=6).move_arc_center_to([3.8, y, 0])
                             for y in (-2.0, 0.5, 3.0) for k in range(3)])
            self.play(LaggedStart(*[Create(w) for w in waves], lag_ratio=0.08), run_time=1.6)
            self.play(waves.animate.shift(RIGHT * 0.35).set_opacity(0), run_time=1.0)
            self.remove(waves)

        # ---------- 4. Válvula de expansión ----------
        with self.segment(4) as d:
            self.play(FadeOut(k_lbl), FadeIn(valve, scale=0.5), run_time=0.5)
            v_lbl = pill("Válvula", ACCENT, 28).next_to(valve, UP, buff=0.3)
            self.play(FadeIn(v_lbl), Flash(valve, color=COLD, line_length=0.35, num_lines=12), run_time=0.8)
            dots.color_fn = lambda p: refrig_color(p) if p < f_evap_end else INK
            cold = T("-20 °C", 40, COLD).move_to([-1.2, 4.5, 0])
            self.play(FadeIn(cold, scale=1.4), run_time=0.6)

        # ---------- 5. Evaporador ----------
        with self.segment(5) as d:
            self.play(FadeOut(v_lbl), FadeOut(cold), Create(evap), run_time=0.8)
            e_lbl = pill("Evaporador", COLD, 28).move_to([-1.3, 1.8, 0])
            self.play(FadeIn(e_lbl), run_time=0.4)
            food = VGroup(
                Circle(0.45, fill_color=PINK, fill_opacity=1, stroke_width=0),
                RoundedRectangle(corner_radius=0.1, width=0.8, height=1.2, fill_color=GOOD,
                                 fill_opacity=1, stroke_width=0),
                RoundedRectangle(corner_radius=0.1, width=1.0, height=0.7, fill_color=ACCENT,
                                 fill_opacity=1, stroke_width=0),
            ).arrange(RIGHT, buff=0.35, aligned_edge=DOWN).move_to([-1.5, -0.4, 0])
            self.play(LaggedStart(*[FadeIn(f, shift=UP * 0.3) for f in food], lag_ratio=0.2), run_time=0.8)
            arrows = VGroup(*[Arrow(f.get_top(), [f.get_x(), 2.7, 0], color=HOT, stroke_width=6, buff=0.1)
                              for f in food])
            self.play(LaggedStart(*[GrowArrow(a) for a in arrows], lag_ratio=0.2), run_time=1.0)
            dots.color_fn = refrig_color
            self.play(inside.animate.set_fill(COLD, opacity=0.32), FadeOut(arrows), run_time=1.0)
            self.play(Rotate(Arc(radius=0.6, angle=1.6 * PI, color=INK, stroke_width=6)
                             .add_tip(tip_length=0.25).move_to([2.6, 0.2, 0]), angle=2 * PI),
                      run_time=1.2)

        # ---------- 6. Cierre ----------
        with self.segment(6) as d:
            self.play(FadeOut(e_lbl), run_time=0.3)
            back = pill("Atrás: ~45 °C", HOT, 30).move_to([2.4, 4.9, 0])
            front = pill("Adentro: 4 °C", COLD, 30).move_to([-1.5, -2.6, 0])
            self.play(FadeIn(back, shift=DOWN * 0.2), FadeIn(front, shift=UP * 0.2), run_time=0.7)
            self.wait(1.4)
            scene_all = Group(*[m for m in self.mobjects if m is not self._caption])
            logo = VGroup(T("EXPLA", 72, INK), T("PIX", 72, ACCENT)).arrange(RIGHT, buff=0.05)
            sub = T("cómo funcionan las cosas", 30, MUTED, weight=NORMAL).next_to(logo, DOWN)
            brand = VGroup(logo, sub).move_to([0, 0.5, 0])
            dots.clear_updaters()
            self.play(FadeOut(scene_all, scale=0.9), run_time=0.6)
            self.play(FadeIn(brand, scale=1.2), run_time=0.6)
