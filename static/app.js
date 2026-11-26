// Canon Workbench front end: send the melody + settings to Flask, show the score.

const fields = ["melody", "voices", "delay_bars", "delay_beats", "interval",
                "repeats", "ending", "time_signature", "key"];
const el = id => document.getElementById(id);

function collect() {
  return {
    melody: el("melody").value,
    voices: Number(el("voices").value),
    delay_bars: Number(el("delay_bars").value) || 0,
    delay_beats: Number(el("delay_beats").value) || 0,
    interval: el("interval").value,
    repeats: Number(el("repeats").value) || 1,
    ending: el("ending").value,
    time_signature: el("time_signature").value,
    key: el("key").value,
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
  buildMixer(data.playback.voices.length);
  const s = data.summary;
  el("status").textContent =
    `${s.notes} notes · melody ${s.melody_bars} bars · entries every ${s.delay_beats} beats`;
  showMessages([], data.warnings);
}

let timer = null;
function scheduleRefresh() {
  clearTimeout(timer);
  timer = setTimeout(refresh, 350);
}

for (const id of fields) {
  el(id).addEventListener("input", scheduleRefresh);
  el(id).addEventListener("change", scheduleRefresh);
}

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
el("sound").onchange = () => Player.setSound(el("sound").value);

// Space bar plays/stops, except while typing in a text field.
document.addEventListener("keydown", e => {
  const typing = ["TEXTAREA", "INPUT", "SELECT"].includes(document.activeElement.tagName);
  if (e.code === "Space" && !typing) {
    e.preventDefault();
    el("play").click();
  }
});

refresh();
