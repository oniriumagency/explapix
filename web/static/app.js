// Factos Didácticos Studio — frontend sin build (JS vanilla)
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const STATUS = {
  generado: "Por revisar", aprobado: "Aprobado", rechazado: "Rechazado", error: "Error", incompleto: "Incompleto",
  subido_privado: "YouTube · privado", no_listado: "YouTube · no listado", publico: "YouTube · público",
  queued: "En cola", running: "Generando", done: "Listo", cancelled: "Cancelado",
  pendiente: "Pendiente", manual: "Escena a mano", en_cola: "En cola", omitido: "Omitido", publicado: "Publicado",
};
const ENGINES = { chatterbox: "Chatterbox (natural)", kokoro: "Kokoro (rápida)", piper: "Piper (robótica)" };
const PRIV = { private: "Privado", unlisted: "No listado", public: "Público" };
const fmtDate = (s) => s ? new Date(s).toLocaleString("es", { dateStyle: "medium", timeStyle: "short" }) : "";
const fmtDur = (s) => s ? `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}` : "";
const pill = (st) => `<span class="pill st-${esc(st)}">${esc(STATUS[st] || st)}</span>`;

async function api(path, opts = {}) {
  const o = { ...opts, headers: { ...(opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {}) } };
  if (o.body && !(o.body instanceof FormData)) o.body = JSON.stringify(o.body);
  const r = await fetch(path, o);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `Error ${r.status}`);
  return data;
}
function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast" + (err ? " err" : ""); t.hidden = false;
  clearTimeout(t._h); t._h = setTimeout(() => (t.hidden = true), err ? 6000 : 3000);
}
async function act(fn, okMsg) {
  try { const r = await fn(); if (okMsg) toast(okMsg); return r; } catch (e) { toast(e.message, true); }
}
// diálogo modal: fields = HTML; devuelve FormData o null
function dialog(title, html, okLabel = "Aceptar", okClass = "primary") {
  return new Promise((res) => {
    const d = $("#dlg"), f = $("#dlgForm");
    f.innerHTML = `<h2>${esc(title)}</h2>${html}<div class="row"><button value="no" class="ghost">Cancelar</button><button value="ok" class="${okClass}">${esc(okLabel)}</button></div>`;
    d.onclose = () => res(d.returnValue === "ok" ? new FormData(f) : null);
    d.showModal();
  });
}

// ---------------- navegación
let current = "biblioteca";
function show(tab, push = true) {
  current = tab;
  document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("on", s.id === tab));
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab || (tab === "detalle" && b.dataset.tab === "biblioteca")));
  if (push && location.hash !== "#" + tab && tab !== "detalle") history.replaceState(null, "", "#" + tab);
  ({ calendario: loadCalendar, biblioteca: loadLibrary, cola: loadJobs, comentarios: loadComments, voces: loadVoices, sistema: loadSystem, crear: loadCreate }[tab] || (() => {}))();
}
document.querySelectorAll("#tabs button").forEach((b) => (b.onclick = () => show(b.dataset.tab)));
window.addEventListener("hashchange", () => route());
function route() {
  const h = location.hash.slice(1);
  if (h.startsWith("v/")) openVideo(h.slice(2));
  else show(document.getElementById(h) ? h : "biblioteca", false);
}

// ---------------- biblioteca
let videos = [];
async function loadLibrary() {
  videos = await act(() => api("/api/videos")) || [];
  renderGrid();
}
function renderGrid() {
  const f = $("#filter").value;
  const list = videos.filter((v) => !f || (f === "subido" ? v.youtube_id : v.status === f));
  $("#grid").innerHTML = list.length ? list.map((v) => `
    <article class="vcard" data-id="${esc(v.id)}">
      <div class="thumb" style="${v.has_video ? `background-image:url('/media/${esc(v.id)}/thumb.jpg')` : ""}">
        ${pill(v.status)}<span class="dur">${fmtDur(v.duration)}</span>
      </div>
      <div class="info"><b>${esc(v.title)}</b><small>${fmtDate(v.created)} · ${esc(ENGINES[v.engine]?.split(" ")[0] || v.engine)}</small></div>
    </article>`).join("") : `<div class="empty">No hay videos ${f ? "con ese filtro" : "todavía. Crea uno en «Nuevo»"}.</div>`;
  document.querySelectorAll(".vcard").forEach((c) => (c.onclick = () => (location.hash = "v/" + c.dataset.id)));
}
$("#filter").onchange = renderGrid;

async function openVideo(id) {
  const v = await act(() => api("/api/videos/" + encodeURIComponent(id)));
  if (!v) return show("biblioteca");
  show("detalle", false);
  const yt = (v.youtube_id ? `<a href="https://youtube.com/shorts/${esc(v.youtube_id)}" target="_blank" rel="noopener">YouTube ↗</a> ` : "")
    + (v.instagram_permalink ? `<a href="${esc(v.instagram_permalink)}" target="_blank" rel="noopener">Instagram ↗</a>` : "");
  const st = v.stats || {}, sy = st.youtube || {}, si = st.instagram || {};
  const statsHtml = (st.youtube || st.instagram) ? `<div class="tiles" style="margin:.6rem 0">
      ${st.youtube ? `<div class="tile"><div class="k">YouTube</div><div class="v">${(sy.views ?? 0).toLocaleString("es")} vistas</div><small>${sy.avg_view_pct != null ? `${sy.avg_view_pct}% visto · ${sy.avg_view_s}s promedio · ` : ""}${sy.likes ?? 0} ❤ · ${sy.comments ?? 0} 💬</small></div>` : ""}
      ${st.instagram ? `<div class="tile"><div class="k">Instagram</div><div class="v">${(si.views ?? 0).toLocaleString("es")} reproducciones</div><small>alcance ${si.reach ?? "—"} · ${si.saved ?? 0} guardados · ${si.shares ?? 0} compartidos</small></div>` : ""}
    </div><small class="hint">Actualizado ${fmtDate(st.updated)}</small>` : "";
  const locked = !!v.youtube_id;
  const ready = v.has_video;
  $("#detalle").innerHTML = `
    <button class="back" onclick="location.hash='biblioteca'">← Biblioteca</button>
    <div class="detail">
      <div>
        ${ready ? `<video src="/media/${esc(v.id)}/video.mp4" controls playsinline preload="metadata" poster="/media/${esc(v.id)}/thumb.jpg"></video>` : `<div class="card warn">Este video no terminó de generarse.</div>`}
        <div class="actions">
          ${ready && !locked ? `<button class="ok" id="bApprove">Aprobar</button><button class="danger" id="bReject">Rechazar…</button>` : ""}
          <button class="ghost" id="bRegen">Regenerar…</button>
          ${ready && !locked ? `<button class="yt" id="bUpload">Subir a YouTube…</button>` : ""}
          ${ready && !v.instagram_id ? `<button class="ig" id="bIg">Subir a Instagram…</button>` : ""}
          <button class="ghost" id="bDelete">Mover a papelera</button>
        </div>
      </div>
      <div>
        <div class="bar" style="margin-bottom:.4rem">${pill(v.status)} <small>${fmtDate(v.created)} · ${fmtDur(v.duration)} · voz ${esc(v.engine)}</small> ${yt}</div>
        ${v.scheduled ? `<p class="hint">📅 Programado en el calendario: ${esc(v.scheduled)}</p>` : ""}
        ${statsHtml}
        ${v.review?.note ? `<p class="warn">Nota de revisión: ${esc(v.review.note)}</p>` : ""}
        ${v.review?.replaced_by ? `<p class="hint">Regenerado como <a href="#v/${esc(v.review.replaced_by)}">${esc(v.review.replaced_by)}</a></p>` : ""}
        ${v.replaces ? `<p class="hint">Versión nueva de <a href="#v/${esc(v.replaces)}">${esc(v.replaces)}</a></p>` : ""}
        <div class="card form">
          <label>Título <input id="mTitle" maxlength="100" value="${esc(v.title)}" ${locked || !ready ? "disabled" : ""}></label>
          <label>Descripción <textarea id="mDesc" rows="5" ${locked || !ready ? "disabled" : ""}>${esc(v.description)}</textarea></label>
          <label>Tags <small>(separados por coma)</small><input id="mTags" value="${esc((v.tags || []).join(", "))}" ${locked || !ready ? "disabled" : ""}></label>
          <label>Caption de Instagram <textarea id="mIg" rows="6" ${v.instagram_id || !ready ? "disabled" : ""}>${esc(v.ig_caption || "")}</textarea></label>
          <label>Comentario fijado <small>(publícalo y fíjalo a mano: las APIs no permiten fijar)</small><input id="mPin" value="${esc(v.pinned_comment || "")}" ${!ready ? "disabled" : ""}></label>
          ${!ready ? "" : `<button class="primary" id="bSaveMeta">Guardar cambios</button>`}
        </div>
        <h2>Guion</h2>
        <div class="card">${(v.segments || []).map((s, i) => `
          <div class="seg"><div class="n">${i + 1}</div><div><p>${esc(s.narration)}</p><small>🎬 ${esc(s.visual)}</small>${s.duration ? `<small>${s.duration.toFixed(1)} s</small>` : ""}</div></div>`).join("") || "<p class='hint'>Sin guion.</p>"}
        </div>
        ${v.error_log ? `<details open><summary>Error de render</summary><pre>${esc(v.error_log)}</pre></details>` : ""}
        ${v.scene ? `<details><summary>Código de la animación (scene.py)</summary><pre>${esc(v.scene)}</pre></details>` : ""}
      </div>
    </div>`;
  const reload = () => openVideo(id);
  $("#bApprove") && ($("#bApprove").onclick = () => act(() => api(`/api/videos/${id}/review`, { method: "POST", body: { status: "approved" } }), "Aprobado ✓").then(reload));
  $("#bReject") && ($("#bReject").onclick = async () => {
    const f = await dialog("Rechazar video", `<label>¿Qué hay que cambiar? <small>(se usará como indicación al regenerar)</small><textarea name="note" rows="4" required></textarea></label>
      <label><input type="checkbox" name="regen" style="width:auto"> Regenerar ahora con esta nota (usa Claude)</label>`, "Rechazar", "danger");
    if (!f) return;
    await act(() => api(`/api/videos/${id}/review`, { method: "POST", body: { status: "rejected", note: f.get("note") } }), "Rechazado");
    if (f.get("regen")) await act(() => api(`/api/videos/${id}/regenerate`, { method: "POST", body: { mode: "ai", note: f.get("note") } }), "Regeneración en cola");
    reload();
  });
  $("#bRegen").onclick = async () => {
    const f = await dialog("Regenerar", `
      <label><input type="radio" name="mode" value="ai" checked style="width:auto"> Nuevo guion y animación (usa Claude)</label>
      <label><input type="radio" name="mode" value="voice" style="width:auto"> Misma animación, solo rehacer voz y render (gratis)</label>
      <label>Indicaciones <textarea name="note" rows="3">${esc(v.review?.note || "")}</textarea></label>
      <label>Voz <select name="engine">${Object.entries(ENGINES).map(([k, n]) => `<option value="${k}" ${k === sysTts ? "selected" : ""}>${n}</option>`).join("")}</select></label>`, "Poner en cola");
    if (!f) return;
    await act(() => api(`/api/videos/${id}/regenerate`, { method: "POST", body: { mode: f.get("mode"), note: f.get("note"), engine: f.get("engine") } }), "En cola ✓");
    refreshRunning();
  };
  $("#bUpload") && ($("#bUpload").onclick = async () => {
    const f = await dialog("Subir a YouTube", `
      <p>Se subirá <b>${esc($("#mTitle").value)}</b> al canal. Revisa el título y la descripción antes de seguir.</p>
      <label>Visibilidad <select name="privacy"><option value="private">Privado (recomendado: revísalo en YouTube Studio)</option><option value="unlisted">No listado</option><option value="public">Público</option></select></label>
      <label><input type="checkbox" name="sure" required style="width:auto"> Sí, quiero subir este video</label>
      <p class="hint">Gasta ~1600 unidades de cuota (unas 6 subidas al día).</p>`, "Subir", "yt");
    if (!f) return;
    await act(() => api(`/api/videos/${id}/meta`, { method: "PUT", body: metaBody() }));
    await act(() => api(`/api/videos/${id}/upload`, { method: "POST", body: { privacy: f.get("privacy"), confirm: true } }), "Subida en cola ✓");
    refreshRunning();
  });
  const metaBody = () => ({ title: $("#mTitle").value, description: $("#mDesc").value, tags: $("#mTags").value, ig_caption: $("#mIg").value, pinned_comment: $("#mPin").value });
  $("#bSaveMeta") && ($("#bSaveMeta").onclick = () => act(() => api(`/api/videos/${id}/meta`, { method: "PUT", body: metaBody() }), "Guardado ✓"));
  $("#bIg") && ($("#bIg").onclick = async () => {
    const f = await dialog("Subir a Instagram", `
      <p>Se publicará como <b>Reel</b> en tu cuenta, con el caption de abajo. Instagram no tiene modo privado: <b>será público</b>.</p>
      <pre style="max-height:160px">${esc($("#mIg").value)}</pre>
      <label><input type="checkbox" name="sure" required style="width:auto"> Sí, publicar este Reel</label>
      <p class="hint">Se abre un enlace público temporal (Tailscale Funnel) solo mientras Meta descarga el video.</p>`, "Publicar", "ig");
    if (!f) return;
    await act(() => api(`/api/videos/${id}/meta`, { method: "PUT", body: metaBody() }));
    await act(() => api(`/api/videos/${id}/instagram`, { method: "POST", body: { confirm: true } }), "Publicación en cola ✓");
    refreshRunning();
  });
  $("#bDelete").onclick = async () => {
    if (!(await dialog("Mover a papelera", "<p>El video se moverá a out/_papelera (no se borra de YouTube si ya estaba subido).</p>", "Mover", "danger"))) return;
    await act(() => api(`/api/videos/${id}`, { method: "DELETE" }), "Movido a papelera");
    location.hash = "biblioteca";
  };
}

// ---------------- calendario
const CAL_ST = ["pendiente", "manual", "en_cola", "generado", "aprobado", "publicado", "error", "omitido"];
let cal = null;
async function loadCalendar() {
  cal = await act(() => api("/api/calendar"));
  if (!cal) return;
  $("#calAuto").checked = !!cal.auto_generate;
  const n = (st) => cal.items.filter((i) => i.status === st).length;
  $("#calInfo").textContent = `${n("generado") + n("aprobado") + n("publicado")} listos · ${n("pendiente")} pendientes · ${n("en_cola")} en cola. Horas en hora de CDMX. Las flechas cambian el orden (las fechas se quedan).`;
  $("#cal").innerHTML = cal.items.map((it, k) => `
    <div class="item cal" data-id="${esc(it.id)}">
      <div class="head">
        <div class="day">Día ${it.day}<small>${new Date(it.date + "T12:00").toLocaleDateString("es-MX", { weekday: "short", day: "numeric", month: "short" })} · ${esc(it.time)}</small></div>
        <div class="t"><b>${esc(it.title)}</b><small>🎣 ${esc(it.hook)}</small></div>
        <div class="ctrl">
          <span class="pill st-${esc(it.status)}">${esc(STATUS[it.status] || it.status)}</span>
          <button class="ghost" data-up ${k === 0 ? "disabled" : ""} title="Subir">↑</button>
          <button class="ghost" data-down ${k === cal.items.length - 1 ? "disabled" : ""} title="Bajar">↓</button>
          ${it.video ? `<a class="pill st-done" href="#v/${esc(it.video.id)}">Ver video →</a>` : ""}
          ${["pendiente", "error", "manual"].includes(it.status) ? `<button class="primary" data-gen>${it.has_scene ? "Generar" : "Generar con IA"}</button>` : ""}
        </div>
      </div>
      <details><summary>Editar textos y guion</summary>
        <div class="form" style="margin-top:.5rem">
          <div class="row"><label>Tema <input data-f="topic" value="${esc(it.topic)}"></label><label style="flex:0 1 120px">Hora <input data-f="time" value="${esc(it.time)}"></label>
            <label style="flex:0 1 160px">Estado <select data-f="status">${CAL_ST.map((x) => `<option value="${x}" ${x === it.status ? "selected" : ""}>${esc(STATUS[x] || x)}</option>`).join("")}</select></label></div>
          <label>Gancho (primer 1,5 s) <input data-f="hook" value="${esc(it.hook)}"></label>
          <label>Título YouTube Shorts <small>(&lt; 60)</small><input data-f="title" maxlength="100" value="${esc(it.title)}"></label>
          <label>Caption de Instagram <textarea data-f="ig_caption" rows="7">${esc(it.ig_caption)}</textarea></label>
          <label>Comentario fijado <input data-f="pinned_comment" value="${esc(it.pinned_comment)}"></label>
          <label>Notas <input data-f="notes" value="${esc(it.notes || "")}"></label>
          <button class="primary" data-save>Guardar</button>
          <h3 style="margin-top:1rem">Guion</h3>
          ${(it.storyboard?.segments || []).map((sg, i) => `<div class="seg"><div class="n">${i + 1}</div><div><p>${esc(sg.narration)}</p><small>🎬 ${esc(sg.visual)}</small></div></div>`).join("")}
        </div>
      </details>
    </div>`).join("");
  document.querySelectorAll("#cal .item").forEach((el, k) => {
    const id = el.dataset.id;
    const move = async (d) => {
      const order = cal.items.map((i) => i.id); const j = k + d;
      [order[k], order[j]] = [order[j], order[k]];
      await act(() => api("/api/calendar/reorder", { method: "POST", body: { order } }));
      loadCalendar();
    };
    $("[data-up]", el).onclick = () => move(-1);
    $("[data-down]", el).onclick = () => move(1);
    $("[data-gen]", el) && ($("[data-gen]", el).onclick = () => act(() => api(`/api/calendar/${id}/generate`, { method: "POST" }), "En cola ✓").then(() => { loadCalendar(); refreshRunning(); }));
    $("[data-save]", el).onclick = () => {
      const body = {}; el.querySelectorAll("[data-f]").forEach((f) => (body[f.dataset.f] = f.value));
      act(() => api(`/api/calendar/${id}`, { method: "PUT", body }), "Guardado ✓").then(loadCalendar);
    };
  });
}
$("#calAuto").onchange = (e) => act(() => api("/api/calendar/settings", { method: "PUT", body: { auto_generate: e.target.checked } }), e.target.checked ? "Generación automática activada" : "Generación automática pausada");

// ---------------- nuevo
let sysTts = "chatterbox";
function engineOptions(sel, selected) {
  sel.innerHTML = Object.entries(ENGINES).map(([k, n]) => `<option value="${k}" ${k === selected ? "selected" : ""}>${n}</option>`).join("");
}
async function loadCreate() {
  const s = await act(() => api("/api/status"));
  if (!s) return;
  sysTts = s.tts;
  engineOptions($("#engine"), s.tts);
  $("#nokey").hidden = s.llm_ready;
  $("#btnCreate").disabled = !s.llm_ready;
}
$("#btnCreate").onclick = async () => {
  const r = await act(() => api("/api/jobs", { method: "POST", body: { kind: "video", topics: $("#topics").value, notes: $("#notes").value, engine: $("#engine").value, quality: $("#quality").value } }));
  if (r) { toast(`${r.length} video(s) en cola ✓`); $("#topics").value = ""; location.hash = "cola"; refreshRunning(); }
};
$("#btnExample").onclick = async () => {
  const r = await act(() => api("/api/jobs", { method: "POST", body: { kind: "example", engine: $("#engine").value, quality: $("#quality").value } }));
  if (r) { toast("Ejemplo en cola ✓"); location.hash = "cola"; refreshRunning(); }
};

// ---------------- cola
const openLogs = new Map(); // id -> offset
async function loadJobs() {
  const js = await act(() => api("/api/jobs")) || [];
  const box = $("#jobs");
  if (!js.length) { box.innerHTML = `<div class="empty">No hay trabajos todavía.</div>`; return; }
  box.innerHTML = js.map((j) => `
    <div class="item" data-id="${esc(j.id)}">
      <div class="head"><b>${esc(j.title)}</b><span>${pill(j.status)}</span></div>
      <small>${fmtDate(j.created)}${j.step ? ` · paso ${j.step.n}/${j.step.of}: ${esc(j.step.name)}` : ""}${j.error ? ` · <span class="no">${esc(j.error)}</span>` : ""}</small>
      <div class="row" style="margin-top:.4rem">
        <button class="ghost" data-log>${openLogs.has(j.id) ? "Ocultar log" : "Ver log"}</button>
        ${["queued", "running"].includes(j.status) ? `<button class="ghost" data-cancel>Cancelar</button>` : ""}
        ${j.result ? `<a class="pill st-done" href="#v/${esc(j.result)}">Abrir video →</a>` : ""}
        ${j.meta?.file ? `<audio controls src="/media/voces/${esc(j.meta.file)}"></audio>` : ""}
      </div>
      ${openLogs.has(j.id) ? `<pre data-pre></pre>` : ""}
    </div>`).join("");
  box.querySelectorAll(".item").forEach((it) => {
    const id = it.dataset.id;
    $("[data-log]", it).onclick = () => { openLogs.has(id) ? openLogs.delete(id) : openLogs.set(id, 0); loadJobs(); };
    $("[data-cancel]", it) && ($("[data-cancel]", it).onclick = () => act(() => api(`/api/jobs/${id}/cancel`, { method: "POST" }), "Cancelando…").then(loadJobs));
    if (openLogs.has(id)) { openLogs.set(id, 0); pullLog(id, $("[data-pre]", it)); }
  });
}
async function pullLog(id, pre) {
  const r = await api(`/api/jobs/${id}/log?offset=${openLogs.get(id) || 0}`).catch(() => null);
  if (!r) return;
  pre.textContent += r.text; openLogs.set(id, r.offset); pre.scrollTop = pre.scrollHeight;
}
setInterval(() => {
  if (current !== "cola") return;
  document.querySelectorAll("#jobs .item").forEach((it) => { const pre = $("[data-pre]", it); if (pre) pullLog(it.dataset.id, pre); });
}, 2000);

// barra de progreso global
let lastRunning = null;
async function refreshRunning() {
  const s = await api("/api/status").catch(() => null);
  if (!s) return;
  sysTts = s.tts;
  const r = s.queue.running, el = $("#running");
  const b = $("#qbadge"); const n = s.queue.queued + (r ? 1 : 0);
  b.hidden = !n; b.textContent = n;
  if (r) {
    const pct = r.step ? Math.round((r.step.n - 0.5) / r.step.of * 100) : 5;
    el.innerHTML = `<span>⏳ ${esc(r.title)}${r.step ? ` — ${esc(r.step.name)}` : ""}</span><span class="prog"><i style="width:${pct}%"></i></span>`;
    el.hidden = false;
  } else el.hidden = true;
  const key = r ? r.id + (r.step?.n || 0) : "none";
  if (lastRunning !== null && key !== lastRunning) {
    if (current === "cola") loadJobs();
    if (current === "biblioteca") loadLibrary();
  }
  lastRunning = key;
}
setInterval(refreshRunning, 4000);

// ---------------- comentarios
async function loadComments() {
  const cs = await act(() => api("/api/comments")) || [];
  const box = $("#comments");
  const st = await api("/api/status").catch(() => ({}));
  $("#btnFetch").disabled = !(st.youtube_token && st.anthropic_key);
  if (!cs.length) { box.innerHTML = `<div class="empty">${st.youtube_token ? "Sin borradores. Pulsa «Buscar nuevos»." : "Conecta YouTube en Sistema para traer comentarios."}</div>`; return; }
  box.innerHTML = cs.slice().reverse().map((c) => {
    const state = c.sent ? "done" : c.discarded ? "cancelled" : c.approved ? "aprobado" : c.skip ? "rechazado" : "generado";
    const label = c.sent ? "Enviada" : c.discarded ? "Descartada" : c.approved ? "Aprobada" : c.skip ? "Claude sugiere no responder" : "Por revisar";
    return `<div class="item" data-id="${esc(c.comment_id)}">
      <div class="head"><b>${esc(c.author)}</b><span class="pill st-${state}">${esc(label)}</span></div>
      <p>💬 ${esc(c.text)}</p>
      ${c.skip && c.reason ? `<small>Motivo: ${esc(c.reason)}</small>` : ""}
      <textarea rows="2" ${c.sent ? "disabled" : ""}>${esc(c.reply)}</textarea>
      ${c.sent ? "" : `<div class="row" style="margin-top:.4rem"><button class="ok" data-a>${c.approved ? "Quitar aprobación" : "Aprobar"}</button><button class="ghost" data-s>Guardar texto</button><button class="ghost" data-d>${c.discarded ? "Recuperar" : "Descartar"}</button></div>`}
    </div>`;
  }).join("");
  box.querySelectorAll(".item").forEach((it) => {
    const id = it.dataset.id, ta = $("textarea", it), c = cs.find((x) => x.comment_id === id);
    const put = (b, m) => act(() => api(`/api/comments/${encodeURIComponent(id)}`, { method: "PUT", body: b }), m).then(loadComments);
    $("[data-a]", it) && ($("[data-a]", it).onclick = () => put({ reply: ta.value, approved: !c.approved, discarded: false }, c.approved ? "Aprobación quitada" : "Aprobada ✓"));
    $("[data-s]", it) && ($("[data-s]", it).onclick = () => put({ reply: ta.value }, "Guardado ✓"));
    $("[data-d]", it) && ($("[data-d]", it).onclick = () => put({ discarded: !c.discarded }, c.discarded ? "Recuperada" : "Descartada"));
  });
}
$("#btnFetch").onclick = () => act(() => api("/api/comments/fetch", { method: "POST" }), "Buscando comentarios… (mira la Cola)").then(refreshRunning);
$("#btnSend").onclick = async () => {
  if (!(await dialog("Enviar respuestas", "<p>Se publicarán en YouTube todas las respuestas <b>aprobadas</b> que aún no se enviaron (50 unidades de cuota cada una).</p>", "Publicar", "yt"))) return;
  act(() => api("/api/comments/send", { method: "POST", body: { confirm: true } }), "Envío en cola ✓").then(refreshRunning);
};

// ---------------- voces
async function loadVoices() {
  const v = await act(() => api("/api/voices"));
  if (!v) return;
  engineOptions($("#vEngine"), v.default_engine);
  engineOptions($("#vTestEngine"), v.default_engine);
  $("#vKokoro").value = v.settings.EXPLAPIX_KOKORO_VOICE || "em_alex";
  $("#vEx").value = v.settings.EXPLAPIX_CB_EXAGGERATION || 0.6;
  $("#vCfg").value = v.settings.EXPLAPIX_CB_CFG || 0.4;
  $("#exV").textContent = $("#vEx").value; $("#cfgV").textContent = $("#vCfg").value;
  $("#refInfo").innerHTML = v.ref.exists
    ? `<p>Referencia actual: <b>${v.ref.custom ? "tu grabación" : "voz de Kokoro (em_alex)"}</b></p><audio controls src="/media/ref.wav?t=${v.ref.mtime}"></audio>`
    : `<p class="warn">No hay referencia: Chatterbox usará su voz por defecto.</p>`;
  $("#samples").innerHTML = v.files.length ? v.files.map((f) => `
    <div class="item"><div class="head"><b>${esc(f.name.replace(/\.(mp3|wav)$/, "").replaceAll("_", " "))}</b><small>${Math.round(f.size / 1024)} KB</small></div>
    <audio controls preload="none" src="/media/voces/${esc(f.name)}"></audio></div>`).join("") : `<div class="empty">Sin muestras.</div>`;
}
$("#vEx").oninput = () => ($("#exV").textContent = $("#vEx").value);
$("#vCfg").oninput = () => ($("#cfgV").textContent = $("#vCfg").value);
$("#btnVoiceSave").onclick = () => act(() => api("/api/settings/voice", { method: "PUT", body: {
  EXPLAPIX_TTS: $("#vEngine").value, EXPLAPIX_KOKORO_VOICE: $("#vKokoro").value,
  EXPLAPIX_CB_EXAGGERATION: +$("#vEx").value, EXPLAPIX_CB_CFG: +$("#vCfg").value } }), "Voz guardada ✓").then(loadVoices);
$("#btnVoiceTest").onclick = () => act(() => api("/api/voices/test", { method: "POST", body: { text: $("#vText").value, engine: $("#vTestEngine").value } }), "Generando… la muestra aparecerá en la Cola").then(refreshRunning);
$("#btnRef").onclick = async () => {
  const f = $("#refFile").files[0];
  if (!f) return toast("Elige un archivo de audio", true);
  const fd = new FormData(); fd.append("file", f);
  const r = await act(() => api("/api/voices/ref", { method: "POST", body: fd }));
  if (r) { toast(`Referencia guardada (${r.duration} s) ✓`); loadVoices(); }
};
$("#btnRefReset").onclick = () => act(() => api("/api/voices/ref/reset", { method: "POST" }), "Referencia restaurada").then(loadVoices);

// ---------------- sistema
async function loadSystem() {
  const s = await act(() => api("/api/status"));
  if (!s) return;
  const ig = await api("/api/instagram").catch(() => ({}));
  $("#igState").innerHTML = ig.connected ? `<span class="yes">✓ Conectado como @${esc(ig.username)}</span> · token hasta ${new Date(ig.expires_at * 1000).toLocaleDateString("es-MX")} (se renueva solo)` : (ig.app ? `<span class="no">App guardada, falta autorizar</span>` : `<span class="no">Sin configurar</span>`);
  $("#igRedirect").value = ig.redirect_uri || "https://localhost/";
  const stt = await api("/api/stats").catch(() => ({ videos: [], by_category: [] }));
  $("#statsBox").innerHTML = stt.videos.length ? `
    <h3>Por categoría</h3><div class="list">${stt.by_category.map((c) => `<div class="item"><div class="head"><b>${esc(c.category)}</b><small>${c.videos} video(s) · ${c.avg_views.toLocaleString("es")} vistas prom.${c.avg_pct != null ? ` · ${c.avg_pct}% visto` : ""}</small></div></div>`).join("")}</div>
    <h3>Mejores videos</h3><div class="list">${stt.videos.slice(0, 8).map((r) => `<div class="item"><div class="head"><a href="#v/${esc(r.id)}">${esc(r.title)}</a><small>YT ${r.yt_views ?? "—"}${r.yt_pct != null ? ` (${r.yt_pct}% visto)` : ""} · IG ${r.ig_views ?? "—"} · 💾 ${r.ig_saved ?? "—"}</small></div></div>`).join("")}</div>`
    : `<p class="hint">Aún no hay videos publicados con métricas.</p>`;
  const g = s.gpu, q = s.quota;
  const yn = (b, y = "Configurada", n = "Falta") => `<span class="${b ? "yes" : "no"}">${b ? "✓ " + y : "✗ " + n}</span>`;
  $("#sys").innerHTML = `
    <div class="tile"><div class="k">Motor de IA (guiones y escenas)</div><div class="v">${yn(s.llm_ready, esc(s.llm === "claude-code" ? "Suscripción Claude" : "API Anthropic"), s.llm === "api" ? "Falta clave" : "Falta CLI")}</div><small>${esc(s.llm)}${s.llm === "api" ? "" : " · sin costo aparte, con pausas para no agotar límites"}</small></div>
    <div class="tile"><div class="k">Calendario</div><div class="v">${s.calendar.total} temas</div><small>${Object.entries(s.calendar.by_status).map(([k, n]) => `${esc(STATUS[k] || k)}: ${n}`).join(" · ")}${s.calendar.auto ? " · auto ON" : ""}</small></div>
    <div class="tile"><div class="k">YouTube</div><div class="v">${yn(s.youtube_token, "Conectado", s.youtube_client ? "Sin conectar" : "Falta client_secret")}</div></div>
    <div class="tile"><div class="k">Instagram</div><div class="v">${yn(s.instagram, "Conectado", "Sin conectar")}</div></div>
    <div class="tile"><div class="k">Cuota YouTube hoy (${esc(q.day)}, hora del Pacífico)</div><div class="v">${q.used.toLocaleString("es")} / ${q.limit.toLocaleString("es")}</div>
      <div class="meter"><i style="width:${Math.min(100, q.used / q.limit * 100)}%;${q.used > 8000 ? "background:var(--coral)" : ""}"></i></div><small>Quedan ~${q.uploads_left} subidas</small></div>
    <div class="tile"><div class="k">GPU</div><div class="v">${g ? `${g.util}% · ${g.temp}°C` : "—"}</div>${g ? `<small>${esc(g.name)} · ${(g.mem_used / 1024).toFixed(1)}/${(g.mem_total / 1024).toFixed(1)} GB VRAM</small><div class="meter"><i style="width:${g.mem_used / g.mem_total * 100}%"></i></div>` : ""}</div>
    <div class="tile"><div class="k">Disco libre</div><div class="v">${s.disk.free_gb} GB</div><small>de ${s.disk.total_gb} GB · videos: ${s.disk.out_gb} GB</small></div>
    <div class="tile"><div class="k">Videos / cola</div><div class="v">${s.videos} · ${s.queue.queued + (s.queue.running ? 1 : 0)}</div><small>voz por defecto: ${esc(ENGINES[s.tts] || s.tts)}</small></div>`;
}
$("#btnIgApp").onclick = () => act(() => api("/api/instagram/app", { method: "PUT", body: { app_id: $("#igAppId").value, app_secret: $("#igSecret").value, redirect_uri: $("#igRedirect").value } }), "App de Instagram guardada ✓").then(() => { $("#igSecret").value = ""; loadSystem(); });
$("#btnIgUrl").onclick = async () => { const r = await act(() => api("/api/instagram/auth-url", { method: "POST" })); if (r) window.open(r.url, "_blank", "noopener"); };
$("#btnIgCode").onclick = () => act(() => api("/api/instagram/auth-code", { method: "POST", body: { url: $("#igCode").value } }), "Instagram conectado ✓").then(() => { $("#igCode").value = ""; loadSystem(); });
$("#btnStats").onclick = () => act(() => api("/api/stats/update", { method: "POST" }), "Actualizando métricas… (mira la Cola)").then(refreshRunning);
$("#btnKey").onclick = () => act(() => api("/api/settings/anthropic", { method: "PUT", body: { key: $("#akey").value } }), "Clave guardada ✓").then(() => { $("#akey").value = ""; loadSystem(); });
$("#btnYtUrl").onclick = async () => {
  const r = await act(() => api("/api/youtube/auth-url", { method: "POST" }));
  if (r) window.open(r.url, "_blank", "noopener");
};
$("#btnYtCode").onclick = () => act(() => api("/api/youtube/auth-code", { method: "POST", body: { url: $("#ytCode").value } }), "YouTube conectado ✓").then(() => { $("#ytCode").value = ""; loadSystem(); });

route();
refreshRunning();
