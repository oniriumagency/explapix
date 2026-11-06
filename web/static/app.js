// Factos Didácticos Studio — frontend sin build (JS vanilla)
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const STATUS = {
  generado: "Por revisar", aprobado: "Aprobado", rechazado: "Rechazado", error: "Error", incompleto: "Incompleto",
  subido_privado: "YouTube · privado", no_listado: "YouTube · no listado", publico: "YouTube · público",
  queued: "En cola", running: "Generando", done: "Listo", cancelled: "Cancelado",
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
  ({ biblioteca: loadLibrary, cola: loadJobs, comentarios: loadComments, voces: loadVoices, sistema: loadSystem, crear: loadCreate }[tab] || (() => {}))();
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
  const yt = v.youtube_id ? `<a href="https://youtube.com/shorts/${esc(v.youtube_id)}" target="_blank" rel="noopener">Ver en YouTube ↗</a>` : "";
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
          <button class="ghost" id="bDelete">Mover a papelera</button>
        </div>
      </div>
      <div>
        <div class="bar" style="margin-bottom:.4rem">${pill(v.status)} <small>${fmtDate(v.created)} · ${fmtDur(v.duration)} · voz ${esc(v.engine)}</small> ${yt}</div>
        ${v.review?.note ? `<p class="warn">Nota de revisión: ${esc(v.review.note)}</p>` : ""}
        ${v.review?.replaced_by ? `<p class="hint">Regenerado como <a href="#v/${esc(v.review.replaced_by)}">${esc(v.review.replaced_by)}</a></p>` : ""}
        ${v.replaces ? `<p class="hint">Versión nueva de <a href="#v/${esc(v.replaces)}">${esc(v.replaces)}</a></p>` : ""}
        <div class="card form">
          <label>Título <input id="mTitle" maxlength="100" value="${esc(v.title)}" ${locked || !ready ? "disabled" : ""}></label>
          <label>Descripción <textarea id="mDesc" rows="5" ${locked || !ready ? "disabled" : ""}>${esc(v.description)}</textarea></label>
          <label>Tags <small>(separados por coma)</small><input id="mTags" value="${esc((v.tags || []).join(", "))}" ${locked || !ready ? "disabled" : ""}></label>
          ${locked || !ready ? "" : `<button class="primary" id="bSaveMeta">Guardar cambios</button>`}
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
    await act(() => api(`/api/videos/${id}/meta`, { method: "PUT", body: { title: $("#mTitle").value, description: $("#mDesc").value, tags: $("#mTags").value } }));
    await act(() => api(`/api/videos/${id}/upload`, { method: "POST", body: { privacy: f.get("privacy"), confirm: true } }), "Subida en cola ✓");
    refreshRunning();
  });
  $("#bSaveMeta") && ($("#bSaveMeta").onclick = () => act(() => api(`/api/videos/${id}/meta`, { method: "PUT", body: { title: $("#mTitle").value, description: $("#mDesc").value, tags: $("#mTags").value } }), "Guardado ✓"));
  $("#bDelete").onclick = async () => {
    if (!(await dialog("Mover a papelera", "<p>El video se moverá a out/_papelera (no se borra de YouTube si ya estaba subido).</p>", "Mover", "danger"))) return;
    await act(() => api(`/api/videos/${id}`, { method: "DELETE" }), "Movido a papelera");
    location.hash = "biblioteca";
  };
}

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
  $("#nokey").hidden = s.anthropic_key;
  $("#btnCreate").disabled = !s.anthropic_key;
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
  const g = s.gpu, q = s.quota;
  const yn = (b, y = "Configurada", n = "Falta") => `<span class="${b ? "yes" : "no"}">${b ? "✓ " + y : "✗ " + n}</span>`;
  $("#sys").innerHTML = `
    <div class="tile"><div class="k">Clave de Anthropic</div><div class="v">${yn(s.anthropic_key)}</div></div>
    <div class="tile"><div class="k">YouTube</div><div class="v">${yn(s.youtube_token, "Conectado", s.youtube_client ? "Sin conectar" : "Falta client_secret")}</div></div>
    <div class="tile"><div class="k">Cuota YouTube hoy (${esc(q.day)}, hora del Pacífico)</div><div class="v">${q.used.toLocaleString("es")} / ${q.limit.toLocaleString("es")}</div>
      <div class="meter"><i style="width:${Math.min(100, q.used / q.limit * 100)}%;${q.used > 8000 ? "background:var(--coral)" : ""}"></i></div><small>Quedan ~${q.uploads_left} subidas</small></div>
    <div class="tile"><div class="k">GPU</div><div class="v">${g ? `${g.util}% · ${g.temp}°C` : "—"}</div>${g ? `<small>${esc(g.name)} · ${(g.mem_used / 1024).toFixed(1)}/${(g.mem_total / 1024).toFixed(1)} GB VRAM</small><div class="meter"><i style="width:${g.mem_used / g.mem_total * 100}%"></i></div>` : ""}</div>
    <div class="tile"><div class="k">Disco libre</div><div class="v">${s.disk.free_gb} GB</div><small>de ${s.disk.total_gb} GB · videos: ${s.disk.out_gb} GB</small></div>
    <div class="tile"><div class="k">Videos / cola</div><div class="v">${s.videos} · ${s.queue.queued + (s.queue.running ? 1 : 0)}</div><small>voz por defecto: ${esc(ENGINES[s.tts] || s.tts)}</small></div>`;
}
$("#btnKey").onclick = () => act(() => api("/api/settings/anthropic", { method: "PUT", body: { key: $("#akey").value } }), "Clave guardada ✓").then(() => { $("#akey").value = ""; loadSystem(); });
$("#btnYtUrl").onclick = async () => {
  const r = await act(() => api("/api/youtube/auth-url", { method: "POST" }));
  if (r) window.open(r.url, "_blank", "noopener");
};
$("#btnYtCode").onclick = () => act(() => api("/api/youtube/auth-code", { method: "POST", body: { url: $("#ytCode").value } }), "YouTube conectado ✓").then(() => { $("#ytCode").value = ""; loadSystem(); });

route();
refreshRunning();
