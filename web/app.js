const $ = (sel) => document.querySelector(sel);
const api = async (path, opts = {}) => {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
};

const PRAYERS = ["fajr", "dhuhr", "asr", "maghrib", "isha"];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

let state = { status: null, media: [], devices: [] };

// ---------- status header ----------

function renderStatus() {
  const s = state.status;
  if (!s) return;
  const next = s.next;
  $("#next-prayer").textContent = next
    ? `${next.name} at ${new Date(next.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
    : s.times ? "Done for today" : "Set your location below";

  const playing = s.playing;
  const el = $("#now-playing");
  el.classList.toggle("hidden", !playing);
  if (playing) el.textContent = `Playing ${playing.label}: ${playing.mp3}`;

  const grid = $("#times");
  grid.innerHTML = "";
  if (!s.times) return;
  const now = new Date();
  for (const name of PRAYERS) {
    const hhmm = s.times[name];
    const [h, m] = hhmm.split(":").map(Number);
    const t = new Date(); t.setHours(h, m, 0, 0);
    const cell = document.createElement("div");
    cell.className = "cell" + (t < now ? " past" : "") + (next && next.name === name ? " next-up" : "");
    cell.innerHTML = `<div class="name">${name}</div><div class="time">${hhmm}</div>`;
    grid.appendChild(cell);
  }
}

function tickCountdown() {
  const next = state.status?.next;
  if (!next) { $("#countdown").textContent = ""; return; }
  const diff = new Date(next.at) - new Date();
  if (diff <= 0) { refreshStatus(); return; }
  const h = Math.floor(diff / 3.6e6), m = Math.floor(diff / 6e4) % 60, sec = Math.floor(diff / 1e3) % 60;
  $("#countdown").textContent = `in ${h}h ${String(m).padStart(2, "0")}m ${String(sec).padStart(2, "0")}s`;
}
setInterval(tickCountdown, 1000);

async function refreshStatus() {
  state.status = await api("/status");
  renderStatus();
}

// ---------- test panel ----------

function fillSelect(sel, options, selected) {
  sel.innerHTML = "";
  for (const opt of options) {
    const o = document.createElement("option");
    if (typeof opt === "string") { o.value = opt; o.textContent = opt.replace(/^Adhan-|\.mp3$/g, ""); }
    else { o.value = opt.id ?? ""; o.textContent = opt.label; }
    if (o.value === (selected ?? "")) o.selected = true;
    sel.appendChild(o);
  }
}

$("#test-play").onclick = async () => {
  try {
    await api("/test", {
      method: "POST",
      body: JSON.stringify({
        mp3: $("#test-mp3").value,
        volume: Number($("#test-volume").value),
        device: $("#test-device").value || null,
      }),
    });
  } catch (e) { alert(e.message); }
};
$("#test-stop").onclick = () => api("/stop", { method: "POST" });

// ---------- prayers ----------

async function renderPrayers() {
  const prayers = await api("/prayers");
  const box = $("#prayers");
  box.innerHTML = "";
  for (const p of prayers) {
    const row = document.createElement("div");
    row.className = "prayer-row";
    row.innerHTML = `
      <input type="checkbox" ${p.enabled ? "checked" : ""} title="Enabled">
      <span class="pname">${p.name}</span>
      <select class="mp3"></select>
      <input type="range" min="0" max="100" value="${p.volume}" title="Volume">
    `;
    fillSelect(row.querySelector(".mp3"), state.media, p.mp3);
    const save = (fields) =>
      api(`/prayers/${p.name}`, { method: "PUT", body: JSON.stringify(fields) }).then(refreshStatus);
    row.querySelector("input[type=checkbox]").onchange = (e) => save({ enabled: e.target.checked });
    row.querySelector(".mp3").onchange = (e) => save({ mp3: e.target.value });
    row.querySelector("input[type=range]").onchange = (e) => save({ volume: Number(e.target.value) });
    box.appendChild(row);
  }
}

// ---------- hooks ----------

function checkGroup(container, items, labels) {
  container.innerHTML = "";
  items.forEach((val, i) => {
    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox" value="${val}">${labels[i]}`;
    container.appendChild(label);
  });
}

async function renderHooks() {
  const hooksList = await api("/hooks");
  const box = $("#hooks");
  box.innerHTML = hooksList.length ? "" : `<div class="meta">No hooks yet.</div>`;
  for (const h of hooksList) {
    const card = document.createElement("div");
    card.className = "hook-card";
    const days = h.days.length === 7 ? "every day" : h.days.map((d) => DAYS[d]).join(", ");
    card.innerHTML = `
      <div>
        <div>${h.enabled ? "" : "⏸ "}${h.name}</div>
        <div class="meta">${h.position} · ${h.prayers.join(", ")} · ${days} · ${h.script}</div>
      </div>
      <div class="row" style="margin:0">
        <button class="toggle">${h.enabled ? "Disable" : "Enable"}</button>
        <button class="danger del">Delete</button>
      </div>`;
    card.querySelector(".toggle").onclick = () =>
      api(`/hooks/${h.id}`, { method: "PUT", body: JSON.stringify({ enabled: !h.enabled }) }).then(renderHooks);
    card.querySelector(".del").onclick = () => {
      if (confirm(`Delete hook "${h.name}"?`))
        api(`/hooks/${h.id}`, { method: "DELETE" }).then(renderHooks);
    };
    box.appendChild(card);
  }
}

async function setupHookForm() {
  const scripts = await api("/hook-scripts");
  const posSel = $("#hook-position");
  const fillScripts = () => fillSelect($("#hook-script"), scripts[posSel.value].map((s) => ({ id: s, label: s })));
  posSel.onchange = fillScripts;
  fillScripts();
  checkGroup($("#hook-prayers"), PRAYERS, PRAYERS);
  checkGroup($("#hook-days"), [0, 1, 2, 3, 4, 5, 6], DAYS);

  $("#hook-form").onsubmit = async (e) => {
    e.preventDefault();
    const checked = (sel) => [...document.querySelectorAll(`${sel} input:checked`)].map((i) => i.value);
    try {
      await api("/hooks", {
        method: "POST",
        body: JSON.stringify({
          name: $("#hook-name").value,
          position: posSel.value,
          script: $("#hook-script").value,
          prayers: checked("#hook-prayers"),
          days: checked("#hook-days").map(Number),
        }),
      });
      e.target.reset();
      $("#hook-form-details").open = false;
      renderHooks();
    } catch (err) { alert(err.message); }
  };
}

// ---------- settings ----------

async function renderSettings() {
  const s = await api("/settings");
  $("#set-lat").value = s.lat ?? "";
  $("#set-lng").value = s.lng ?? "";
  fillSelect($("#set-method"), s.methods.map((m) => ({ id: m, label: m })), s.method);
}

$("#settings-form").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api("/settings", {
      method: "PUT",
      body: JSON.stringify({
        lat: Number($("#set-lat").value),
        lng: Number($("#set-lng").value),
        method: $("#set-method").value,
      }),
    });
    refreshStatus();
  } catch (err) { alert(err.message); }
};

// ---------- events ----------

function eventLi(ev) {
  const li = document.createElement("li");
  li.className = `type-${ev.type}`;
  const ts = new Date(ev.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  li.innerHTML = `<span class="ts">${ts}</span>${ev.detail}`;
  return li;
}

async function renderEvents() {
  const events = await api("/events?limit=30");
  const ul = $("#events");
  ul.innerHTML = "";
  events.forEach((ev) => ul.appendChild(eventLi(ev)));
}

// ---------- live updates ----------

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/api/ws`);
  ws.onmessage = (msg) => {
    const data = JSON.parse(msg.data);
    if (data.kind === "playing") { state.status && (state.status.playing = data.playing); renderStatus(); }
    if (data.kind === "event") {
      $("#events").prepend(eventLi(data.event));
      if (["schedule", "adhan"].includes(data.event.type)) refreshStatus();
    }
  };
  ws.onclose = () => setTimeout(connectWs, 3000);
}

// ---------- boot ----------

(async function init() {
  [state.media, state.devices] = await Promise.all([api("/media"), api("/devices")]);
  fillSelect($("#test-mp3"), state.media);
  fillSelect($("#test-device"), state.devices);
  await Promise.all([refreshStatus(), renderPrayers(), renderHooks(), setupHookForm(), renderSettings(), renderEvents()]);
  connectWs();
})();
