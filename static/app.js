// Canon Workbench front end: send the melody + settings to Flask, show the score.

const fields = ["title", "composer", "dedication", "melody", "words", "voices", "delay_bars",
                "delay_beats", "interval", "repeats", "ending", "time_signature", "key"];
const el = id => document.getElementById(id);

function collect() {
  return {
    title: el("title").value,
    composer: el("composer").value,
    dedication: el("dedication").value,
    words: el("words").value,
    tempo: Number(el("tempo").value),
    intentional: [...intentional],
    melody: el("melody").value,
    voices: Number(el("voices").value),
    delay_bars: Number(el("delay_bars").value) || 0,
    delay_beats: Number(el("delay_beats").value) || 0,
    interval: el("interval").value,
    repeats: Number(el("repeats").value) || 1,
    ending: el("ending").value,
    time_signature: el("time_signature").value,
    key: el("key").value,
    guide: typeof Guide !== "undefined" ? Guide.state() : { mode: "free" },
  };
}

function showMessages(errors, warnings) {
  const box = el("messages");
  box.innerHTML = "";
  for (const e of errors) {
    const p = document.createElement("p");
    p.className = "error";
    const where = e.line ? `Line ${e.line}, token ${e.index} “${e.token}”: ` : "";
    p.textContent = where + e.message;
    box.appendChild(p);
  }
  for (const w of warnings) {
    const p = document.createElement("p");
    p.className = "warning";
    p.textContent = "Warning: " + w;
    box.appendChild(p);
  }
}

let requestNumber = 0;

async function refresh() {
  const mine = ++requestNumber;
  el("score").classList.add("stale");
  let data;
  try {
    const res = await fetch("/api/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collect()),
    });
    data = await res.json();
  } catch (err) {
    showMessages([{ message: "Could not reach the server. Is app.py running?" }], []);
    return;
  }
  if (mine !== requestNumber) return; // a newer request is on its way

  if (!data.ok) {
    showMessages(data.errors, []); // keep the last good score, greyed out
    return;
  }
  el("score").innerHTML = data.svg.join("");
  el("score").classList.remove("stale");
  Player.load(data.playback, data.timemap);
  el("backing-wrap").hidden = !Player.hasBacking();
  buildMixer(data.playback.voices.length);
  showFindings(data.findings || []);
  Guide.feedback(data);
  const s = data.summary;
  el("status").textContent =
    `${s.notes} notes · melody ${s.melody_bars} bars · entries every ${s.delay_beats} beats`;
  showMessages([], data.warnings);
}

let timer = null;
function scheduleRefresh() {
  Guide.compose();
  markChanged();
  clearTimeout(timer);
  timer = setTimeout(refresh, 350);
}

for (const id of fields) {
  el(id).addEventListener("input", scheduleRefresh);
  el(id).addEventListener("change", scheduleRefresh);
}

// ---- Rule checker ----

// Findings you've marked "intentional" stay listed but greyed out. They belong to
// the piece: saved with it, and restored when you open it.
let intentional = new Set();
function saveIntentional() { markChanged(); }

let currentFindings = [];
const SEVERITY_RANK = { error: 3, warning: 2, info: 1 };

function plural(n, word) { return `${n} ${word}${n === 1 ? "" : "s"}`; }

function findingItem(f) {
  const li = document.createElement("li");
  li.className = `finding ${f.severity}` + (intentional.has(f.key) ? " ok" : "");
  const beat = Number.isInteger(f.beat) ? f.beat : f.beat.toFixed(2).replace(/0+$/, "");
  li.innerHTML = `
    <button type="button" class="hear" title="Hear this passage">&#9654;</button>
    <div class="text">
      <div class="where"></div>
      <div class="msg"></div>
    </div>
    <button type="button" class="mark" title="Mark as intentional (or undo)">&#10003;</button>`;
  li.querySelector(".where").textContent = `Bar ${f.bar}, beat ${beat} · ${f.label}`;
  li.querySelector(".msg").textContent = f.message;
  li.querySelector(".hear").onclick = () => Player.playRange(f.play_from, f.play_to);
  li.querySelector(".text").onclick = () => focusFinding(f, li);
  li.querySelector(".mark").onclick = () => {
    intentional.has(f.key) ? intentional.delete(f.key) : intentional.add(f.key);
    saveIntentional();
    showFindings(currentFindings);
  };
  return li;
}

function showFindings(findings) {
  currentFindings = findings;
  el("check").hidden = false;
  const problems = findings.filter(f => f.severity !== "info");
  const recognized = findings.filter(f => f.severity === "info");
  const open = problems.filter(f => !intentional.has(f.key));
  const errors = open.filter(f => f.severity === "error").length;
  const warnings = open.filter(f => f.severity === "warning").length;
  el("check-summary").textContent = errors || warnings
    ? `${plural(errors, "error")} · ${plural(warnings, "warning")}`
    : "no problems found";

  const list = el("findings");
  list.innerHTML = "";
  problems.forEach(f => list.appendChild(findingItem(f)));
  const rlist = el("recognized-list");
  rlist.innerHTML = "";
  recognized.forEach(f => rlist.appendChild(findingItem(f)));
  el("recognized-count").textContent = recognized.length;
  colorScore();
}

// Color notes by the most serious finding that involves them.
function colorScore() {
  const score = el("score");
  score.querySelectorAll(".f-error, .f-warning, .f-info, .f-ok").forEach(n =>
    n.classList.remove("f-error", "f-warning", "f-info", "f-ok"));
  if (!el("show-marks").checked) return;
  const showInfo = el("recognized").open;
  const best = new Map(); // note id -> class
  for (const f of currentFindings) {
    if (f.severity === "info" && !showInfo) continue;
    const cls = intentional.has(f.key) ? "f-ok" : `f-${f.severity}`;
    const rank = intentional.has(f.key) ? 0 : SEVERITY_RANK[f.severity];
    for (const id of f.note_ids) {
      if (!best.has(id) || best.get(id).rank < rank) best.set(id, { cls, rank });
    }
  }
  for (const [id, { cls }] of best) document.getElementById(id)?.classList.add(cls);
}

function focusFinding(f, li) {
  document.querySelectorAll("#score .focus").forEach(n => n.classList.remove("focus"));
  document.querySelectorAll(".finding.selected").forEach(n => n.classList.remove("selected"));
  li.classList.add("selected");
  const nodes = f.note_ids.map(id => document.getElementById(id)).filter(Boolean);
  nodes.forEach(n => n.classList.add("focus"));
  nodes[0]?.scrollIntoView({ behavior: "smooth", block: "center" });
}

el("show-marks").onchange = colorScore;
el("recognized").addEventListener("toggle", colorScore);

// ---- Player controls ----

// One strip per voice: mute, solo, volume, octave. Rebuilt only when the voice count changes.
function buildMixer(count) {
  const mixer = el("mixer");
  if (mixer.childElementCount === count) return;
  mixer.innerHTML = "";
  for (let i = 0; i < count; i++) {
    const s = Player.voiceState(i);
    const strip = document.createElement("div");
    strip.className = "voice-strip";
    strip.innerHTML = `
      <span class="name">${i + 1}</span>
      <button type="button" data-act="mute" title="Mute voice ${i + 1}">M</button>
      <button type="button" data-act="solo" title="Solo voice ${i + 1}">S</button>
      <input type="range" min="-30" max="6" step="1" title="Volume, voice ${i + 1}">
      <select title="Octave, voice ${i + 1}">
        <option value="-1">8vb</option><option value="0">as written</option><option value="1">8va</option>
      </select>`;
    const [mute, solo] = strip.querySelectorAll("button");
    const vol = strip.querySelector("input");
    const oct = strip.querySelector("select");
    mute.classList.toggle("on", s.mute);
    solo.classList.toggle("on", s.solo);
    vol.value = s.volume;
    oct.value = s.octave;
    mute.onclick = () => { Player.setVoice(i, { mute: !s.mute }); mute.classList.toggle("on", s.mute); };
    solo.onclick = () => { Player.setVoice(i, { solo: !s.solo }); solo.classList.toggle("on", s.solo); };
    vol.oninput = () => Player.setVoice(i, { volume: Number(vol.value) });
    oct.onchange = () => Player.setVoice(i, { octave: Number(oct.value) });
    mixer.appendChild(strip);
  }
}

Player.onChange(playing => {
  el("play").classList.toggle("playing", playing);
  el("play").innerHTML = playing ? "&#9632; Stop" : "&#9654; Play";
});

el("play").onclick = () => (Player.isPlaying() ? Player.stop() : Player.play());

el("tempo").oninput = () => {
  el("tempo-value").textContent = el("tempo").value;
  Player.setTempo(Number(el("tempo").value));
};
Player.setTempo(Number(el("tempo").value));

el("loop").onchange = () => Player.setLoop(el("loop").checked);
el("backing").onchange = () => Player.setBacking(el("backing").checked);
el("sound").onchange = () => Player.setSound(el("sound").value);

// Space bar plays/stops, except while typing in a text field.
document.addEventListener("keydown", e => {
  const typing = ["TEXTAREA", "INPUT", "SELECT"].includes(document.activeElement.tagName);
  if (e.code === "Space" && !typing) {
    e.preventDefault();
    el("play").click();
  }
});

// ---- Pieces: save, open, new, and an automatic draft ----

const DRAFT_KEY = "canonWorkbench.draft";
let currentSlug = "";   // the saved piece this work came from, if any
let dirty = false;      // changed since the last save or open

function setStatus(text) { el("save-status").textContent = text; }

// The draft is the work in progress, kept in this browser so a reload loses nothing.
function writeDraft() {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({ slug: currentSlug, dirty, piece: collect() }));
  } catch (e) { /* storage off */ }
}

function markChanged() {
  if (Guide.mode() === "puzzle") return; // puzzles never touch your own piece or draft
  dirty = true;
  if (currentSlug) setStatus("unsaved changes");
  writeDraft();
}

function applyPiece(p) {
  for (const id of fields) {
    if (p[id] !== undefined && p[id] !== null) el(id).value = p[id];
  }
  if (p.tempo) {
    el("tempo").value = p.tempo;
    el("tempo-value").textContent = p.tempo;
    Player.setTempo(Number(p.tempo));
  }
  intentional = new Set(p.intentional || []);
  el("more-info").open = Boolean(p.composer || p.dedication);
  Guide.apply(p.guide);
}

async function loadPieceList() {
  const select = el("open-piece");
  let pieces = [];
  try { pieces = await (await fetch("/api/pieces")).json(); } catch (e) { return; }
  select.innerHTML = '<option value="">Open…</option>';
  for (const p of pieces) {
    const o = document.createElement("option");
    o.value = p.slug;
    o.textContent = p.title;
    select.appendChild(o);
  }
}

function okToDiscard() {
  return !dirty || confirm("You have unsaved changes. Discard them?");
}

el("open-piece").onchange = async () => {
  const slug = el("open-piece").value;
  el("open-piece").value = "";
  if (!slug || !okToDiscard()) return;
  const res = await fetch(`/api/pieces/${slug}`);
  if (!res.ok) { setStatus("couldn't open that piece"); return; }
  Player.stop();
  applyPiece(await res.json());
  currentSlug = slug;
  refresh();
  dirty = false;
  writeDraft();
  setStatus("opened");
};

el("new-piece").onclick = () => {
  if (Guide.mode() === "puzzle") return;
  if (!okToDiscard()) return;
  Player.stop();
  applyPiece({
    title: "", composer: "", dedication: "", words: "",
    melody: "% Type your melody here, e.g. C4/4 D4 E4 C4\n",
    voices: 3, delay_bars: 2, delay_beats: 0, interval: "P1", repeats: 1,
    ending: "stagger", time_signature: "4/4", key: "C", intentional: [], guide: { mode: "free" },
  });
  currentSlug = "";
  dirty = false;
  writeDraft();
  setStatus("new piece");
  el("title").focus();
  refresh();
};

el("save-piece").onclick = async () => {
  if (Guide.mode() === "puzzle") { setStatus("puzzles aren't saved; switch back to save your piece"); return; }
  const piece = collect();
  if (!piece.title.trim()) { setStatus("give it a title first"); el("title").focus(); return; }
  const res = await fetch("/api/pieces", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(piece),
  });
  const data = await res.json();
  if (!data.ok) { setStatus(data.error || "save failed"); return; }
  currentSlug = data.slug;
  dirty = false;
  const time = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  setStatus(`saved ${time}`);
  writeDraft();
  loadPieceList();
};

// Ctrl+S / Cmd+S saves.
document.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key === "s") {
    e.preventDefault();
    el("save-piece").click();
  }
});

// ---- Print and export ----

async function exportAs(kind, button) {
  const label = button.textContent;
  button.disabled = true;
  el("export-status").textContent = kind.startsWith("pdf") ? "Engraving with LilyPond…" : "Preparing…";
  try {
    const res = await fetch(`/api/export/${kind}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(collect()),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      showMessages(data?.errors || [{ message: `Export failed (${res.status})` }], []);
      el("export-status").textContent = "";
      return;
    }
    const blob = await res.blob();
    const match = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = match ? match[1] : `canon.${kind}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    el("export-status").textContent = `Downloaded ${a.download}`;
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}

document.querySelectorAll("[data-export]").forEach(b => {
  if (b.classList.contains("needs-lilypond") && document.body.dataset.canPrint !== "yes") b.disabled = true;
  b.onclick = () => exportAs(b.dataset.export, b);
});

el("tempo").addEventListener("change", markChanged);

// ---- Start: restore the last draft, if any ----

Guide.init();

try {
  const draft = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null");
  if (draft && draft.piece) {
    applyPiece(draft.piece);
    currentSlug = draft.slug || "";
    dirty = Boolean(draft.dirty);
    if (dirty) setStatus("restored your unsaved work");
  }
} catch (e) { /* no draft */ }
loadPieceList();
refresh();
