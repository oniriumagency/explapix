// Abre la composición en Chrome (sin renderizar), lee los eventos de sonido/CTA del kit y revisa que todo
// texto visible quede dentro de la zona segura de config/reglas.yaml a lo largo del video.
//   node inspeccionar.mjs <carpeta_proyecto> <chrome> [paso_s]
// Imprime un JSON: {ok, error, eventos, avisos, fuera: [{t, texto, borde}]}
import { pathToFileURL } from "node:url";
import path from "node:path";
import { readFileSync } from "node:fs";
import puppeteer from "puppeteer-core";

const [dir, chrome, pasoArg] = process.argv.slice(2);
const paso = Number(pasoArg || 0.25);
const out = { ok: false, error: null, eventos: [], avisos: [], fuera: [] };
let browser;
try {
  browser = await puppeteer.launch({ executablePath: chrome, headless: true,
    args: ["--no-sandbox", "--disable-gpu", "--allow-file-access-from-files"] });
  const page = await browser.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e.message || e)));
  const html = readFileSync(path.resolve(dir, "index.html"), "utf8");
  const ancho = Number((html.match(/data-width="(\d+)"/) || [])[1] || 1080);
  const alto = Number((html.match(/data-height="(\d+)"/) || [])[1] || 1920);
  await page.setViewport({ width: ancho, height: alto });
  await page.goto(pathToFileURL(path.resolve(dir, "index.html")).href, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  const info = await page.evaluate(() => window.__factos ? { eventos: window.__factos.eventos, avisos: window.__factos.avisos,
    duracion: window.__factos.duracion, zona: window.__factos.zona } : { error: window.__factos_error || null });
  if (!info.eventos) throw new Error(info.error || errs.join("\n") || "la escena no terminó de construirse");
  Object.assign(out, { eventos: info.eventos, avisos: info.avisos });
  const fuera = await page.evaluate((paso) => {
    const f = window.__factos, z = f.zona, tol = 10, res = [];
    const visible = (e) => {
      for (let n = e; n && n !== document.body; n = n.parentElement) {
        const cs = getComputedStyle(n);
        if (cs.visibility === "hidden" || cs.display === "none" || Number(cs.opacity) < 0.05) return false;
      }
      return true;
    };
    for (let t = 0; t < f.duracion; t += paso) {
      f.seek(t);
      if (f.zoom(t) > 1.1) continue;   // con la cámara acercada el recorte es intencional
      for (const e of document.querySelectorAll(".txt")) {
        if (!visible(e)) continue;
        const r = e.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) continue;
        const bordes = [];
        if (r.left < z.x0 - tol) bordes.push("izquierda");
        if (r.right > z.x1 + tol) bordes.push("derecha");
        if (r.top < z.y0 - tol) bordes.push("arriba");
        if (r.bottom > z.y1 + tol) bordes.push("abajo");
        if (bordes.length) res.push({ t: +t.toFixed(2), texto: e.textContent.trim().slice(0, 40), borde: bordes.join("+") });
      }
    }
    return res;
  }, paso);
  // solo cuenta si se repite en al menos 2 muestras seguidas (un rebote de un cuadro no importa)
  const key = (x) => `${x.texto}|${x.borde}`;
  const byKey = new Map();
  for (const x of fuera) { const a = byKey.get(key(x)) || []; a.push(x); byKey.set(key(x), a); }
  for (const a of byKey.values()) {
    if (a.some((x, i) => i > 0 && Math.abs(x.t - a[i - 1].t - paso) < 1e-6)) out.fuera.push({ ...a[0], veces: a.length });
  }
  if (errs.length) out.avisos.push(...errs.map((e) => `error de JavaScript: ${e}`));
  out.ok = true;
} catch (e) {
  out.error = String(e && e.message || e);
} finally {
  if (browser) await browser.close();
}
process.stdout.write(JSON.stringify(out));
