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

PDFs are engraved by [LilyPond](https://lilypond.org), which `pip install -r
requirements.txt` installs as the `lilypond` Python package (a large download,
about 100 MB). A LilyPond already on your PATH is used first if you have one.

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
  rules/          the rule checker
    texture.py    sounding notes, vertical moments, beat strength
    intervals.py  consonance, interval names, steps and leaps
    dissonance.py suspensions, passing/neighbor tones and other figures
    motion.py     parallel, contrary and hidden fifths/octaves
    melodic.py    leaps, range, final note
static/
  app.js          editor, settings, player controls
  player.js       Tone.js playback and note highlighting
  style.css
templates/        HTML page
tests/            pytest tests
pieces/           your saved pieces (JSON)
puzzles/          (coming) puzzle canons to solve
```

The `music/` package has no web code, so it can be tested on its own and
reused later by the counterpoint tutor.
