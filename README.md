# Canon Workbench

A personal tool for learning to write canons and rounds. Type a melody, and
the app shows it in canon with itself: as many voices as you like, entering
at whatever delay and interval you choose.

Plan and status: see the project doc ("Canon Workbench — Plan & Status").

## Run it

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 in your browser. The score updates as you type.

Press **Play** (or the space bar) to hear all voices. Each voice has mute (M),
solo (S), volume, and an octave setting, so you can hear the round the way a
mixed group would sing it. With **Loop** on, you can keep editing while it
plays; the changes are picked up on the fly. Playback needs an internet
connection the first time (it loads the Tone.js audio library and piano
samples); if the piano samples can't load, it falls back to a synth sound.

The **Check** panel lists problems bar by bar, using strict Renaissance rules:
parallel and hidden fifths/octaves, dissonances that aren't prepared or
approached by step, bad leaps, notes outside D4–F5, and a melody that doesn't
end on the tonic. Problem notes are colored on the score (red = error,
amber = warning). Click a finding to outline its notes, ▶ to hear just that
bar, and ✓ to mark it intentional. Correctly handled dissonances (suspensions,
passing and neighbor tones, anticipations, cambiata, échappée) are listed under
"Recognized dissonances"; open that list to color them purple.

**Ways of working** (the buttons above the melody):
- **Free**: type the whole melody yourself.
- **Write a round**: a step-by-step wizard. Choose the phrase length and number of
  voices, then a chord progression that repeats under every phrase (presets
  included), then write one phrase at a time with a hint for each step. Each
  phrase shows whether it's the right length, which strong-beat notes fall
  outside the chord, and how many errors involve it. Tick **Chords** next to
  Play to hear the progression softly under the round.
- **Chain**: write a canon's leader one segment at a time (each as long as the
  entry delay). Each segment says what the follower sings against it, counts
  the errors in its bars, and ▶ plays just those bars.
- **Puzzles**: seven puzzle canons in three kinds: complete a round's missing
  phrase, find where (and at what interval) the next voice enters, and fix a
  canon with a planted wrong note. Hints come one at a time; solved puzzles get
  a ✓ (remembered in your browser). Your own piece is set aside while you
  solve puzzles and comes back when you switch modes.

**Words**: type them in the Words box, one syllable per note, LilyPond-style:
`Do -- na no -- bis pa -- cem`. They appear under every voice.

**Save / Open / New** keep your pieces in the `pieces/` folder (one JSON file
each, including any findings you marked intentional). Unsaved work is also kept
in the browser, so a reload loses nothing. Ctrl+S (Cmd+S) saves.

**Print and export**:
- **PDF: round** is the traditional way to print a round: the melody once, with
  circled numbers where each voice comes in, the words, and a line of
  instructions. Good for a card.
- **PDF: full score** writes every voice out.
- **MusicXML** opens in MuseScore, Finale, Sibelius or Dorico; **MIDI** plays
  anywhere; **LilyPond** gives you the source to fine-tune the engraving.

PDFs are engraved by [LilyPond](https://lilypond.org):
- **Mac:** `brew install lilypond` (with [Homebrew](https://brew.sh)). There's no
  pip package for macOS, so `requirements.txt` skips it there.
- **Windows and Linux:** `pip install -r requirements.txt` installs it as the
  `lilypond` Python package (about 100 MB).

A LilyPond already on your PATH is used first if you have one. Restart the app
after installing it.

Run the tests with:

```bash
python -m pytest
```

## Melody syntax

```
C4/4 D4/8 E4 F#4/2 R/4 G4/4. A4/8 ~A4/2 | B3/1   % comment
```

| You type | Meaning |
| --- | --- |
| `C4` | Pitch letter (A–G), optional `#`/`##`/`b`/`bb`, octave. Middle C is C4. |
| `/4` | Duration as a fraction of a whole note: `/1 /2 /4 /8 /16 /32`. |
| `/4.` `/4..` | Dotted, double-dotted. |
| *(no duration)* | Reuses the previous duration (starts at a quarter). |
| `R/2` | Rest. |
| `~A4` or `A4~` | Tie: `~A4` is tied from the previous note; `A4~` ties into the next. |
| `\|` | Optional barline; you'll get a warning if it isn't at the end of a bar. |
| `%` | Comment to the end of the line. |

## Layout

```
app.py            Flask routes
music/
  model.py        Pitch, Note, Rest, Melody
  parser.py       text syntax -> Melody
  canon.py        Melody + settings -> voices
  render.py       voices -> music21 score -> MusicXML -> SVG (Verovio) + timemap
  playback.py     voices -> note events for the browser player
  lyrics.py       words -> syllables on notes
  export.py       MusicXML, MIDI, LilyPond source and PDF
  harmony.py      chord progressions: chord-tone check, backing chords
  puzzles.py      load, hide answers, and grade puzzles
  rules/          the rule checker
    texture.py    sounding notes, vertical moments, beat strength
    intervals.py  consonance, interval names, steps and leaps
    dissonance.py suspensions, passing/neighbor tones and other figures
    motion.py     parallel, contrary and hidden fifths/octaves
    melodic.py    leaps, range, final note
static/
  app.js          editor, settings, player controls, save/open, export
  guide.js        round wizard, chain mode, puzzles
  player.js       Tone.js playback and note highlighting
  style.css
templates/        HTML page
tests/            pytest tests
pieces/           your saved pieces (JSON)
puzzles/          puzzle canons (JSON); add your own in the same format
```

The `music/` package has no web code, so it can be tested on its own and
reused later by the counterpoint tutor.
