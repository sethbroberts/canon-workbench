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
  render.py       voices -> music21 score -> MusicXML -> SVG (Verovio)
static/           front-end JavaScript and CSS
templates/        HTML page
tests/            pytest tests
puzzles/          (coming) puzzle canons to solve
```

The `music/` package has no web code, so it can be tested on its own and
reused later by the counterpoint tutor.
