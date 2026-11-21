/* Kit HyperFrames de Factos Didácticos (motor alternativo a Manim, misma estética que explapix/kit.py).

Una escena es un archivo escena.js con UNA función:

    function escena(k) {
      k.camSway(1.2, 7);
      k.segmento(0, { mood: "energia" }, (d) => {      // d = duración real del audio de ese segmento
        const horno = k.obj(k.s.blob(560, 380, "#4F5BD5") + k.s.cara(150, "feliz", 120, -60), { x: 540, y: 800 });
        k.play(k.popIn(horno));                          // bloquea: avanza el reloj lo que dura
        k.alive(horno);                                  // vida constante (flota + pulso)
        k.camTo(horno, { zoom: 1.4, angle: -6, dur: 1.2 });   // NO bloquea
        k.wait(0.4);
      });
    }

LIENZO DE DISEÑO: 1080×1920 px, origen arriba a la izquierda, y hacia abajo. Todo lo importante va en la
caja x∈[24, 1056], y∈[84, 1560] (equivale a DESIGN_BOX de kit.py). El kit la encuadra sola dentro de la
zona segura de config/reglas.yaml y pone debajo la franja de subtítulos (no dibujes ahí).
VIDEO LARGO HORIZONTAL (cfg.formato = "largo"): lienzo 1920×1080, caja x∈[72, 1848], y∈[60, 924], margen de TV
del 5 %, capítulos con k.chapter(titulo, { numero }) y pantalla final con k.endScreen(20) (en vez de k.outro()).

TIEMPO: como en Manim, hay un cursor k.t. k.play(...) agrega animaciones en paralelo en el cursor y lo
avanza lo que dure la más larga; k.wait(s) lo avanza. k.segmento(i) pone el cursor al inicio exacto del
audio i, así que la imagen nunca se desfasa de la voz aunque un segmento se pase de tiempo (se avisa).

Todo es determinista (PRNG con semilla, nada de Math.random ni Date): HyperFrames hace seek a cada
cuadro, así que la vida continua (idles, cámara, partículas, parpadeo) se calcula en función de t.
*/
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  let W = 1080, H = 1920;   // se fijan en crear() según el formato (vertical u horizontal)

  // ---------- Paleta (la de kit.py) ----------
  const C = {
    BG: "#0B0D26", BG2: "#26145A", INK: "#FFF8EE", MUTED: "#7E86C9", BLUE: "#2F6BFF", CYAN: "#46E0FF",
    VIOLET: "#8B5CFF", PINK: "#FF4FA3", CORAL: "#FF7A45", SUN: "#FFC93C", MINT: "#2EE6A8",
  };
  C.ACCENT = C.SUN; C.HOT = C.CORAL; C.COLD = C.CYAN; C.GOOD = C.MINT;
  const PALETTE = [C.BLUE, C.CYAN, C.VIOLET, C.PINK, C.CORAL, C.SUN, C.MINT];
  const MOODS = {  // abajo, medio, arriba, halo
    noche: ["#0B0D26", "#0B0D26", "#26145A", C.VIOLET],
    energia: ["#0D0B2E", "#1B0F4D", "#4A1A7A", C.VIOLET],
    calor: ["#1F0A1E", "#3A0F24", "#6B1E2A", C.CORAL],
    frio: ["#06142E", "#0A2450", "#0F3A6E", C.CYAN],
    naturaleza: ["#061F1E", "#0A3330", "#11524A", C.MINT],
    sol: ["#1E1206", "#3A2208", "#6A3A0C", C.SUN],
    magia: ["#1A0726", "#33104A", "#5E1A6E", C.PINK],
  };
  let DESIGN_BOX = [24, 1056, 84, 1560];   // x0, x1, y0, y1 (vertical; en horizontal [72, 1848, 60, 924])
  const CTA_TEXT = { guardar: "Guarda este video", comentar: "Comenta", compartir: "Compártelo",
    seguir: "Síguenos", like: "Dale like" };

  // ---------- Utilidades ----------
  function rng(seed) {
    let s = seed | 0;
    return function () {
      s = (s + 0x6D2B79F5) | 0;
      let t = Math.imul(s ^ (s >>> 15), 1 | s);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const lerp = (a, b, u) => a + (b - a) * u;
  const easeIO = (u) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2);
  function anticipateOvershoot(t, tension = 2.2) {
    const a = (x) => x * x * ((tension + 1) * x - tension), o = (x) => x * x * ((tension + 1) * x + tension);
    return t < 0.5 ? 0.5 * a(2 * t) : 0.5 * (o(2 * t - 2) + 2);
  }
  function hex(c) { const n = parseInt(c.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
  function shade(c, k) {   // k<0 oscurece hacia el fondo, k>0 aclara hacia blanco (como kit.py)
    const a = hex(c), b = k < 0 ? hex(C.BG) : [255, 255, 255], u = Math.abs(k);
    return "#" + a.map((v, i) => Math.round(lerp(v, b[i], u)).toString(16).padStart(2, "0")).join("");
  }
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  let uid = 0;
  const nid = (p) => `${p}${++uid}`;
  function el(tag, attrs, parent, ns) {
    const e = ns ? document.createElementNS(NS, tag) : document.createElement(tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  // ---------- Formas SVG con volumen (cadenas; se combinan con +) ----------
  // Todas se dibujan centradas en (cx, cy) dentro del SVG del objeto (origen = centro del objeto).
  const s = {
    /** Forma plana con sombra tonal abajo-derecha y luz de borde arriba-izquierda (toon de kit.py). */
    toon(d, color, { sombra = 0.14, luz = true, piso = false, w = 100, h = 100 } = {}) {
      const off = sombra * Math.min(w, h);
      const id = nid("t");
      let out = "";
      if (piso) out += `<ellipse cx="0" cy="${h / 2 + 6}" rx="${w * 0.47}" ry="${Math.max(w * 0.07, 6)}" fill="#000" opacity=".35"/>`;
      out += `<clipPath id="${id}"><path d="${d}"/></clipPath>`;
      out += `<path d="${d}" fill="${color}"/>`;
      out += `<g clip-path="url(#${id})"><path d="${d}" transform="translate(${-off} ${-off})" fill="none" stroke="${shade(color, -0.32)}" stroke-width="${off * 2.4}"/></g>`;
      if (luz) out += `<g clip-path="url(#${id})"><path d="${d}" transform="translate(${off * 0.3} ${off * 0.3})" fill="none" stroke="${shade(color, 0.5)}" stroke-opacity=".9" stroke-width="${off * 0.7}"/></g>`;
      return out;
    },
    rectPath(w, h, r, cx = 0, cy = 0) {
      r = Math.min(r, w / 2, h / 2);
      const x = cx - w / 2, y = cy - h / 2;
      return `M${x + r} ${y}H${x + w - r}A${r} ${r} 0 0 1 ${x + w} ${y + r}V${y + h - r}A${r} ${r} 0 0 1 ${x + w - r} ${y + h}H${x + r}A${r} ${r} 0 0 1 ${x} ${y + h - r}V${y + r}A${r} ${r} 0 0 1 ${x + r} ${y}Z`;
    },
    circlePath(r, cx = 0, cy = 0) {
      return `M${cx - r} ${cy}A${r} ${r} 0 1 0 ${cx + r} ${cy}A${r} ${r} 0 1 0 ${cx - r} ${cy}Z`;
    },
    /** Caja redondeada con volumen (el ladrillo básico). */
    blob(w, h, color, { r, cx = 0, cy = 0, piso = false } = {}) {
      r = r == null ? Math.min(w, h) * 0.22 : r;
      return s.toon(s.rectPath(w, h, r, cx, cy), color, { w, h, piso });
    },
    /** Bola con volumen. */
    bola(r, color, { cx = 0, cy = 0, piso = false } = {}) {
      return s.toon(s.circlePath(r, cx, cy), color, { w: 2 * r, h: 2 * r, piso });
    },
    /** Corazón con volumen (ancho ≈ size). */
    corazon(size, color, { cx = 0, cy = 0 } = {}) {
      const k = size / 200;
      const p = (x, y) => `${cx + x * k} ${cy + y * k}`;
      const d = `M${p(0, 70)}C${p(-20, 50)} ${p(-100, 10)} ${p(-100, -35)}C${p(-100, -75)} ${p(-60, -95)} ${p(-32, -90)}C${p(-15, -87)} ${p(-5, -75)} ${p(0, -62)}C${p(5, -75)} ${p(15, -87)} ${p(32, -90)}C${p(60, -95)} ${p(100, -75)} ${p(100, -35)}C${p(100, 10)} ${p(20, 50)} ${p(0, 70)}Z`;
      return s.toon(d, color, { w: size, h: size * 0.8 });
    },
    /** Gota con volumen (alto ≈ size). */
    gota(size, color, { cx = 0, cy = 0 } = {}) {
      const k = size / 200;
      const p = (x, y) => `${cx + x * k} ${cy + y * k}`;
      const d = `M${p(0, -100)}C${p(30, -55)} ${p(70, -10)} ${p(70, 30)}C${p(70, 72)} ${p(38, 100)} ${p(0, 100)}C${p(-38, 100)} ${p(-70, 72)} ${p(-70, 30)}C${p(-70, -10)} ${p(-30, -55)} ${p(0, -100)}Z`;
      return s.toon(d, color, { w: size * 0.7, h: size });
    },
    /** Cualquier path con volumen: s.forma("M0 0 L...", color, ancho, alto). */
    forma(d, color, w = 100, h = 100) { return s.toon(d, color, { w, h }); },
    /** Carita: ojos (parpadean solos), boca y mejillas. mood: feliz | sorpresa | dormido | serio. */
    cara(width = 120, mood = "feliz", cx = 0, cy = 0, ojos = C.BG) {
      const k = width / 120;
      let o = `<g transform="translate(${cx} ${cy}) scale(${k})">`;
      o += `<ellipse cx="-54" cy="19" rx="24" ry="13" fill="${C.PINK}" opacity=".6"/><ellipse cx="54" cy="19" rx="24" ry="13" fill="${C.PINK}" opacity=".6"/>`;
      if (mood === "dormido") {
        o += `<path d="M-48 -4 A14 14 0 0 0 -20 -4 M20 -4 A14 14 0 0 0 48 -4" fill="none" stroke="${ojos}" stroke-width="8" stroke-linecap="round"/>`;
      } else {
        const hh = mood === "sorpresa" ? 19 : 16;
        o += `<g class="ojos"><g transform="translate(-34 -6)"><ellipse rx="10" ry="${hh}" fill="${ojos}"/><circle cx="3" cy="-7" r="4" fill="#fff"/></g>`;
        o += `<g transform="translate(34 -6)"><ellipse rx="10" ry="${hh}" fill="${ojos}"/><circle cx="3" cy="-7" r="4" fill="#fff"/></g></g>`;
      }
      if (mood === "sorpresa") o += `<ellipse cx="0" cy="26" rx="10" ry="12" fill="${ojos}"/>`;
      else if (mood === "serio") o += `<path d="M-12 24 H12" stroke="${ojos}" stroke-width="8" stroke-linecap="round"/>`;
      else o += `<path d="M-15 18 Q0 34 15 18" fill="none" stroke="${ojos}" stroke-width="8" stroke-linecap="round"/>`;
      return o + "</g>";
    },
    /** Destello de 4 puntas. */
    destello(size = 30, color = C.INK, cx = 0, cy = 0) {
      const a = size, b = size * 0.22;
      return `<path d="M${cx} ${cy - a}L${cx + b} ${cy - b}L${cx + a} ${cy}L${cx + b} ${cy + b}L${cx} ${cy + a}L${cx - b} ${cy + b}L${cx - a} ${cy}L${cx - b} ${cy - b}Z" fill="${color}"/>`;
    },
    /** Halo de luz (lo importante brilla); ponlo ANTES de la forma. */
    brillo(r, color = C.CYAN, cx = 0, cy = 0, opacidad = 0.45) {
      const id = nid("g");
      return `<radialGradient id="${id}"><stop offset="0" stop-color="${color}" stop-opacity="${opacidad}"/><stop offset=".45" stop-color="${color}" stop-opacity="${opacidad * 0.35}"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></radialGradient><circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#${id})"/>`;
    },
    /** Rayos radiales detrás de un protagonista. */
    rayos(largo = 700, color = C.BLUE, n = 14, opacidad = 0.16, ancho = 70) {
      const R = rng(3);
      let o = "";
      for (let i = 0; i < n; i++) {
        const ang = (2 * Math.PI * i) / n + (R() - 0.5) * 0.2, L = largo * (0.6 + 0.4 * R()), da = ancho / L;
        o += `<path d="M0 0L${L * Math.cos(ang - da)} ${L * Math.sin(ang - da)}L${L * Math.cos(ang + da)} ${L * Math.sin(ang + da)}Z" fill="${color}" opacity="${opacidad}"/>`;
      }
      return o;
    },
    /** Tubo con volumen por una lista de puntos [[x,y],...] relativos al objeto. */
    tubo(puntos, color = C.MUTED, ancho = 26) {
      const d = "M" + puntos.map((p) => `${p[0]} ${p[1]}`).join("L");
      return `<path class="trazo" d="${d}" fill="none" stroke="${shade(color, -0.35)}" stroke-width="${ancho}" stroke-linecap="round" stroke-linejoin="round"/>` +
        `<path class="trazo ruta" d="${d}" transform="translate(-2 -2)" fill="none" stroke="${color}" stroke-width="${ancho * 0.55}" stroke-linecap="round" stroke-linejoin="round"/>`;
    },
  };

  // ---------- Kit ----------
  function crear(cfg) {
    const LARGO = cfg.formato === "largo";   // horizontal 16:9 para YouTube (igual que LARGO de kit.py)
    if (LARGO) { W = 1920; H = 1080; DESIGN_BOX = [72, 1848, 60, 924]; } else { W = 1080; H = 1920; DESIGN_BOX = [24, 1056, 84, 1560]; }
    const CTA = LARGO ? { ...CTA_TEXT, seguir: "Suscríbete" } : CTA_TEXT;
    const root = document.getElementById("root");
    let DUR = cfg.duracion;   // en horizontal se alarga si la escena sigue (pantalla final de 20 s)
    const durs = cfg.segmentos.map((x) => x.duracion);
    const starts = []; let acc = 0;
    for (const d of durs) { starts.push(acc); acc += d; }

    // encuadre de la zona segura (igual que _safe_framing de kit.py)
    const Z = cfg.zona;   // fracciones arriba/abajo/derecha/izquierda
    const sx0 = Z.izquierda * W, sx1 = W - Z.derecha * W, sy0 = Z.arriba * H, sy1 = H - Z.abajo * H;
    const band = cfg.franja_subtitulos;
    const cy1 = sy1 - band;
    const [x0, x1, y0, y1] = DESIGN_BOX;
    const esc_ = Math.min((sx1 - sx0) / (x1 - x0), (cy1 - sy0) / (y1 - y0));
    const contentC = [(sx0 + sx1) / 2, (sy0 + cy1) / 2], designC = [(x0 + x1) / 2, (y0 + y1) / 2];
    const toScreen = (p) => [contentC[0] + (p[0] - designC[0]) * esc_, contentC[1] + (p[1] - designC[1]) * esc_];
    const captionY = sy1 - band / 2;

    // capas
    const bg = el("div", { id: "bg", class: "capa" }, root);
    const moodEls = {};
    for (const [name, [lo, mid, hi, halo]] of Object.entries(MOODS)) {
      const [r, g, b] = hex(halo);
      moodEls[name] = el("div", { class: "mood", style: `opacity:${name === "noche" ? 1 : 0};background:radial-gradient(circle at 50% 38%, rgba(${r},${g},${b},.26) 0, rgba(${r},${g},${b},.08) 380px, transparent 720px),linear-gradient(to top, ${lo} 0%, ${mid} 55%, ${hi} 100%)` }, bg);
    }
    const mundo = el("div", { id: "mundo", class: "capa" }, root);
    const estrellas = el("svg", { width: W, height: H, class: "capa", style: "overflow:visible" }, mundo, true);
    const encuadre = el("div", { id: "encuadre", class: "capa", style: `transform-origin:0 0;transform:translate(${contentC[0]}px,${contentC[1]}px) scale(${esc_}) translate(${-designC[0]}px,${-designC[1]}px)` }, mundo);
    const ui = el("div", { id: "ui", class: "capa" }, root);

    const tl = gsap.timeline({ paused: true });
    const k = { C, PALETTE, MOODS, s, W, H, LARGO, tl, t: 0, eventos: [], avisos: [], objetos: [], shade, rng };
    const procs = [];          // funciones (t) => void, llamadas en cada cuadro
    const R = rng(cfg.semilla || 7);

    const sfx = (kind, t, gain = 1) => k.eventos.push({ t: +(+t).toFixed(3), kind, gain });
    k.sfx = (kind = "pop", delay = 0, gain = 1) => sfx(kind, k.t + delay, gain);
    k.eventos.push({ t: 0, kind: "layout_safe_frame", gain: 0 });

    // ---------- Fondo: polvo de estrellas en 3 capas (parallax) ----------
    const stars = [];
    for (let i = 0; i < (LARGO ? 170 : 130); i++) {
      const layer = i % 6 < 3 ? 0 : i % 6 < 5 ? 1 : 2;
      const st = { x: R() * (W + 420) - 210, y: R() * (H + 580) - 290, r: [1.6, 2.6, 3.8][layer], ph: R() * 6.28, w: 0.8 + R() * 2.2,
        layer, c: R() < 0.2 ? PALETTE[i % PALETTE.length] : C.INK };
      st.e = el("circle", { r: st.r, fill: st.c }, estrellas, true);
      stars.push(st);
    }
    procs.push((t) => {
      for (const st of stars) {
        const spd = [8, 16, 28][st.layer];
        let y = st.y - t * spd; y = ((y + 290) % (H + 580) + (H + 580)) % (H + 580) - 290;
        st.e.setAttribute("cx", st.x + Math.sin(t * 0.2 + st.ph) * spd * 0.6);
        st.e.setAttribute("cy", y);
        st.e.setAttribute("opacity", ((0.35 + 0.25 * st.layer) * (0.55 + 0.45 * Math.sin(t * st.w + st.ph))).toFixed(3));
      }
    });

    // ---------- Cámara (no bloqueante) ----------
    const cam = { z: [], a: [], p: [], sway: [] };   // tramos {t0, dur, from, to}
    function camVal(list, t, def) {
      let v = def;
      for (const sg of list) {
        if (t < sg.t0) break;
        const u = sg.dur <= 0 ? 1 : clamp((t - sg.t0) / sg.dur, 0, 1);
        v = Array.isArray(sg.from) ? sg.from.map((f, i) => lerp(f, sg.to[i], easeIO(u))) : lerp(sg.from, sg.to, easeIO(u));
      }
      return v;
    }
    const restP = contentC.slice();
    // en horizontal el lienzo es ancho: el mismo giro mueve mucho más los bordes, así que se usa la mitad
    const GIRO = LARGO ? 0.5 : 1;
    k.camSway = (amp = 1.2, period = 7) => { cam.sway.push({ t0: k.t, amp: amp * GIRO, period }); };
    /** Mueve la cámara SIN bloquear: centro (objeto o [x,y] de diseño), zoom (1 = normal) y giro en grados (±10). */
    k.camTo = (target, { zoom, angle, dur = 1.2 } = {}) => {
      const t0 = k.t;
      if (target != null) {
        const p = Array.isArray(target) ? target : target.pos(t0);
        const sp = toScreen(p);
        cam.p.push({ t0, dur, from: camVal(cam.p, t0, restP), to: sp });
      }
      if (zoom != null) cam.z.push({ t0, dur, from: camVal(cam.z, t0, 1), to: zoom });
      if (angle != null) cam.a.push({ t0, dur, from: camVal(cam.a, t0, 0), to: angle * GIRO });
      sfx("woosh", t0, 0.8);
    };
    k.camReset = (dur = 1.0) => k.camTo(restP.map((v, i) => (v - contentC[i]) / esc_ + designC[i]), { zoom: 1, angle: 0, dur });
    procs.push((t) => {
      const z = camVal(cam.z, t, 1), p = camVal(cam.p, t, restP);
      let a = camVal(cam.a, t, 0);
      const sw = cam.sway.filter((x) => x.t0 <= t).pop();
      if (sw) a += sw.amp * Math.sin((2 * Math.PI * (t - sw.t0)) / sw.period);
      // el punto p queda en el centro del contenido, con zoom y giro alrededor de él
      mundo.style.transform = `translate(${contentC[0]}px,${contentC[1]}px) rotate(${a}deg) scale(${z}) translate(${-p[0]}px,${-p[1]}px)`;
    });
    mundo.style.transformOrigin = "0 0";

    // ---------- Moods ----------
    let moodActual = "noche";
    k.mood = (name, dur = 1.2) => {
      if (!MOODS[name] || name === moodActual) return;
      tl.fromTo(moodEls[name], { opacity: 0 }, { opacity: 1, duration: dur, ease: "sine.inOut" }, k.t);
      tl.fromTo(moodEls[moodActual], { opacity: 1 }, { opacity: 0, duration: dur, ease: "sine.inOut" }, k.t);
      moodActual = name;
      sfx("shimmer", k.t, 0.6);
    };

    // ---------- Objetos ----------
    /**
     * Crea un objeto en el lienzo de diseño. contenido: SVG (cadena con formas de k.s) o {html: "..."}.
     * Opciones: x, y (centro), escala, rot (grados), z (orden), ancla ("abajo" | "centro") para pop/squash.
     * Aparece al usarlo en k.popIn (o al instante si visible: true).
     */
    k.obj = (contenido, { x = W / 2, y = H / 2, escala = 1, rot = 0, z = 0, ancla = "abajo", visible = false, opacidad = 1 } = {}) => {
      const pos = el("div", { class: "obj", style: `z-index:${z}` }, encuadre);
      const vida = el("div", { class: "vida" }, pos);
      const cuerpo = el("div", { class: "cuerpo" }, vida);
      let bb = null;
      if (typeof contenido === "string") {
        const sv = el("svg", { width: 1, height: 1, style: "overflow:visible;position:absolute;left:0;top:0" }, cuerpo, true);
        sv.innerHTML = contenido;
        try { bb = contenido ? sv.getBBox() : null; } catch (e) { bb = null; }
      } else if (contenido && contenido.html) {
        const h = el("div", { class: "html" }, cuerpo);
        h.innerHTML = contenido.html;
      }
      const o = { el: pos, vida, cuerpo, st: { x, y, s: escala, r: rot, o: opacidad }, track: [], idles: [], idx: k.objetos.length,
        ancla, visibleDesde: null, salio: null };
      o.track.push({ t0: -1, dur: 0, from: [x, y], to: [x, y], ease: (u) => u });
      o.pos = (t) => {
        let v = [x, y];
        for (const sg of o.track) {
          if (t < sg.t0) break;
          const u = sg.dur <= 0 ? 1 : clamp((t - sg.t0) / sg.dur, 0, 1);
          v = sg.path ? sg.path(sg.ease(u)) : [lerp(sg.from[0], sg.to[0], sg.ease(u)), lerp(sg.from[1], sg.to[1], sg.ease(u))];
        }
        return v;
      };
      gsap.set(pos, { x, y, scale: escala, rotation: rot, opacity: opacidad, visibility: "hidden" });
      // ancla del squash: centro del objeto o su base (el SVG está centrado en el origen del objeto)
      gsap.set(cuerpo, { transformOrigin: ancla === "centro" || !bb ? "0px 0px" : `0px ${(bb.y + bb.height).toFixed(1)}px` });
      o.setX = gsap.quickSetter(pos, "x", "px"); o.setY = gsap.quickSetter(pos, "y", "px");
      o.ojos = Array.from(cuerpo.querySelectorAll(".ojos"));
      o.ojos.forEach((e) => { e.style.transformBox = "fill-box"; e.style.transformOrigin = "50% 50%"; });
      if (visible) mostrar(o, k.t);
      k.objetos.push(o);
      return o;
    };
    function mostrar(o, t) {
      if (o.visibleDesde == null) { o.visibleDesde = t; tl.set(o.el, { visibility: "visible" }, t); }
    }
    function ocultar(o, t) { o.salio = t; tl.set(o.el, { visibility: "hidden" }, t); }
    /** Texto suelto (Fredoka por defecto). Para nombrar partes usa k.pill; para el título, k.titulo. */
    k.texto = (txt, { size = 44, color = C.INK, peso = 700, fuente = "Fredoka", ancho = null, ...opts } = {}) =>
      k.obj({ html: `<div class="txt" style="font:${peso} ${size}px/1.12 '${fuente}';color:${color};${ancho ? `width:${ancho}px;white-space:normal;` : ""}">${esc(txt).replace(/\n/g, "<br/>")}</div>` }, { ancla: "centro", ...opts });
    /** Título grande en mayúsculas (admite \n) con sombra suave. */
    k.titulo = (txt, { size = 78, color = C.INK, ...opts } = {}) =>
      k.obj({ html: `<div class="txt titulo" style="font-size:${size}px;color:${color}">${esc(txt.toUpperCase()).replace(/\n/g, "<br/>")}</div>` }, { ancla: "centro", y: LARGO ? 170 : 230, ...opts });
    /** Etiqueta en cápsula con volumen (nombrar partes; 3-4 palabras máx.). */
    k.pill = (txt, color = C.SUN, { size = 40, colorTexto = null, ...opts } = {}) => {
      const dark = [C.SUN, C.MINT, C.CYAN, C.CORAL, C.INK].includes(color);
      const tc = colorTexto || (dark ? C.BG : C.INK);
      return k.obj({ html: `<div class="txt pill" style="font-size:${size}px;background:${color};color:${tc}">${esc(txt)}</div>` }, { ancla: "centro", ...opts });
    };

    // ---------- Animaciones (devuelven {dur, add(at)}; se usan dentro de k.play) ----------
    const anim = (dur, add) => ({ dur, add });
    /** Entra con squash & stretch y rebote (nunca fade a secas para objetos sólidos). */
    k.popIn = (o, { dur = 0.6 } = {}) => anim(dur, (t) => {
      mostrar(o, t);
      const c = o.cuerpo;
      tl.fromTo(c, { scaleX: 0, scaleY: 0 }, { scaleX: 1.12, scaleY: 1.22, duration: dur * 0.42, ease: "power2.out" }, t);
      tl.fromTo(c, { scaleX: 1.12, scaleY: 1.22 }, { scaleX: 0.93, scaleY: 0.9, duration: dur * 0.25, ease: "sine.inOut" }, t + dur * 0.42);
      tl.fromTo(c, { scaleX: 0.93, scaleY: 0.9 }, { scaleX: 1, scaleY: 1, duration: dur * 0.33, ease: "back.out(2)" }, t + dur * 0.67);
      sfx(o.el.querySelector(".txt") ? "blip" : "pop", t, 1);
    });
    /** Sale con anticipación (crece un poco y se encoge a nada). Para volver, crea el objeto de nuevo. */
    k.exitOut = (o, { dur = 0.45 } = {}) => anim(dur, (t) => {
      const c = o.cuerpo;
      tl.fromTo(c, { scaleX: 1, scaleY: 1 }, { scaleX: 1.1, scaleY: 1.1, duration: dur * 0.3, ease: "sine.out" }, t);
      tl.fromTo(c, { scaleX: 1.1, scaleY: 1.1 }, { scaleX: 0, scaleY: 0, duration: dur * 0.7, ease: "back.in(1.8)" }, t + dur * 0.3);
      ocultar(o, t + dur);
      k.stopIdle(o, t + dur);
      sfx("woosh", t, 0.5);
    });
    /** Gelatina: rebote elástico al llegar o golpear (follow-through). */
    k.jelly = (o, { cantidad = 0.18, dur = 0.8 } = {}) => anim(dur, (t) => {
      const c = o.cuerpo, n = 6;
      let prev = [1, 1];
      for (let i = 1; i <= n; i++) {
        const u = i / n, a = cantidad * Math.sin(u * Math.PI * 3) * Math.exp(-u * 3);
        const nx = [1 + a, 1 - a];
        tl.fromTo(c, { scaleX: prev[0], scaleY: prev[1] }, { scaleX: i === n ? 1 : nx[0], scaleY: i === n ? 1 : nx[1], duration: dur / n, ease: "sine.inOut" }, t + (dur * (i - 1)) / n);
        prev = nx;
      }
      sfx("thud", t, 0.5);
    });
    /** Exageración: crece con resorte y vuelve (el dato sorprendente). */
    k.emphasize = (o, { escala = 1.25, dur = 0.7 } = {}) => anim(dur, (t) => {
      const c = o.cuerpo;
      tl.fromTo(c, { scaleX: 1, scaleY: 1 }, { scaleX: escala, scaleY: escala, duration: dur * 0.4, ease: "back.out(3)" }, t);
      tl.fromTo(c, { scaleX: escala, scaleY: escala }, { scaleX: 1, scaleY: 1, duration: dur * 0.6, ease: "elastic.out(1, .45)" }, t + dur * 0.4);
      sfx("blip", t, 1);
    });
    /** Salto con anticipación (se agacha), estirón en el aire y aplastón al caer. */
    k.squashBounce = (o, { alto = 100, dur = 0.9 } = {}) => anim(dur, (t) => {
      const c = o.cuerpo, v = o.vida;
      tl.fromTo(c, { scaleX: 1, scaleY: 1 }, { scaleX: 1.18, scaleY: 0.8, duration: dur * 0.18, ease: "sine.out" }, t);
      tl.fromTo(c, { scaleX: 1.18, scaleY: 0.8 }, { scaleX: 0.88, scaleY: 1.16, duration: dur * 0.16, ease: "sine.out" }, t + dur * 0.18);
      tl.fromTo(c, { scaleX: 0.88, scaleY: 1.16 }, { scaleX: 1, scaleY: 1, duration: dur * 0.3, ease: "sine.inOut" }, t + dur * 0.34);
      tl.fromTo(c, { y: 0 }, { y: -alto, duration: dur * 0.32, ease: "power2.out" }, t + dur * 0.18);
      tl.fromTo(c, { y: -alto }, { y: 0, duration: dur * 0.3, ease: "power2.in" }, t + dur * 0.5);
      tl.fromTo(c, { scaleX: 1, scaleY: 1 }, { scaleX: 1.22, scaleY: 0.8, duration: dur * 0.08, ease: "sine.out" }, t + dur * 0.8);
      tl.fromTo(c, { scaleX: 1.22, scaleY: 0.8 }, { scaleX: 1, scaleY: 1, duration: dur * 0.12, ease: "back.out(2)" }, t + dur * 0.88);
      sfx("thud", t + dur * 0.82, 1);
    });
    function moveTo(o, t, dur, to, ease, path) {
      const from = o.pos(t);
      const ez = typeof ease === "function" ? ease : gsap.parseEase(ease || "power2.inOut");
      // la posición se calcula con o.pos(t) en cada cuadro (así otras cosas pueden seguirla)
      o.track.push({ t0: t, dur, from, to, ease: ez, path });
      o.st.x = to[0]; o.st.y = to[1];
    }
    /** Movimiento general: {x, y, escala, rot, opacidad, dur, ease}. */
    k.mover = (o, { x, y, escala, rot, opacidad, dur = 0.8, ease = "power2.inOut" } = {}) => anim(dur, (t) => {
      if (x != null || y != null) moveTo(o, t, dur, [x ?? o.st.x, y ?? o.st.y], ease);
      const from = { scale: o.st.s, rotation: o.st.r, opacity: o.st.o }, to = { ...from };
      if (escala != null) { to.scale = escala; o.st.s = escala; }
      if (rot != null) { to.rotation = rot; o.st.r = rot; }
      if (opacidad != null) { to.opacity = opacidad; o.st.o = opacidad; }
      tl.fromTo(o.el, from, { ...to, duration: dur, ease }, t);
    });
    /** Se echa para atrás, sale disparado, se pasa y se asienta. */
    k.anticipateMove = (o, [x, y], { dur = 0.9 } = {}) => anim(dur, (t) => {
      moveTo(o, t, dur, [x, y], (u) => anticipateOvershoot(u));
      sfx("woosh", t + dur * 0.25, 1);
    });
    /** Viaja en arco (no en recta). angulo en grados (+ = curva hacia arriba). */
    k.moveArc = (o, [x, y], { angulo = 60, dur = 0.9, ease = "power2.inOut" } = {}) => anim(dur, (t) => {
      const [ax, ay] = o.pos(t), mx = (ax + x) / 2, my = (ay + y) / 2;
      const dx = x - ax, dy = y - ay, L = Math.hypot(dx, dy) || 1;
      const h = (Math.tan(((angulo * Math.PI) / 180) / 2) * L) / 2;
      const cx = mx + (dy / L) * h, cy = my - (dx / L) * h;   // control de la curva
      moveTo(o, t, dur, [x, y], ease, (u) => [(1 - u) * (1 - u) * ax + 2 * (1 - u) * u * cx + u * u * x, (1 - u) * (1 - u) * ay + 2 * (1 - u) * u * cy + u * u * y]);
      sfx("woosh", t + dur * 0.05, 1);
    });
    /** Gira el objeto (grados, relativo). */
    k.rotar = (o, grados, { dur = 0.6, ease = "back.inOut(1.6)" } = {}) => anim(dur, (t) => {
      tl.fromTo(o.el, { rotation: o.st.r }, { rotation: o.st.r + grados, duration: dur, ease }, t);
      o.st.r += grados;
    });
    /** Dibuja los trazos (.trazo) de un objeto: tubos, flechas, líneas. */
    k.drawIn = (o, { dur = 1.0 } = {}) => anim(dur, (t) => {
      mostrar(o, t);
      const ps = o.el.querySelectorAll(".trazo");
      (ps.length ? ps : o.el.querySelectorAll("path[stroke], line, polyline")).forEach((p) => {
        const L = p.getTotalLength ? Math.max(p.getTotalLength(), 1) : 1000;
        tl.fromTo(p, { attr: { "stroke-dasharray": L, "stroke-dashoffset": L } }, { attr: { "stroke-dashoffset": 0 }, duration: dur, ease: "power2.inOut" }, t);
      });
      sfx("woosh", t, 0.5);
    });
    /** Aparece/desaparece con opacidad (solo halos, rayos, luces; los objetos sólidos usan popIn/exitOut). */
    k.fadeIn = (o, { dur = 0.5 } = {}) => anim(dur, (t) => { mostrar(o, t); tl.fromTo(o.cuerpo, { opacity: 0 }, { opacity: 1, duration: dur }, t); });
    k.fadeOut = (o, { dur = 0.5 } = {}) => anim(dur, (t) => { tl.fromTo(o.cuerpo, { opacity: 1 }, { opacity: 0, duration: dur }, t); ocultar(o, t + dur); });
    /** Cambia el atributo de un elemento interno (selector CSS) del objeto: p. ej. color de un path con clase. */
    const lastAttr = new WeakMap();
    k.attr = (o, selector, attrs, { dur = 0.5, ease = "sine.inOut" } = {}) => anim(dur, (t) => {
      o.el.querySelectorAll(selector).forEach((e) => {
        const prev = lastAttr.get(e) || {}, from = {};
        for (const a in attrs) from[a] = a in prev ? prev[a] : e.getAttribute(a);
        tl.fromTo(e, { attr: from }, { attr: attrs, duration: dur, ease }, t);
        lastAttr.set(e, { ...prev, ...attrs });
      });
    });
    /** Varios objetos entran escalonados (overlapping action). */
    k.cascada = (objs, { anim: fn = (o) => k.popIn(o), lag = 0.15 } = {}) => {
      const parts = objs.map((o) => fn(o));
      const dur = parts.reduce((m, p, i) => Math.max(m, i * lag + p.dur), 0);
      return anim(dur, (t) => parts.forEach((p, i) => p.add(t + i * lag)));
    };
    /** Espera dur segundos y luego hace la animación (para secuencias dentro de un play). */
    k.despues = (dur, a) => anim(dur + a.dur, (t) => a.add(t + dur));
    /** Agrega las animaciones en paralelo en el cursor y lo avanza lo que dure la más larga. */
    k.play = (...anims) => {
      let m = 0;
      for (const a of anims.flat()) { if (!a) continue; a.add(k.t); m = Math.max(m, a.dur); }
      k.t += m;
    };
    k.wait = (sec) => { k.t += Math.max(0, sec); };

    // ---------- Vida constante (calculada por cuadro, desde el cursor) ----------
    function idle(o, kind, params) { o.idles.push({ kind, t0: k.t, t1: Infinity, ...params, ph: R() * 6.28 }); mostrar(o, k.t); return o; }
    k.idleFloat = (o, { amp = 10, period = 3.2 } = {}) => idle(o, "float", { amp, period });
    k.idlePulse = (o, { amp = 0.05, period = 1.4 } = {}) => idle(o, "pulse", { amp, period });
    k.idleBreathe = (o, { amp = 0.03, period = 2.6 } = {}) => idle(o, "breathe", { amp, period });
    k.idleWiggle = (o, { deg = 4, period = 1.8 } = {}) => idle(o, "wiggle", { deg, period });
    k.idleSpin = (o, { vueltasPorS = 0.25 } = {}) => idle(o, "spin", { v: vueltasPorS });
    /** float + pulso (por defecto), o "wiggle" | "breathe" | "spin". */
    k.alive = (o, estilo = "float") => {
      if (estilo === "wiggle") return k.idleWiggle(o);
      if (estilo === "breathe") return k.idleBreathe(o);
      if (estilo === "spin") return k.idleSpin(o);
      k.idleFloat(o, { amp: 9, period: 2.6 + R() });
      return k.idlePulse(o, { amp: 0.025, period: 1.6 + R() * 0.8 });
    };
    /** Detiene la vida constante (antes de moverlo con otra animación de cuerpo). */
    k.stopIdle = (o, t = k.t) => { for (const i of o.idles) if (i.t1 === Infinity) i.t1 = t; };
    procs.push((t) => {
      for (const o of k.objetos) {
        let dx = 0, dy = 0, sx = 1, sy = 1, rot = 0;
        for (const i of o.idles) {
          if (t < i.t0) continue;
          const tt = Math.min(t, i.t1) - i.t0;
          const fade = t > i.t1 ? 0 : 1;
          const w = (2 * Math.PI) / (i.period || 1);
          if (i.kind === "float") dy += fade * i.amp * Math.sin(tt * w + i.ph);
          else if (i.kind === "pulse") { const v = 1 + fade * i.amp * Math.sin(tt * w + i.ph); sx *= v; sy *= v; }
          else if (i.kind === "breathe") { const v = i.amp * Math.sin(tt * w + i.ph) * fade; sx *= 1 - v * 0.6; sy *= 1 + v; }
          else if (i.kind === "wiggle") rot += fade * i.deg * Math.sin(tt * w + i.ph);
          else if (i.kind === "spin") rot += 360 * i.v * tt;   // el giro acumulado se conserva al detenerlo
        }
        const [px, py] = o.pos(t);
        o.setX(px); o.setY(py);
        o.vida.style.transform = `translate(${dx}px,${dy}px) rotate(${rot}deg) scale(${sx},${sy})`;
        if (o.ojos.length) {
          const u = (t + o.idx * 1.37) % (2.6 + (o.idx % 3) * 0.5);
          const b = u < 0.14 ? Math.max(0.08, Math.abs(1 - u / 0.07)) : 1;
          for (const e of o.ojos) e.style.transform = `scaleY(${b})`;
        }
      }
    });

    /** Animación continua propia: fn(t) se llama en cada cuadro con el tiempo del video (determinista). */
    k.cadaCuadro = (fn) => { procs.push(fn); };

    // ---------- Partículas (deterministas) ----------
    const PCOL = { chispas: [C.SUN, C.CORAL, C.INK], burbujas: [C.CYAN, C.INK], calor: [C.CORAL, C.SUN, C.PINK],
      estrellas: [C.INK, C.SUN, C.CYAN], confeti: PALETTE, frio: [C.CYAN, C.INK, C.BLUE], orbita: [C.CYAN, C.VIOLET, C.MINT],
      polvo: [C.INK, C.MUTED, C.VIOLET] };
    /**
     * Sistema de partículas vivo: tipo chispas | burbujas | calor | estrellas | confeti | frio | orbita | polvo.
     * {x, y, w, h, n, sigue: obj, colores, tam}. Se quita con k.exitOut(p) o k.fadeOut(p).
     */
    k.particulas = (tipo = "polvo", { x = W / 2, y = LARGO ? 480 : 900, w = 400, h = 400, n = 30, sigue = null, colores = null, tam = 1, z = 5 } = {}) => {
      const P = rng(Math.floor(R() * 1e9));
      const cols = colores || PCOL[tipo] || PALETTE;
      const o = k.obj("", { x, y, z, ancla: "centro", visible: true });
      if (sigue) o.pos = (t) => sigue.pos(t);
      const svg = o.cuerpo.querySelector("svg");
      const ps = [];
      for (let i = 0; i < n; i++) {
        const c = cols[Math.floor(P() * cols.length)];
        let e;
        if (tipo === "burbujas") e = el("circle", { r: (7 + P() * 12) * tam, fill: C.CYAN, "fill-opacity": 0.12, stroke: c, "stroke-width": 3 }, svg, true);
        else if (tipo === "estrellas") { e = el("g", {}, svg, true); e.innerHTML = s.destello((8 + P() * 12) * tam, c); }
        else if (tipo === "confeti") e = el("rect", { x: -5 * tam, y: -10 * tam, width: 10 * tam, height: 20 * tam, rx: 2, fill: c }, svg, true);
        else {
          const rad = { chispas: [4, 7], calor: [5, 11], frio: [4, 8], orbita: [6, 11], polvo: [2, 5] }[tipo] || [4, 7];
          e = el("circle", { r: (rad[0] + P() * (rad[1] - rad[0])) * tam, fill: c }, svg, true);
        }
        ps.push({ e, a: P(), b: P(), c: P(), d: P(), life: tipo === "chispas" ? 0.4 + P() * 0.5 : tipo === "polvo" ? 2 + P() * 3 :
          ["burbujas", "calor", "confeti", "frio"].includes(tipo) ? 0 : 1e9, sp: 0.6 + P() * 0.9 });
      }
      const t0 = k.t;
      if (["chispas", "confeti", "estrellas", "orbita"].includes(tipo)) sfx("shimmer", t0, 0.7);
      procs.push((t) => {
        if (o.salio != null && t > o.salio) return;
        const tt = Math.max(t - t0, 0);
        for (const p of ps) {
          let px = 0, py = 0, op = 1, rot = 0;
          if (tipo === "chispas") {
            const u = (tt + p.a * p.life) % p.life, ang = p.b * 6.283, v = 180 + p.c * 220;
            px = Math.cos(ang) * v * u; py = -(Math.sin(ang) * v + 120) * u + 0.5 * 480 * u * u; op = 1 - u / p.life;
          } else if (["burbujas", "calor", "confeti", "frio"].includes(tipo)) {
            const vy = tipo === "confeti" ? 200 + p.c * 170 : tipo === "frio" ? 50 + p.c * 60 : tipo === "burbujas" ? 70 + p.c * 90 : 100 + p.c * 110;
            const life = h / vy, u = (tt + p.a * life) % life;
            const down = tipo === "confeti" || tipo === "frio";
            px = (p.b - 0.5) * w + 30 * Math.sin(u * 3 + p.d * 6.28);
            py = down ? -h / 2 + vy * u : h / 2 - vy * u;
            const f = u / life; op = tipo === "confeti" ? (f < 0.85 ? 1 : (1 - f) / 0.15) : Math.sin(Math.PI * f);
            rot = tipo === "confeti" ? tt * 170 * (p.d > 0.5 ? 1 : -1) : 0;
          } else if (tipo === "orbita") {
            const rr = (0.5 + 0.5 * p.a) * Math.min(w, h) / 2, ang = p.b * 6.283 + tt * (0.8 + p.c * 1.2) * (p.d > 0.5 ? 1 : -1);
            px = rr * Math.cos(ang); py = rr * Math.sin(ang) * 0.55; op = 0.9;
          } else if (tipo === "estrellas") {
            px = (p.a - 0.5) * w; py = (p.b - 0.5) * h; op = 0.25 + 0.75 * Math.abs(Math.sin(tt * 1.7 + p.c * 6.28)); rot = tt * 40;
          } else {  // polvo
            const u = (tt + p.a * p.life) % p.life;
            px = (p.b - 0.5) * w + (p.c - 0.5) * 40 * u; py = (p.d - 0.5) * h - 40 * u; op = Math.sin((Math.PI * u) / p.life) * 0.8;
          }
          p.e.setAttribute("transform", `translate(${px.toFixed(1)} ${py.toFixed(1)}) rotate(${rot.toFixed(1)})`);
          p.e.setAttribute("opacity", Math.max(op, 0).toFixed(3));
        }
      });
      return o;
    };
    /** Puntos que fluyen por la ruta (.ruta) de un objeto hecho con k.s.tubo (corriente, refrigerante, sangre). */
    k.flujo = (tuboObj, { n = 8, color = C.CYAN, r = 8, vel = 0.5 } = {}) => {
      const path = tuboObj.el.querySelector(".ruta");
      const svg = tuboObj.cuerpo.querySelector("svg");
      const dots = Array.from({ length: n }, () => el("circle", { r, fill: color }, svg, true));
      const L = path.getTotalLength(), t0 = k.t;
      mostrar(tuboObj, t0);
      procs.push((t) => {
        const vis = t >= t0 && (tuboObj.salio == null || t < tuboObj.salio);
        dots.forEach((d, i) => {
          if (!vis) { d.setAttribute("opacity", 0); return; }
          const u = (((t - t0) * vel + i / n) % 1 + 1) % 1, p = path.getPointAtLength(u * L);
          d.setAttribute("cx", p.x); d.setAttribute("cy", p.y); d.setAttribute("opacity", 1);
        });
      });
      return tuboObj;
    };

    // ---------- Staging ----------
    const enEscena = (t) => k.objetos.filter((o) => o.visibleDesde != null && o.visibleDesde <= t && (o.salio == null || o.salio > t));
    /** Apaga todo menos lo que importa. */
    k.dimOthers = (keep, { opacidad = 0.2, dur = 0.5 } = {}) => {
      const ks = [].concat(keep);
      return anim(dur, (t) => enEscena(t).filter((o) => !ks.includes(o)).forEach((o) => {
        tl.fromTo(o.el, { opacity: o.st.o }, { opacity: opacidad, duration: dur }, t); o.st.o = opacidad;
      }));
    };
    /** Vuelve a encender todo. */
    k.undim = ({ dur = 0.4 } = {}) => anim(dur, (t) => enEscena(t).forEach((o) => {
      if (o.st.o !== 1) { tl.fromTo(o.el, { opacity: o.st.o }, { opacity: 1, duration: dur }, t); o.st.o = 1; }
    }));
    /** Saca todo con anticipación y en cascada (bloquea). */
    k.clearStage = ({ dur = 0.7 } = {}) => {
      const ms = enEscena(k.t);
      if (!ms.length) return;
      const lag = Math.min(0.05, (dur * 0.4) / ms.length);
      k.play(k.cascada(ms, { anim: (o) => k.exitOut(o, { dur: dur - lag * (ms.length - 1) }), lag }));
    };

    // ---------- Subtítulos, CTA, capítulos, cierre ----------
    const capsDiv = el("div", { class: "subs" }, ui);
    function chunks(text, per = cfg.caracteres_por_linea || 22) {
      const lines = []; let cur = "";
      for (const w of text.split(/\s+/).filter(Boolean)) {
        if (cur && cur.length + w.length + 1 > per) { lines.push(cur); cur = w; } else cur = (cur + " " + w).trim();
      }
      if (cur) lines.push(cur);
      const out = [];
      for (let i = 0; i < lines.length; i += 2) out.push(lines.slice(i, i + 2));
      return out;
    }
    function captions(i) {
      const t0 = starts[i], d = durs[i], cs = chunks(cfg.segmentos[i].texto);
      const wts = cs.map((c) => c.join("").length + 6), tot = wts.reduce((a, b) => a + b, 0) || 1;
      let a = t0;
      cs.forEach((c, ci) => {
        const dd = (d * wts[ci]) / tot;
        const div = el("div", { class: "sub txt", style: `top:${captionY}px;left:${sx0}px;width:${sx1 - sx0}px` }, capsDiv);
        div.innerHTML = c.map(esc).join("<br/>");
        tl.set(div, { visibility: "visible" }, a);
        tl.fromTo(div, { yPercent: -50, scale: 0.88 }, { scale: 1, duration: 0.2, ease: "back.out(2)" }, a);
        tl.set(div, { visibility: "hidden" }, Math.min(a + dd, DUR - 0.001));
        a += dd;
      });
    }
    const ICONS = {
      guardar: `<path d="M-19 -27 H19 V27 L0 9 L-19 27Z" fill="${C.SUN}" stroke="#000" stroke-width="3" stroke-linejoin="round"/>`,
      comentar: `<rect x="-28" y="-22" width="56" height="40" rx="13" fill="${C.CYAN}"/><path d="M-16 16 L-4 16 L-22 32Z" fill="${C.CYAN}"/><circle cx="-13" cy="-2" r="4" fill="${C.BG}"/><circle cx="0" cy="-2" r="4" fill="${C.BG}"/><circle cx="13" cy="-2" r="4" fill="${C.BG}"/>`,
      compartir: `<path d="M-26 20 L6 -2 L6 10 Z" fill="${C.MINT}"/><path d="M3 -24 L30 0 L3 24Z" fill="${C.MINT}"/><rect x="-22" y="-8" width="30" height="12" fill="${C.MINT}" transform="rotate(34 -8 -2)"/>`,
      like: `<circle cx="-10" cy="-6" r="13" fill="${C.PINK}"/><circle cx="10" cy="-6" r="13" fill="${C.PINK}"/><path d="M-22 -2 H22 L0 24Z" fill="${C.PINK}"/>`,
      seguir: `<path d="M-18 6 V-6 A18 18 0 0 1 18 -6 V6 Z" fill="${C.VIOLET}"/><rect x="-25" y="5" width="50" height="8" rx="4" fill="${C.VIOLET}"/><circle cy="20" r="5" fill="${C.VIOLET}"/>`,
    };
    /** Ícono de llamado a la acción sobre los subtítulos; guardar/comentar/compartir/like llevan flecha a los botones. */
    function cta(kind, t, dur) {
      const y = captionY - band / 2 - 66, x = (sx0 + sx1) / 2;
      const box = el("div", { class: "cta", style: `left:${x}px;top:${y}px` }, ui);
      box.innerHTML = `<div class="badge txt"><svg width="64" height="64" viewBox="-32 -32 64 64">${ICONS[kind] || ICONS.seguir}</svg><span>${esc(CTA[kind] || kind)}</span></div>`;
      tl.set(box, { visibility: "visible" }, t);
      tl.fromTo(box, { xPercent: -50, yPercent: -50, scale: 0, rotation: -10 }, { scale: 1, rotation: 0, duration: 0.6, ease: "elastic.out(1.1, .5)" }, t);
      tl.fromTo(box, { scale: 1 }, { scale: 0, duration: 0.3, ease: "back.in(2)", immediateRender: false }, t + dur - 0.3);
      tl.set(box, { visibility: "hidden" }, t + dur);
      sfx(`cta_${kind}`, t, 0); sfx("pop", t, 1); sfx("blip", t + 0.15, 1);
      if (LARGO) return ctaFlechaAbajo(kind, x, y, t, dur);
      if (!["guardar", "comentar", "compartir", "like"].includes(kind)) return;
      // flecha: anticipación, disparo con rebote y empujoncitos hacia la columna de botones (derecha)
      const btnY = cfg.botones_altura * H, endX = W - 66;
      const svg = el("svg", { width: W, height: H, class: "capa flecha", style: "overflow:visible" }, ui, true);
      const g = el("g", {}, svg, true);
      const label = CTA[kind] || kind;
      const startX = x + (64 + 22 + 62 + label.length * 21) / 2 + 18;   // borde derecho del ícono + aire
      g.innerHTML = `<line x1="0" y1="0" x2="1" y2="0" stroke="${C.SUN}" stroke-width="16" stroke-linecap="round"/><path d="M-12 -26 L34 0 L-12 26Z" fill="${C.SUN}" stroke="${C.SUN}" stroke-width="8" stroke-linejoin="round"/>`;
      const line = g.querySelector("line"), head = g.querySelector("path");
      const st = { u: 0, n: 0 };
      const paint = () => {
        const sx = startX, sy = (y + btnY) / 2;
        const ex = endX - 34 + st.n, ey = btnY;
        const tipx = sx + (ex - sx) * st.u, tipy = sy + (ey - sy) * st.u;
        const ang = (Math.atan2(ey - sy, ex - sx) * 180) / Math.PI;
        line.setAttribute("x1", sx); line.setAttribute("y1", sy); line.setAttribute("x2", tipx); line.setAttribute("y2", tipy);
        head.setAttribute("transform", `translate(${tipx} ${tipy}) rotate(${ang}) scale(${clamp(st.u * 3, 0, 1)})`);
      };
      const proxy = {};
      Object.defineProperty(proxy, "u", { get: () => st.u, set: (v) => { st.u = v; paint(); } });
      Object.defineProperty(proxy, "n", { get: () => st.n, set: (v) => { st.n = v; paint(); } });
      paint();
      tl.set(svg, { visibility: "visible", opacity: 1 }, t + 0.25);
      tl.fromTo(proxy, { u: 0 }, { u: 1, duration: 0.6, ease: (u) => anticipateOvershoot(u) }, t + 0.25);
      for (let q = 0; q < Math.floor((dur - 1.3) / 0.45); q++)
        tl.fromTo(proxy, { n: 0 }, { n: 18, duration: 0.16, ease: "sine.out", yoyo: true, repeat: 1 }, t + 1.0 + q * 0.45);
      tl.fromTo(svg, { opacity: 1 }, { opacity: 0, duration: 0.3, immediateRender: false }, t + dur - 0.3);
      tl.set(svg, { visibility: "hidden" }, t + dur);
    }
    /** Horizontal: los botones están bajo el reproductor → flecha que rebota hacia abajo junto al ícono. */
    function ctaFlechaAbajo(kind, x, y, t, dur) {
      if (!["guardar", "comentar", "compartir", "like", "seguir"].includes(kind)) return;
      const label = CTA[kind] || kind;
      const ax = x + (64 + 22 + 62 + label.length * 21) / 2 + 40, top = y - 34;
      const svg = el("svg", { width: W, height: H, class: "capa flecha", style: "overflow:visible" }, ui, true);
      const g = el("g", {}, svg, true);
      g.innerHTML = `<line x1="0" y1="0" x2="0" y2="1" stroke="${C.SUN}" stroke-width="14" stroke-linecap="round"/><path d="M-22 -10 L0 30 L22 -10Z" fill="${C.SUN}" stroke="${C.SUN}" stroke-width="8" stroke-linejoin="round"/>`;
      const line = g.querySelector("line"), head = g.querySelector("path");
      const st = { u: 0, b: 0 };
      const paint = () => {
        const bot = top + (36 + st.b) * st.u;
        line.setAttribute("x1", ax); line.setAttribute("x2", ax); line.setAttribute("y1", top); line.setAttribute("y2", bot);
        head.setAttribute("transform", `translate(${ax} ${bot}) scale(${clamp(st.u * 3, 0, 1)})`);
      };
      const proxy = {};
      Object.defineProperty(proxy, "u", { get: () => st.u, set: (v) => { st.u = v; paint(); } });
      Object.defineProperty(proxy, "b", { get: () => st.b, set: (v) => { st.b = v; paint(); } });
      paint();
      tl.set(svg, { visibility: "visible", opacity: 1 }, t + 0.25);
      tl.fromTo(proxy, { u: 0 }, { u: 1, duration: 0.45, ease: "back.out(2.5)" }, t + 0.25);
      for (let q = 0; q < Math.floor((dur - 1.0) / 0.4); q++)
        tl.fromTo(proxy, { b: 0 }, { b: 18, duration: 0.2, ease: "sine.out", yoyo: true, repeat: 1 }, t + 0.7 + q * 0.4);
      tl.fromTo(svg, { opacity: 1 }, { opacity: 0, duration: 0.3, immediateRender: false }, t + dur - 0.3);
      tl.set(svg, { visibility: "hidden" }, t + dur);
    }
    /** Mini-título de capítulo (entra, se queda y sale, bloquea): ≈1.2 s en vertical; en horizontal ≈1.8 s con
     *  «CAPÍTULO N» encima (es la pausa natural donde YouTube puede poner un anuncio). */
    k.chapter = (titulo, { color = C.VIOLET, numero = null } = {}) => {
      const [cx, cy] = designC;
      const p = k.pill(titulo, color, { size: LARGO ? 76 : 54, colorTexto: C.INK, x: cx, y: LARGO ? cy + 20 : cy - 360, z: 50 });
      const n = LARGO && numero != null
        ? k.texto(`CAPÍTULO ${numero}`, { size: 40, color: C.MUTED, x: cx, y: cy - 70, z: 50 }) : null;
      sfx("chapter", k.t, 0);
      k.play(k.popIn(p, { dur: 0.5 }), ...(n ? [k.despues(0.1, k.popIn(n, { dur: 0.45 }))] : []));
      k.wait(LARGO ? 0.9 : 0.35);
      k.play(k.exitOut(p, { dur: 0.35 }), ...(n ? [k.exitOut(n, { dur: 0.35 })] : []));
    };
    /** Pantalla final de YouTube (solo horizontal): logo y mensaje en la mitad izquierda; la derecha queda libre
     *  para los elementos de YouTube Studio (video sugerido y suscribirse), con guías suaves. Dura `dur` s (bloquea). */
    k.endScreen = (dur = 20, mensaje = "¡Gracias por ver!") => {
      if (!LARGO) throw new Error("k.endScreen es solo para el video largo horizontal; en vertical usa k.outro()");
      const cx = W * 0.27, cy = H * 0.46;
      sfx("end_screen", k.t, 0);
      const halo = k.obj(s.brillo(380, C.VIOLET, 0, 0, 0.35), { x: cx, y: cy - 30, ancla: "centro", z: 40 });
      const l1 = k.texto("FACTOS", { size: 150, x: cx, y: cy - 90, z: 41 });
      const l2 = k.texto("DIDÁCTICOS", { size: 100, color: C.SUN, x: cx, y: cy + 30, z: 41 });
      const sub = k.texto(mensaje, { size: 46, color: C.MUTED, peso: 500, x: cx, y: cy + 130, z: 41 });
      const gx = W * 0.73;
      const guias = k.obj(`<rect x="-336" y="-250" width="672" height="378" rx="24" fill="rgba(0,0,0,.18)" stroke="${C.INK}" stroke-opacity=".25" stroke-width="3"/>`
        + `<circle cx="0" cy="${128 + 40 + 114}" r="114" fill="rgba(0,0,0,.18)" stroke="${C.INK}" stroke-opacity=".25" stroke-width="3"/>`,
        { x: gx, y: H * 0.42, ancla: "centro", z: 39 });
      k.particulas("estrellas", { x: W / 2, y: H / 2, w: W, h: H, n: 40, z: 38 });
      sfx("pop", k.t + 0.1, 1);
      k.play(k.fadeIn(halo, { dur: 0.4 }), k.popIn(l1, { dur: 0.8 }), k.despues(0.15, k.popIn(l2, { dur: 0.7 })),
        k.fadeIn(sub, { dur: 0.6 }), k.fadeIn(guias, { dur: 0.8 }));
      k.idlePulse(l1, { amp: 0.02, period: 1.8 }); k.idlePulse(l2, { amp: 0.02, period: 1.8 });
      k.wait(Math.max(dur - 0.8, 0.1));
    };
    /** Cierre de marca con confeti (≈1.2 s). Llámalo al final del último segmento, después de k.clearStage(). */
    k.outro = () => {
      const [cx, cy] = designC;
      const halo = k.obj(s.brillo(430, C.VIOLET, 0, 0, 0.4), { x: cx, y: cy - 40, ancla: "centro", z: 40 });
      const l1 = k.texto("FACTOS", { size: 150, x: cx, y: cy - 110, z: 41 });
      const l2 = k.texto("DIDÁCTICOS", { size: 104, color: C.SUN, x: cx, y: cy + 10, z: 41 });
      const sub = k.texto("ciencia de todos los días", { size: 48, color: C.MUTED, peso: 500, x: cx, y: cy + 110, z: 41 });
      k.particulas("confeti", { x: cx, y: cy - 200, w: 1000, h: 1400, n: 60, z: 42 });
      sfx("pop", k.t + 0.1, 1); sfx("pop", k.t + 0.35, 0.8);
      k.play(k.fadeIn(halo, { dur: 0.3 }), k.popIn(l1, { dur: 0.8 }), k.despues(0.15, k.popIn(l2, { dur: 0.7 })), k.despues(0.3, k.popIn(sub, { dur: 0.6 })));
      k.idlePulse(l1, { amp: 0.02, period: 1.6 }); k.idlePulse(l2, { amp: 0.02, period: 1.6 });
    };

    // ---------- Segmentos ----------
    k.duraciones = durs.slice();
    k.inicios = starts.slice();
    /** Bloque de un segmento: el cursor arranca exacto donde empieza su audio. fn(d) recibe la duración. */
    k.segmento = (i, opts, fn) => {
      if (typeof opts === "function") { fn = opts; opts = {}; }
      if (i < 0 || i >= durs.length) throw new Error(`segmento ${i} no existe (hay ${durs.length})`);
      const t0 = starts[i], d = durs[i];
      if (k.t > t0 + 0.05) k.avisos.push(`el segmento ${i - 1} se pasó ${(k.t - t0).toFixed(2)} s de su audio`);
      k.t = t0;
      if (opts && opts.mood) k.mood(opts.mood);
      fn(d);
      if (!LARGO && k.t > t0 + d + 0.05 && i === durs.length - 1) k.avisos.push(`el último segmento se pasó ${(k.t - t0 - d).toFixed(2)} s`);
      k.t = Math.max(k.t, t0 + d);
    };

    k._finalizar = () => {
      // video largo: el capítulo dura lo que dure más, la voz o la animación (la voz se rellena con silencio);
      // así la pantalla final de 20 s no se corta cuando la narración del cierre es más corta
      if (LARGO && k.t > DUR + 0.05) DUR = +k.t.toFixed(3);
      durs.forEach((_, i) => captions(i));
      cfg.segmentos.forEach((sg, i) => {
        if (!sg.cta) return;
        const d = durs[i];
        cta(sg.cta, starts[i] + Math.max(d * 0.35, 0.3), Math.min(2.8, Math.max(1.8, d * 0.6)));
      });
      // reloj: GSAP escribe «t» en cada seek y el setter dibuja la parte procedural
      const clock = {}; let _t = -1;
      Object.defineProperty(clock, "t", { get: () => _t, set: (v) => { _t = v; for (const f of procs) f(v); } });
      tl.fromTo(clock, { t: 0 }, { t: DUR, duration: DUR, ease: "none" }, 0);
      k.eventos.sort((a, b) => a.t - b.t);
      window.__factos = { eventos: k.eventos, avisos: k.avisos, duracion: DUR,
        zona: { x0: sx0, x1: sx1, y0: sy0, y1: sy1 }, seek: (t) => tl.seek(t, false),
        zoom: (t) => camVal(cam.z, t, 1) };
      return tl;
    };
    return k;
  }

  window.Factos = { crear, C, PALETTE, MOODS, s };
})();
