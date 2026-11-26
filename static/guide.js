// Guided ways of working: the round wizard, chain mode, and puzzles.
//
// In every mode the melody box still holds the whole melody, so the score,
// checker, player and exports work exactly as in free mode. The guides just
// build that melody from smaller pieces and give feedback on each piece.
// Loaded before app.js; uses its helpers (el, scheduleRefresh, refresh, ...).

const Guide = (() => {
  let mode = "free";
  const round = { phrase_bars: 2, progression: "I V I I", parts: [], step: 0 };
  const chain = { parts: [""] };
  let feedbackData = null; // last render's {guide, findings}
  let presets = {};

  const $ = id => document.getElementById(id);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // Length of one bar in quarter notes for the chosen meter: 4/4 -> 4, 6/8 -> 3.
  function barLength() {
    const [n, d] = $("time_signature").value.split("/").map(Number);
    return (n * 4) / d;
  }
  function delayLength() {
    return (Number($("delay_bars").value) || 0) * barLength() + (Number($("delay_beats").value) || 0);
  }
  // A rest lasting `bars` bars, in the melody syntax (used to hold a missing phrase's place).
  function restBars(bars) {
    const token = { 1: "R/4", 1.5: "R/4.", 2: "R/2", 3: "R/2.", 4: "R/1", 6: "R/1." }[barLength()] || "R/1";
    return Array(bars).fill(token).join(" | ");
  }

  // ---- building the melody from the pieces ----

  function compose() {
    if (mode === "round" || mode === "chain") {
      const parts = (mode === "round" ? round.parts.slice(0, phraseCount()) : chain.parts).map(p => (p || "").trim());
      const upTo = parts.findIndex(p => !p); // stop at the first empty piece so later ones don't shift
      $("melody").value = (upTo === -1 ? parts : parts.slice(0, upTo)).join("\n");
    } else if (mode === "puzzle") {
      Puzzles.compose();
    }
  }

  function state() {
    if (mode === "round") return { mode, phrase_bars: round.phrase_bars, progression: round.progression,
                                   parts: round.parts.slice(0, phraseCount()), step: round.step };
    if (mode === "chain") return { mode, parts: chain.parts.slice() };
    if (mode === "puzzle") return Puzzles.guideForRender();
    return { mode: "free" };
  }

  // ---- switching modes ----

  function lockSettings(ids) {
    for (const id of ["voices", "delay_bars", "delay_beats", "interval", "time_signature", "key"]) {
      const locked = ids.includes(id);
      $(id).disabled = locked;
      $(id).closest("label").classList.toggle("locked", locked);
    }
  }

  function showPanels() {
    document.querySelectorAll(".modes button").forEach(b => b.classList.toggle("on", b.dataset.mode === mode));
    $("guide-round").hidden = mode !== "round";
    $("guide-chain").hidden = mode !== "chain";
    $("guide-puzzle").hidden = mode !== "puzzle";
    $("melody-block").hidden = mode === "round" || mode === "chain";
    $("melody").readOnly = false;
    $("save-piece").disabled = mode === "puzzle";
    if (mode === "round") lockSettings(["voices", "delay_bars", "delay_beats", "interval"]);
    else if (mode !== "puzzle") lockSettings([]);
  }

  function hasNotes(text) {
    return text.split("\n").some(line => line.split("%")[0].trim());
  }

  function setMode(next, { fromPiece = false } = {}) {
    if (next === mode) return;
    if (!fromPiece) {
      const empty = next === "round" ? !round.parts.some(Boolean) : next === "chain" ? !chain.parts.some(Boolean) : false;
      if (empty && mode === "free" && hasNotes($("melody").value)) {
        if (!confirm("This starts a new, empty melody built step by step. Your current melody and words " +
                     "will be replaced. Go ahead?")) return;
        $("words").value = "";
        intentional = new Set();
      }
    }
    // Keep a copy of your own work (taken before the mode changes) to restore after puzzles.
    const stash = next === "puzzle" ? { piece: collect(), slug: currentSlug, dirty } : null;
    if (mode === "puzzle") Puzzles.leave();
    mode = next;
    showPanels();
    if (mode === "round") { syncRoundSettings(); renderStep(); }
    if (mode === "chain") renderSegments();
    if (mode === "puzzle") { Puzzles.enter(stash); return; }
    if (!fromPiece) scheduleRefresh();
  }

  function apply(g) {
    g = g || { mode: "free" };
    if (g.mode === "round") {
      round.phrase_bars = g.phrase_bars || 2;
      round.progression = g.progression ?? "I V I I";
      round.parts = (g.parts || []).slice();
      round.step = g.step || 0;
    }
    if (g.mode === "chain") chain.parts = (g.parts && g.parts.length ? g.parts : [""]).slice();
    const target = g.mode === "puzzle" ? "free" : (g.mode || "free");
    if (target !== mode) setMode(target, { fromPiece: true });
    else { showPanels(); if (mode === "round") renderStep(); if (mode === "chain") renderSegments(); }
    compose();
  }

  // ---- round wizard ----

  function phraseCount() { return Number($("voices").value) || 3; }

  function steps() {
    const list = [{ key: "setup", title: "Shape of the round" }, { key: "chords", title: "Chords under every phrase" }];
    for (let i = 1; i <= phraseCount(); i++) list.push({ key: `phrase${i}`, title: `Phrase ${i}`, phrase: i });
    list.push({ key: "polish", title: "Listen and polish" });
    return list;
  }

  function syncRoundSettings() {
    $("delay_bars").value = round.phrase_bars;
    $("delay_beats").value = 0;
    $("interval").value = "P1";
  }

  function phraseHint(i, n) {
    if (i === 1) return "Write a simple, singable tune over the chords: a chord note on each strong beat " +
      "(beats 1 and 3 in 4/4). Long notes are fine here; other phrases will move against them.";
    if (i === 2) return "This phrase sings against phrase 1. Move where phrase 1 holds still, hold where it moves. " +
      "Keep chord notes on strong beats, and don't move in parallel fifths or octaves with phrase 1.";
    let text = "Fill in what's missing: a different register (above or below the others), a different rhythm, " +
      "and chord notes that nobody else is singing.";
    if (i === n) text += " This is the last phrase each voice sings, so ending on the tonic sounds final.";
    return text;
  }

  function renderStep() {
    const list = steps();
    round.step = Math.max(0, Math.min(round.step, list.length - 1));
    const step = list[round.step];
    $("step-count").textContent = `Step ${round.step + 1} of ${list.length}`;
    $("step-title").textContent = step.title;
    $("step-back").disabled = round.step === 0;
    $("step-next").disabled = round.step === list.length - 1;
    const body = $("step-body");

    if (step.key === "setup") {
      body.innerHTML = `
        <p class="hint">A round is a set of phrases, all the same length, that sound together. Each voice sings
          them in order, entering one phrase after the voice before it. So a round has as many phrases as voices.
          Choose the meter and key in the settings below.</p>
        <div class="row">
          <label>Phrase length
            <select id="g-phrase-bars">${[1, 2, 3, 4].map(b =>
              `<option value="${b}" ${b === round.phrase_bars ? "selected" : ""}>${b} bar${b > 1 ? "s" : ""}</option>`).join("")}
            </select></label>
          <label>Voices (phrases)
            <select id="g-voices">${[2, 3, 4, 5, 6].map(v =>
              `<option ${v === phraseCount() ? "selected" : ""}>${v}</option>`).join("")}</select></label>
        </div>
        <p class="hint">Two-bar phrases and three voices are a good first round.</p>`;
      $("g-phrase-bars").onchange = e => { round.phrase_bars = Number(e.target.value); syncRoundSettings(); scheduleRefresh(); renderOverview(); };
      $("g-voices").onchange = e => { $("voices").value = e.target.value; scheduleRefresh(); renderStep(); };
    } else if (step.key === "chords") {
      body.innerHTML = `
        <p class="hint">Every phrase sounds over the same chords, because all phrases are sung at once. Pick a
          progression: its chords are spread evenly across each phrase. Notes on strong beats should belong to
          the chord sounding under them. Tick <b>Chords</b> next to Play to hear it.</p>
        <div class="row">
          <label>Preset <select id="g-preset"><option value="">choose…</option>${Object.entries(presets).map(([v, name]) =>
            `<option value="${esc(v)}">${esc(name)}</option>`).join("")}</select></label>
        </div>
        <label>Progression <input id="g-progression" type="text" value="${esc(round.progression)}" placeholder="I V I I"></label>
        <p class="status" id="g-chords-status"></p>
        <p class="hint">Roman numerals in the key: I is the home chord, V the dominant, IV the subdominant,
          lowercase for minor chords (vi, or i and iv in a minor key).</p>`;
      $("g-preset").onchange = e => {
        if (!e.target.value) return;
        round.progression = e.target.value;
        $("g-progression").value = round.progression;
        scheduleRefresh();
      };
      $("g-progression").oninput = e => { round.progression = e.target.value; scheduleRefresh(); };
    } else if (step.phrase) {
      const i = step.phrase;
      body.innerHTML = `
        <p class="hint">${phraseHint(i, phraseCount())}</p>
        <textarea id="g-part" spellcheck="false" rows="3" placeholder="e.g. A4/2 G4/2 | F4/1">${esc(round.parts[i - 1] || "")}</textarea>
        <div class="status" id="g-part-status"></div>`;
      $("g-part").oninput = e => { round.parts[i - 1] = e.target.value; scheduleRefresh(); };
    } else {
      body.innerHTML = `
        <p class="hint">Turn on <b>Loop</b> and <b>Chords</b> and press Play. Then mute each voice in turn (M) and
          listen to what the others do without it. Fix anything the Check panel flags; ▶ plays each problem.
          Add words, give it a title, save it, and print it.</p>`;
    }
    renderOverview();
    showFeedback();
  }

  function renderOverview() {
    const ul = $("phrase-overview");
    ul.innerHTML = "";
    steps().forEach((s, idx) => {
      if (!s.phrase) return;
      const li = document.createElement("li");
      li.className = idx === round.step ? "current" : "";
      li.innerHTML = `<span>Phrase ${s.phrase}</span><span class="what" id="ov-${s.phrase}">${round.parts[s.phrase - 1] ? "" : "not written yet"}</span>`;
      li.style.cursor = "pointer";
      li.onclick = () => { round.step = idx; renderStep(); };
      ul.appendChild(li);
    });
  }

  // Which phrase (0-based) of a round is voice v singing at time t?
  function phraseAt(v, t, partLength, melodyLength) {
    const local = t - (v - 1) * partLength;
    if (local < 0 || melodyLength <= 0) return -1;
    return Math.floor((local % melodyLength) / partLength);
  }

  function roundErrorCounts() {
    const counts = {};
    if (!feedbackData || !feedbackData.guide.parts) return counts;
    const L = feedbackData.guide.part_length;
    const filled = feedbackData.guide.parts.filter(p => p.length > 0).length;
    for (const f of feedbackData.findings) {
      if (f.severity !== "error") continue;
      const hit = new Set(f.notes.map(([v, t]) => phraseAt(v, t, L, filled * L)).filter(x => x >= 0));
      hit.forEach(i => { counts[i] = (counts[i] || 0) + 1; });
    }
    return counts;
  }

  function phraseStatus(i) {
    const g = feedbackData && feedbackData.guide;
    const part = g && g.parts ? g.parts[i - 1] : null;
    if (!round.parts[i - 1] || !part) return { html: "not written yet", cls: "" };
    if (part.error) return { html: `<span class="bad">${esc(part.error)}</span>`, cls: "bad" };
    const bits = ['<span class="ok">✓ right length</span>'];
    const chords = (g.chord_fit || []).filter(c => c.phrase === i);
    if (chords.length) bits.push(`<span class="meh">${chords.length} strong-beat note${chords.length > 1 ? "s" : ""} outside the chord</span>`);
    const errs = roundErrorCounts()[i - 1] || 0;
    bits.push(errs ? `<span class="bad">${errs} error${errs > 1 ? "s" : ""} involving this phrase</span>` : '<span class="ok">no errors</span>');
    return { html: bits.join(" · "), chords };
  }

  function showFeedback() {
    if (mode === "round") {
      const g = feedbackData && feedbackData.guide;
      for (let i = 1; i <= phraseCount(); i++) {
        const ov = $(`ov-${i}`);
        if (ov) ov.innerHTML = phraseStatus(i).html;
      }
      const step = steps()[round.step];
      if (step && step.phrase && $("g-part-status")) {
        const st = phraseStatus(step.phrase);
        let html = st.html;
        if (st.chords && st.chords.length) {
          const bar = barLength();
          html += "<ul>" + st.chords.map(c => {
            const t = c.start;
            return `<li>bar ${Math.floor(t / bar) + 1}, beat ${(t % bar) + 1}: ${esc(c.note)} isn't in ${esc(c.chord)} (${c.chord_notes.join(" ")})</li>`;
          }).join("") + "</ul>";
        }
        $("g-part-status").innerHTML = html;
      }
      if ($("g-chords-status")) {
        $("g-chords-status").innerHTML = g && g.progression_error
          ? `<span class="bad">${esc(g.progression_error)}</span>` : (round.progression ? '<span class="ok">✓ chords understood</span>' : "");
      }
    }
    if (mode === "chain") showSegmentFeedback();
  }

  // ---- chain mode ----

  function intervalWords() {
    const opt = $("interval").selectedOptions[0];
    return opt ? opt.textContent.trim() : "at the unison";
  }

  function renderSegments() {
    const box = $("segments");
    box.innerHTML = "";
    const L = delayLength();
    const bar = barLength();
    chain.parts.forEach((text, k) => {
      const from = (k * L) / bar + 1, to = ((k + 1) * L) / bar;
      const bars = Number.isInteger(from) && Number.isInteger(to)
        ? (from === to ? `bar ${from}` : `bars ${from}–${to}`) : `beats ${k * L + 1}–${(k + 1) * L}`;
      const against = k === 0 ? "The leader starts alone."
        : `Heard against voice 2 singing segment ${k} (${intervalWords()}).`;
      const div = document.createElement("div");
      div.className = "segment";
      div.innerHTML = `
        <div class="seg-head"><b>Segment ${k + 1}</b> <span class="quiet small">${bars}</span>
          <button type="button" class="play-seg" title="Hear these bars">&#9654;</button></div>
        <div class="against">${esc(against)}</div>
        <textarea spellcheck="false" rows="2">${esc(text)}</textarea>
        <div class="status" id="seg-status-${k}"></div>`;
      div.querySelector("textarea").oninput = e => { chain.parts[k] = e.target.value; scheduleRefresh(); };
      div.querySelector(".play-seg").onclick = () => Player.playRange(k * L, (k + 1) * L);
      box.appendChild(div);
    });
    showSegmentFeedback();
  }

  function showSegmentFeedback() {
    const g = feedbackData && feedbackData.guide;
    const L = delayLength();
    chain.parts.forEach((text, k) => {
      const st = $(`seg-status-${k}`);
      if (!st) return;
      const part = g && g.parts ? g.parts[k] : null;
      if (!text.trim() || !part) { st.innerHTML = ""; return; }
      if (part.error) { st.innerHTML = `<span class="bad">${esc(part.error)}</span>`; return; }
      const errs = feedbackData.findings.filter(f => f.severity === "error" && f.start >= k * L && f.start < (k + 1) * L).length;
      st.innerHTML = '<span class="ok">✓ right length</span> · ' +
        (errs ? `<span class="bad">${errs} error${errs > 1 ? "s" : ""} in these bars</span>` : '<span class="ok">no errors in these bars</span>');
    });
  }

  // ---- puzzles ----

  const Puzzles = (() => {
    const SOLVED_KEY = "canonWorkbench.solvedPuzzles";
    let solved = new Set();
    try { solved = new Set(JSON.parse(localStorage.getItem(SOLVED_KEY) || "[]")); } catch (e) { /* storage off */ }
    let list = [];
    let current = null;
    let hintsShown = 0;
    let stash = null; // the piece you were working on before opening puzzles

    async function loadList() {
      list = await (await fetch("/api/puzzles")).json();
      const sel = $("puzzle-list");
      sel.innerHTML = list.map(p =>
        `<option value="${p.id}">${solved.has(p.id) ? "✓ " : ""}${"★".repeat(p.level || 1)} ${esc(p.title)}</option>`).join("");
      if (current) sel.value = current.id;
    }

    async function enter(saved) {
      stash = saved;
      await loadList();
      const next = list.find(p => !solved.has(p.id)) || list[0];
      if (next) open(next.id);
    }

    function leave() {
      Player.stop();
      if (stash) {
        $("puzzle-answer").value = "";
        current = null;
        const s = stash;
        stash = null;
        applyPiece(s.piece);
        currentSlug = s.slug;
        dirty = s.dirty;
        setStatus(dirty ? "unsaved changes" : "");
        refresh();
      }
    }

    async function open(id) {
      const res = await fetch(`/api/puzzles/${id}`);
      if (!res.ok) return;
      current = await res.json();
      hintsShown = 0;
      const p = current, s = p.settings;
      Player.stop();
      for (const [k, v] of Object.entries({
        title: p.title, composer: "", dedication: "", words: p.words || "",
        time_signature: s.time_signature, key: s.key, voices: s.voices,
        delay_bars: s.delay_bars, delay_beats: s.delay_beats || 0, interval: s.interval || "P1",
        repeats: s.repeats || 1, ending: s.ending || "stagger",
      })) $(k).value = v;
      intentional = new Set();
      $("more-info").open = false;
      setStatus("puzzle: not saved with your pieces");
      $("puzzle-list").value = id;
      $("puzzle-title").textContent = p.title;
      $("puzzle-intro").textContent = p.intro;
      $("puzzle-source").textContent = p.source || "";
      $("puzzle-hints").innerHTML = "";
      $("puzzle-result").innerHTML = "";
      $("puzzle-hint").disabled = !(p.hints && p.hints.length);
      $("puzzle-answer").value = "";

      const given = $("puzzle-given");
      if (p.type === "complete") {
        const missing = p.phrases.indexOf(null) + 1;
        given.innerHTML = p.phrases.map((t, i) => t === null
          ? `<code class="missing">Phrase ${i + 1}: (yours to write, ${p.phrase_bars} bars)</code>`
          : `<code>Phrase ${i + 1}: ${esc(t)}</code>`).join("");
        $("puzzle-answer-label").textContent = `Your phrase ${missing}`;
        $("puzzle-how").textContent = "Write the missing phrase, press Play (try Loop) to hear it against the others, then Check answer.";
      } else {
        given.innerHTML = "";
        $("melody").value = p.melody;
        $("puzzle-how").textContent = p.type === "entries"
          ? "Set 'Entry every' and 'Each entry' in the settings below, listen, then press Check answer."
          : "Edit the melody below. The Check panel shows the errors; ▶ plays each one.";
      }
      $("puzzle-answer-box").hidden = p.type !== "complete";
      $("melody-block").hidden = p.type === "complete";
      $("melody").readOnly = p.type === "entries";
      lockSettings(p.type === "entries" ? ["voices", "time_signature", "key"]
                                        : ["voices", "delay_bars", "delay_beats", "interval", "time_signature", "key"]);
      compose();
      refresh();
    }

    function answerText() { return $("puzzle-answer").value; }

    function compose() {
      if (!current || current.type !== "complete") return;
      const ans = answerText().trim() || restBars(current.phrase_bars);
      $("melody").value = current.phrases.map(t => (t === null ? ans : t)).join("\n");
    }

    function guideForRender() {
      if (!current || current.type !== "complete") return { mode: "free" };
      const ans = answerText().trim() || restBars(current.phrase_bars);
      return { mode: "round", phrase_bars: current.phrase_bars, progression: current.progression || "",
               parts: current.phrases.map(t => (t === null ? ans : t)) };
    }

    async function check() {
      if (!current) return;
      let attempt;
      if (current.type === "complete") attempt = { text: answerText() };
      else if (current.type === "fix") attempt = { text: $("melody").value };
      else attempt = { delay_beats: delayLength(), interval: $("interval").value };
      const res = await fetch(`/api/puzzles/${current.id}/check`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(attempt),
      });
      const r = await res.json();
      const items = (r.findings || []).map(f => `<li>${esc(f.label)}: ${esc(f.message)}</li>`).join("");
      $("puzzle-result").innerHTML = `<p class="${r.solved ? "solved" : "not-yet"}">${esc(r.message)}</p>` +
        (items ? `<ul>${items}</ul>` : "");
      if (r.solved && !solved.has(current.id)) {
        solved.add(current.id);
        try { localStorage.setItem(SOLVED_KEY, JSON.stringify([...solved])); } catch (e) { /* storage off */ }
        loadList();
      }
    }

    function hint() {
      if (!current || !current.hints) return;
      if (hintsShown < current.hints.length) {
        const li = document.createElement("li");
        li.textContent = current.hints[hintsShown++];
        $("puzzle-hints").appendChild(li);
      }
      $("puzzle-hint").disabled = hintsShown >= current.hints.length;
    }

    async function reveal() {
      if (!current || !confirm("Show a solution? (You can still try your own afterwards.)")) return;
      const sol = await (await fetch(`/api/puzzles/${current.id}/solution`)).json();
      if (current.type === "complete") $("puzzle-answer").value = sol.solution;
      else if (current.type === "fix") $("melody").value = sol.solution;
      else if (sol.answers && sol.answers.length) {
        const a = sol.answers[0], bar = barLength();
        $("delay_bars").value = Math.floor(a.delay_beats / bar);
        $("delay_beats").value = a.delay_beats % bar;
        $("interval").value = a.interval;
      }
      $("puzzle-result").innerHTML = '<p class="quiet">Here is one solution. Press Play to hear it.</p>';
      compose();
      refresh();
    }

    function init() {
      $("puzzle-list").onchange = e => open(e.target.value);
      $("puzzle-check").onclick = check;
      $("puzzle-hint").onclick = hint;
      $("puzzle-reveal").onclick = reveal;
      $("puzzle-answer").addEventListener("input", scheduleRefresh);
    }

    return { enter, leave, open, compose, guideForRender, init, current: () => current };
  })();

  // ---- wiring ----

  function init() {
    try { presets = JSON.parse($("presets").textContent); } catch (e) { presets = {}; }
    document.querySelectorAll(".modes button").forEach(b => { b.onclick = () => setMode(b.dataset.mode); });
    $("step-back").onclick = () => { round.step--; renderStep(); };
    $("step-next").onclick = () => { round.step++; renderStep(); };
    $("add-segment").onclick = () => { chain.parts.push(""); renderSegments(); };
    $("remove-segment").onclick = () => {
      if (chain.parts.length > 1) { chain.parts.pop(); renderSegments(); scheduleRefresh(); }
    };
    // Segment labels depend on the delay, meter and interval.
    for (const id of ["delay_bars", "delay_beats", "interval", "time_signature"]) {
      $(id).addEventListener("change", () => { if (mode === "chain") renderSegments(); });
    }
    $("voices").addEventListener("change", () => { if (mode === "round") renderStep(); });
    Puzzles.init();
    showPanels();
  }

  return {
    init,
    apply,
    compose,
    state,
    mode: () => mode,
    feedback: data => { feedbackData = data.guide ? data : { guide: {}, findings: data.findings || [] }; showFeedback(); },
    puzzle: () => Puzzles.current(),
  };
})();
