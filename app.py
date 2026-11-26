"""Canon Workbench web app.

Run with:   python app.py      then open http://127.0.0.1:5000
"""

from __future__ import annotations

from fractions import Fraction

from flask import Flask, jsonify, render_template, request

from music.canon import ENDINGS, INTERVAL_CHOICES, CanonSettings, build_canon
from music.parser import ParseError, check_barlines, parse_melody
from music.render import build_score, measure_length, render_svg, to_musicxml

app = Flask(__name__)

EXAMPLE = """% Frere Jacques (traditional round). Try 4 voices, 2 bars apart.
F4/4 G4 A4 F4 | F4 G4 A4 F4 | A4 Bb4 C5/2 | A4/4 Bb4 C5/2 |
C5/8 D5 C5 Bb4 A4/4 F4 | C5/8 D5 C5 Bb4 A4/4 F4 | F4 C4 F4/2 | F4/4 C4 F4/2
"""

DEFAULTS = {
    "voices": 4,
    "delay_bars": 2,
    "delay_beats": 0,
    "interval": "P1",
    "repeats": 1,
    "ending": "stagger",
    "time_signature": "4/4",
    "key": "F",
}


@app.get("/")
def index():
    return render_template(
        "index.html",
        example=EXAMPLE,
        intervals=INTERVAL_CHOICES,
        endings=ENDINGS,
        defaults=DEFAULTS,
    )


def _settings_from(data: dict) -> tuple[CanonSettings, Fraction, str, str]:
    ts = data.get("time_signature") or "4/4"
    bar = measure_length(ts)
    delay = Fraction(str(data.get("delay_bars", 0))) * bar + Fraction(str(data.get("delay_beats", 0)))
    settings = CanonSettings(
        voices=int(data.get("voices", 3)),
        delay=delay,
        interval=data.get("interval") or "P1",
        repeats=int(data.get("repeats", 1)),
        ending=data.get("ending") or "stagger",
        octave_shifts=[int(x) for x in data.get("octave_shifts", [])],
    )
    return settings, bar, ts, data.get("key", "C")


@app.post("/api/render")
def api_render():
    data = request.get_json(force=True) or {}

    try:
        melody = parse_melody(data.get("melody", ""))
    except ParseError as err:
        return jsonify(
            ok=False,
            errors=[
                {"line": i.line, "index": i.index, "token": i.token, "message": i.message}
                for i in err.issues
            ],
        )
    if len(melody) == 0:
        return jsonify(ok=False, errors=[{"line": 0, "index": 0, "token": "", "message": "type some notes"}])

    try:
        settings, bar, ts, key_text = _settings_from(data)
        voices = build_canon(melody, settings)
        xml = to_musicxml(build_score(voices, ts, key_text))
        pages = render_svg(xml, width=int(data.get("width", 2100)))
    except Exception as exc:  # show settings problems in the page, not as a crash
        return jsonify(ok=False, errors=[{"line": 0, "index": 0, "token": "", "message": str(exc)}])

    warnings = check_barlines(melody, bar)
    if settings.voices > 1 and settings.delay >= melody.duration:
        warnings.append("the entry delay is as long as the melody, so voices never overlap")

    return jsonify(
        ok=True,
        svg=pages,
        warnings=warnings,
        summary={
            "notes": len(melody.notes()),
            "melody_bars": float(melody.duration / bar),
            "delay_beats": float(settings.delay),
        },
    )


if __name__ == "__main__":
    app.run(debug=True)
