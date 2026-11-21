// Ejemplo HyperFrames (kit hyperframes/kit.js): ¿Cómo calienta la comida un microondas?
// Es la misma escena que examples/microondas/scene.py, para el motor alternativo. Lienzo de diseño 1080×1920 px
// (y hacia abajo); lo importante dentro de x∈[24,1056], y∈[84,1560]. El kit lo encuadra en la zona segura.

function escena(k) {
  const { C, s } = k;
  const OVEN = "#4F5BD5";

  // Molécula de agua: O grande + 2 H a 104,5° (con carita y cargas opcionales). Devuelve SVG.
  function agua(r = 108, mood = "feliz", cargas = false) {
    let o = "";
    for (const sg of [-1, 1]) {
      const ang = Math.PI / 2 + sg * (104.5 / 2) * Math.PI / 180;      // hacia abajo, abiertas
      o += s.bola(r * 0.55, C.INK, { cx: Math.cos(ang) * r * 1.28, cy: Math.sin(ang) * r * 1.28 });
    }
    o += s.bola(r, C.CORAL) + s.cara(r * 1.1, mood, 0, -4);
    if (cargas) {
      o += `<circle cx="0" cy="${-r * 1.4}" r="${r * 0.32}" fill="${C.BLUE}"/><text x="0" y="${-r * 1.4 + r * 0.13}" text-anchor="middle" font-family="Fredoka" font-weight="700" font-size="${r * 0.42}" fill="${C.INK}">−</text>`;
      for (const sg of [-1, 1]) {
        const ang = Math.PI / 2 + sg * (104.5 / 2) * Math.PI / 180, d = r * 1.95;
        o += `<circle cx="${Math.cos(ang) * d}" cy="${Math.sin(ang) * d}" r="${r * 0.27}" fill="${C.PINK}"/><text x="${Math.cos(ang) * d}" y="${Math.sin(ang) * d + r * 0.12}" text-anchor="middle" font-family="Fredoka" font-weight="700" font-size="${r * 0.38}" fill="${C.INK}">+</text>`;
      }
    }
    return o;
  }

  // Microondas con carita, ventana, plato y tazón (centrado en su origen).
  function horno() {
    return s.blob(888, 600, OVEN, { r: 66, piso: true }) +
      `<rect x="-396" y="-228" width="552" height="456" rx="42" fill="#10143F"/>` +
      `<line x1="-360" y1="-192" x2="-264" y2="-192" stroke="${C.INK}" stroke-width="7" stroke-linecap="round" opacity=".35"/>` +
      `<ellipse cx="-120" cy="186" rx="216" ry="33" fill="${C.MUTED}"/>` +
      s.blob(204, 102, C.CORAL, { r: 42, cx: -120, cy: 114 }) + s.cara(72, "feliz", -120, 116) +
      s.cara(156, "feliz", 234, -180, C.INK) +
      s.bola(50, C.SUN, { cx: 234, cy: -6 }) + `<line x1="234" y1="-6" x2="234" y2="-42" stroke="${C.BG}" stroke-width="7" stroke-linecap="round"/>` +
      s.blob(114, 38, C.MINT, { r: 14, cx: 234, cy: 120 }) + s.blob(114, 38, C.PINK, { r: 14, cx: 234, cy: 172 });
  }

  k.camSway(1.2, 7);
  const titulo = k.titulo("¿Cómo calienta\nel microondas?");

  // ---------- 0. Gancho: no es fuego, es baile ----------
  let oven, dancers, sparks, dance, stars;
  k.segmento(0, { mood: "energia" }, () => {
    stars = k.particulas("estrellas", { x: 540, y: 840, w: 1020, h: 1080, n: 22 });
    k.play(k.popIn(titulo, { dur: 0.6 }));
    oven = k.obj(horno(), { x: 540, y: 888 });
    k.play(k.popIn(oven, { dur: 0.7 }));
    const flame = k.obj(`<path d="M0 -84 L72 48 L-72 48Z" fill="${C.CORAL}"/><path d="M0 -20 L40 48 L-40 48Z" fill="${C.SUN}"/>`, { x: 420, y: 432 });
    const cross = k.obj(`<path class="trazo" d="M-90 -90 L90 90 M90 -90 L-90 90" stroke="${C.PINK}" stroke-width="16" stroke-linecap="round" fill="none"/>`, { x: 420, y: 420, ancla: "centro" });
    k.play(k.popIn(flame, { dur: 0.45 }));
    k.play(k.drawIn(cross, { dur: 0.3 }), k.jelly(flame, { dur: 0.5 }));
    k.play(k.exitOut(flame), k.exitOut(cross));
    dancers = [0, 1, 2].map((i) => k.obj(agua(38), { x: 390 + i * 150, y: 1368 }));
    k.play(k.cascada(dancers, { lag: 0.15 }));
    dancers.forEach((m, i) => { k.idleWiggle(m, { deg: 25, period: 0.5 + 0.1 * i }); k.idleFloat(m, { amp: 14, period: 0.9 + 0.2 * i }); });
    sparks = k.particulas("chispas", { x: 540, y: 1368, w: 120, h: 120, n: 26 });
    dance = k.pill("¡A bailar!", C.SUN, { size: 44, x: 732, y: 432 });
    k.play(k.popIn(dance, { dur: 0.5 }));
    k.idleWiggle(dance, { deg: 5, period: 1.0 });
  });

  // ---------- 1. Magnetrón ----------
  let mag, mLbl, wifi, wLbl, cable, zap;
  k.segmento(1, { mood: "magia" }, () => {
    k.play(k.exitOut(dance), ...dancers.map((m) => k.exitOut(m)), k.exitOut(sparks));
    mag = k.obj(s.blob(180, 144, C.VIOLET, { r: 42 }) + s.cara(96, "serio", 0, 0, C.INK), { x: 846, y: 1320 });
    k.camTo([732, 1200], { zoom: 1.6, angle: -7, dur: 1.3 });
    cable = k.obj(s.tubo([[1044, 1512], [972, 1512], [972, 1320], [936, 1320]], C.MUTED, 24), { x: 0, y: 0 });
    k.play(k.drawIn(cable, { dur: 0.6 }), k.popIn(mag, { dur: 0.7 }));
    k.flujo(cable, { n: 8, color: C.SUN, r: 8, vel: 0.6 });
    zap = k.particulas("chispas", { w: 120, h: 120, n: 30, sigue: mag });
    k.idlePulse(mag, { amp: 0.06, period: 0.5 });
    mLbl = k.pill("Magnetrón", C.VIOLET, { size: 36, x: 732, y: 1152 });
    k.play(k.popIn(mLbl, { dur: 0.45 }));
    wifi = [0, 1, 2].map((i) => k.obj(`<path class="trazo" d="M${-(30 + 30 * i) * 0.7} ${-(30 + 30 * i) * 0.7} A${30 + 30 * i} ${30 + 30 * i} 0 0 1 ${(30 + 30 * i) * 0.7} ${-(30 + 30 * i) * 0.7}" fill="none" stroke="${C.CYAN}" stroke-width="11" stroke-linecap="round" transform="rotate(-90)"/>`, { x: 564, y: 1320, ancla: "centro" }));
    k.play(k.cascada(wifi, { anim: (m) => k.popIn(m, { dur: 0.4 }), lag: 0.2 }));
    wLbl = k.pill("Como el wifi", C.CYAN, { size: 34, x: 540, y: 1452 });
    k.play(k.popIn(wLbl, { dur: 0.4 }), k.emphasize(mag, { escala: 1.2, dur: 0.6 }));
    k.camReset(1.1);
  });

  // ---------- 2. Ondas que rebotan ----------
  let guide, waves, bLbl;
  k.segmento(2, { mood: "energia" }, () => {
    k.play(k.exitOut(mLbl), ...wifi.map((m) => k.exitOut(m)), k.exitOut(wLbl));
    guide = k.obj(s.tubo([[846, 1236], [846, 1176], [708, 1176], [708, 768], [696, 768]], C.SUN, 20), { x: 0, y: 0 });
    k.play(k.drawIn(guide, { dur: 0.6 }));
    // ondas: un path por renglón que se redibuja cada cuadro (vida continua, determinista)
    waves = k.obj([[732, C.SUN], [828, C.CYAN], [924, C.PINK]].map(([y, c]) => `<path class="onda" data-y="${y}" fill="none" stroke="${c}" stroke-width="8" stroke-linecap="round"/>`).join(""), { x: 0, y: 0 });
    const ondas = Array.from(waves.el.querySelectorAll(".onda"));
    const t0 = k.t;
    k.cadaCuadro((t) => {
      ondas.forEach((p, i) => {
        const y = +p.dataset.y, ph = (t - t0) * 9 * (i % 2 ? -1 : 1);
        let d = "";
        for (let x = 168; x <= 672; x += 12) d += `${d ? "L" : "M"}${x} ${(y + 22 * Math.sin(x / 24 - ph)).toFixed(1)}`;
        p.setAttribute("d", d);
      });
    });
    k.play(k.fadeIn(waves, { dur: 0.4 }));
    const hits = [];
    for (const y of [732, 828, 924]) for (const x of [156, 684]) hits.push(k.obj(s.destello(36, C.INK), { x, y, ancla: "centro" }));
    k.play(k.cascada(hits, { anim: (h) => ({ dur: 0.6, add: (t) => { k.popIn(h, { dur: 0.3 }).add(t); k.exitOut(h, { dur: 0.3 }).add(t + 0.3); } }), lag: 0.18 }));
    bLbl = k.pill("Rebotan en el metal", C.SUN, { size: 36, x: 468, y: 432 });
    k.play(k.popIn(bLbl, { dur: 0.45 }));
    k.idleWiggle(bLbl, { deg: 3, period: 1.3 });
    k.camTo(null, { angle: 4, zoom: 1.08, dur: 1.5 });
  });

  // ---------- 3. La molécula de agua ----------
  let big, beam, bubbles, cLbl;
  k.segmento(3, { mood: "frio" }, () => {
    k.clearStage({ dur: 0.7 });
    k.camReset(0.9);
    beam = k.obj(s.rayos(960, C.CYAN, 16, 0.12), { x: 540, y: 888, ancla: "centro", z: -1 });
    bubbles = k.particulas("burbujas", { x: 540, y: 1080, w: 960, h: 1080, n: 22 });
    big = k.obj(agua(150, "feliz", true), { x: 540, y: 860 });
    k.play(k.popIn(big, { dur: 0.8 }), k.fadeIn(beam, { dur: 0.5 }));
    k.idleSpin(beam, { vueltasPorS: 0.03 });
    k.play(k.jelly(big, { dur: 0.6 }));
    cLbl = k.pill("Una punta + y otra −", C.CYAN, { size: 36, x: 540, y: 432 });
    k.play(k.popIn(cLbl, { dur: 0.45 }));
    k.alive(big);
  });

  // ---------- 4. El campo cambia y las moléculas giran ----------
  let field, minis, rate;
  k.segmento(4, { mood: "magia" }, () => {
    k.stopIdle(big);
    k.play(k.exitOut(cLbl, { dur: 0.3 }), k.mover(big, { escala: 0.75, y: 780, dur: 0.6 }));
    field = k.obj(`<line class="trazo" x1="-400" y1="0" x2="380" y2="0" stroke="${C.SUN}" stroke-width="16" stroke-linecap="round"/><path d="M360 -34 L420 0 L360 34Z" fill="${C.SUN}"/><text x="0" y="62" text-anchor="middle" font-family="Fredoka" font-weight="700" font-size="36" fill="${C.SUN}">campo</text>`, { x: 540, y: 1224, ancla: "centro" });
    minis = [0, 1, 2, 3].map((i) => k.obj(agua(36), { x: 252 + i * 192, y: 1404, ancla: "centro" }));
    k.play(k.drawIn(field, { dur: 0.5 }), k.cascada(minis, { lag: 0.12 }));
    for (let j = 0; j < 4; j++) {
      k.camTo(null, { angle: j % 2 === 0 ? 5 : -5, dur: 0.55 });
      k.play(k.rotar(field, 180, { dur: 0.55 }), k.rotar(big, 180, { dur: 0.55 }), ...minis.map((m) => k.rotar(m, 180, { dur: 0.55 })));
    }
    rate = k.pill("¡~5.000 millones por segundo!", C.PINK, { size: 34, colorTexto: C.INK, x: 540, y: 420 });
    k.play(k.popIn(rate, { dur: 0.45 }));
    k.play(k.emphasize(rate, { escala: 1.2, dur: 0.6 }));
    k.camReset(0.8);
    minis.forEach((m, i) => k.idleSpin(m, { vueltasPorS: [0.9, -1.1, 1.3, -0.8][i] / 6.28 }));
  });

  // ---------- 5. Choques = calor ----------
  let hLbl;
  k.segmento(5, { mood: "calor" }, () => {
    k.play(k.exitOut(field), k.exitOut(rate), k.exitOut(big), k.fadeOut(beam, { dur: 0.45 }), k.fadeOut(bubbles, { dur: 0.45 }), ...minis.map((m) => k.exitOut(m)));
    const R = k.rng(4);
    const crowd = Array.from({ length: 14 }, () => k.obj(agua(30), { x: 156 + R() * 600, y: 576 + R() * 840, rot: R() * 360, ancla: "centro" }));
    k.play(k.cascada(crowd, { lag: 0.05 }));
    // agitación: cada molécula rebota dentro de una caja (posición calculada en función de t)
    const t0 = k.t;
    crowd.forEach((m, i) => {
      const x0 = m.st.x, y0 = m.st.y, vx = (R() - 0.5) * 520, vy = (R() - 0.5) * 520;
      const bounce = (p, v, lo, hi, tt) => { const L = hi - lo, u = (((p - lo + v * tt) % (2 * L)) + 2 * L) % (2 * L); return lo + (u < L ? u : 2 * L - u); };
      m.pos = (t) => t < t0 ? [x0, y0] : [bounce(x0, vx, 132, 780, t - t0), bounce(y0, vy, 552, 1440, t - t0)];
      k.idleSpin(m, { vueltasPorS: (i % 2 ? 1 : -1) * 0.95 });
    });
    k.particulas("calor", { x: 456, y: 996, w: 720, h: 960, n: 36 });
    const thermo = k.obj(`<rect x="-30" y="-300" width="60" height="600" rx="30" fill="#2A1530"/><rect class="nivel" x="-18" y="168" width="36" height="72" rx="10" fill="${C.CORAL}"/>` + s.bola(60, C.CORAL, { cx: 0, cy: 300 }), { x: 960, y: 960 });
    k.play(k.popIn(thermo, { dur: 0.5 }));
    k.play(k.attr(thermo, ".nivel", { y: -276, height: 516 }, { dur: 1.3 }), k.jelly(thermo, { dur: 0.8 }));
    hLbl = k.pill("Agitación = calor", C.CORAL, { size: 36, x: 468, y: 408 });
    k.play(k.popIn(hLbl, { dur: 0.45 }));
    k.idleWiggle(hLbl, { deg: 4, period: 0.9 });
  });

  // ---------- 6. El plato gira + cierre ----------
  k.segmento(6, { mood: "energia" }, (d) => {
    k.clearStage({ dur: 0.5 });
    const oven2 = k.obj(horno(), { x: 540, y: 888 });
    k.play(k.popIn(oven2, { dur: 0.6 }));
    k.particulas("calor", { x: 420, y: 900, w: 168, h: 216, n: 16, colores: [C.INK] });
    const turn = k.obj(`<path class="trazo" d="M120 0 A120 120 0 1 1 37 -114" fill="none" stroke="${C.MINT}" stroke-width="11" stroke-linecap="round"/><path d="M20 -140 L62 -110 L18 -84Z" fill="${C.MINT}"/>`, { x: 420, y: 1002, ancla: "centro" });
    k.play(k.popIn(turn, { dur: 0.4 }));
    k.idleSpin(turn, { vueltasPorS: 0.6 / 6.28 });
    const tLbl = k.pill("Gira para repartir", C.MINT, { size: 36, x: 492, y: 432 });
    k.play(k.popIn(tLbl, { dur: 0.4 }), k.squashBounce(oven2, { alto: 36, dur: 0.7 }));
    k.wait(Math.max(0.2, d - (k.t - k.inicios[6]) - 2.0));
    k.clearStage({ dur: 0.6 });
    k.outro();
  });
}
