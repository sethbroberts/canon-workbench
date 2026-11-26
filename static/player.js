// Canon Workbench player: plays every voice with Tone.js and highlights notes on the score.
//
// Times from the server are in quarter notes. They are turned into Tone.js
// "ticks" (PPQ ticks per quarter), so changing the tempo while playing just works.

const Player = (() => {
  const PIANO_BASE = "https://tonejs.github.io/audio/salamander/";
  const PIANO_URLS = {};
  for (const oct of [1, 2, 3, 4, 5, 6, 7]) {
    for (const name of ["C", "D#", "F#", "A"]) PIANO_URLS[`${name}${oct}`] = `${name.replace("#", "s")}${oct}.mp3`;
  }

  let data = null;       // {length, voices: [{number, events: [{midi, start, dur}]}]}
  let timemap = [];      // [{q, on: [ids], off: [ids]}]
  let voices = [];       // per voice: {channel, instrument, part}
  let transportIds = []; // ids from Tone.Transport.schedule, to cancel on rebuild
  let sound = "piano";
  let pianoFailed = false;
  let loop = false;
  let onStateChange = () => {};
  const state = [];      // per voice: {mute, solo, volume (dB), octave}

  const ticks = q => `${Math.round(q * Tone.Transport.PPQ)}i`;

  function voiceState(i) {
    while (state.length <= i) state.push({ mute: false, solo: false, volume: 0, octave: 0 });
    return state[i];
  }

  function makeInstrument(channel) {
    if (sound === "piano" && !pianoFailed) {
      return new Tone.Sampler({
        urls: PIANO_URLS,
        baseUrl: PIANO_BASE,
        release: 1.2,
        onerror: () => {
          if (pianoFailed) return; // every failed file reports; react only once
          pianoFailed = true;
          console.warn("Piano samples could not load; using the synth sound instead.");
          if (data) rebuild();
        },
      }).connect(channel);
    }
    return new Tone.PolySynth(Tone.Synth, {
      oscillator: { type: "triangle" },
      envelope: { attack: 0.02, decay: 0.15, sustain: 0.55, release: 0.5 },
      volume: -8,
    }).connect(channel);
  }

  function clearHighlights() {
    document.querySelectorAll("#score .playing").forEach(n => n.classList.remove("playing"));
  }

  function teardown() {
    for (const id of transportIds) Tone.Transport.clear(id);
    transportIds = [];
    for (const v of voices) {
      v.part.dispose();
      v.instrument.dispose();
      v.channel.dispose();
    }
    voices = [];
  }

  // (Re)build instruments and scheduled notes from the current data.
  // Safe to call while playing: notes already past are skipped and playback continues.
  function rebuild() {
    teardown();
    if (!data) return;
    data.voices.forEach((v, i) => {
      const s = voiceState(i);
      const channel = new Tone.Channel({ volume: s.volume, mute: s.mute, solo: s.solo }).toDestination();
      const instrument = makeInstrument(channel);
      const notes = v.events.map(e => ({ time: ticks(e.start), midi: e.midi, dur: e.dur }));
      const part = new Tone.Part((time, n) => {
        if (instrument.loaded === false) return; // samples still loading
        const midi = n.midi + 12 * voiceState(i).octave;
        instrument.triggerAttackRelease(Tone.Frequency(midi, "midi").toFrequency(), ticks(n.dur), time);
      }, notes).start(0);
      voices.push({ channel, instrument, part });
    });

    for (const moment of timemap) {
      transportIds.push(Tone.Transport.schedule(time => {
        Tone.Draw.schedule(() => {
          if (Tone.Transport.state !== "started") return; // arrived after Stop
          if (moment.q === 0) clearHighlights();
          for (const id of moment.off) document.getElementById(id)?.classList.remove("playing");
          for (const id of moment.on) document.getElementById(id)?.classList.add("playing");
        }, time);
      }, ticks(moment.q)));
    }

    // At the end: stop, unless looping.
    transportIds.push(Tone.Transport.schedule(time => {
      if (!loop) Tone.Draw.schedule(() => stop(), time);
    }, ticks(data.length)));

    Tone.Transport.loopStart = 0;
    Tone.Transport.loopEnd = ticks(data.length);
    Tone.Transport.loop = loop;
  }

  // Called after every successful render.
  function load(playback, newTimemap) {
    data = playback;
    timemap = newTimemap || [];
    if (typeof Tone === "undefined") return;
    rebuild(); // highlights refer to the new score's note ids
  }

  async function play() {
    if (typeof Tone === "undefined") {
      alert("The audio library (Tone.js) didn't load. Check your internet connection and reload.");
      return;
    }
    await Tone.start(); // browsers only allow audio after a click
    if (!voices.length) rebuild();
    if (sound === "piano" && !pianoFailed) {
      // Wait for the samples, but not forever.
      await Promise.race([Tone.loaded(), new Promise(r => setTimeout(r, 8000))]);
    }
    Tone.Transport.start("+0.05", 0);
    onStateChange(true);
  }

  // Play just one passage (in quarter notes), e.g. the bar a finding is in.
  let rangeStopId = null;
  async function playRange(from, to) {
    if (typeof Tone === "undefined") return play();
    await Tone.start();
    if (!voices.length) rebuild();
    if (Tone.Transport.state === "started") stop();
    if (sound === "piano" && !pianoFailed) {
      await Promise.race([Tone.loaded(), new Promise(r => setTimeout(r, 8000))]);
    }
    Tone.Transport.loop = false;
    rangeStopId = Tone.Transport.scheduleOnce(time => {
      Tone.Draw.schedule(() => stop(), time);
    }, ticks(to));
    clearHighlights();
    Tone.Transport.start("+0.05", ticks(from));
    onStateChange(true);
  }

  function stop() {
    if (typeof Tone === "undefined") return;
    if (rangeStopId !== null) {
      Tone.Transport.clear(rangeStopId);
      rangeStopId = null;
      Tone.Transport.loop = loop; // a passage plays once; restore the loop setting
    }
    Tone.Transport.stop();
    Tone.Draw.cancel(0); // drop screen updates queued ahead of the audio
    voices.forEach(v => v.instrument.releaseAll?.());
    clearHighlights();
    onStateChange(false);
  }

  return {
    load,
    play,
    playRange,
    stop,
    isPlaying: () => typeof Tone !== "undefined" && Tone.Transport.state === "started",
    setTempo: bpm => { if (typeof Tone !== "undefined") Tone.Transport.bpm.value = bpm; },
    setLoop: on => {
      loop = on;
      if (typeof Tone !== "undefined") Tone.Transport.loop = on;
    },
    setSound: name => { sound = name; if (data && typeof Tone !== "undefined") rebuild(); },
    setVoice: (i, changes) => {
      const s = Object.assign(voiceState(i), changes);
      const v = voices[i];
      if (v) {
        v.channel.mute = s.mute;
        v.channel.solo = s.solo;
        v.channel.volume.value = s.volume;
      }
    },
    voiceState,
    onChange: fn => { onStateChange = fn; },
    // For tests and debugging.
    debug: () => ({
      voices: voices.length,
      notes: voices.map(v => v.part.length),
      moments: timemap.length,
      sound: pianoFailed ? "synth (piano failed)" : sound,
      state: Tone.Transport.state,
      position: Tone.Transport.ticks / Tone.Transport.PPQ,
    }),
  };
})();
