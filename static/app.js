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
refresh();
