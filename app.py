"""Canon Workbench web app.

Run with:   python app.py      then open http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from fractions import Fraction
from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request

from music.canon import ENDINGS, INTERVAL_CHOICES, CanonSettings, build_canon
from music.export import (LilyPondError, PieceInfo, lilypond_executable, lilypond_source, to_midi, to_pdf,
                          with_metadata)
from music.lyrics import apply_words
from music.parser import ParseError, check_barlines, parse_melody
from music.playback import playback_data
from music.render import build_score, measure_length, note_ids, render_score, to_musicxml
from music.rules import check_canon

app = Flask(__name__)

PIECES_DIR = Path(__file__).resolve().parent / "pieces"

EXAMPLE = """% Frere Jacques (traditional round). Try 4 voices, 2 bars apart.
F4/4 G4 A4 F4 | F4 G4 A4 F4 | A4 Bb4 C5/2 | A4/4 Bb4 C5/2 |
C5/8 D5 C5 Bb4 A4/4 F4 | C5/8 D5 C5 Bb4 A4/4 F4 | F4 C4 F4/2 | F4/4 C4 F4/2
"""
EXAMPLE_WORDS = ("Frè -- re Jac -- ques, frè -- re Jac -- ques, dor -- mez vous? dor -- mez vous? "
                 "Son -- nez les ma -- ti -- nes, son -- nez les ma -- ti -- nes, "
                 "din, dan, don! din, dan, don!")

DEFAULTS = {
    "title": "Frère Jacques",
    "composer": "Traditional",
    "dedication": "",
    "words": EXAMPLE_WORDS,
    "voices": 4,
    "delay_bars": 2,
    "delay_beats": 0,
    "interval": "P1",
    "repeats": 1,
    "ending": "stagger",
    "time_signature": "4/4",
    "key": "F",
}

# Everything that makes up a saved piece.
PIECE_FIELDS = ["title", "composer", "dedication", "words", "melody", "voices", "delay_bars", "delay_beats",
                "interval", "repeats", "ending", "time_signature", "key", "tempo", "intentional"]


@app.get("/")
def index():
    return render_template(
        "index.html",
        example=EXAMPLE,
        intervals=INTERVAL_CHOICES,
        endings=ENDINGS,
        defaults=DEFAULTS,
        can_print=lilypond_executable() is not None,
    )


# ---- turning a request into music ----

class InputProblem(Exception):
    def __init__(self, errors: list[dict]):
        self.errors = errors


def _error(message: str) -> dict:
    return {"line": 0, "index": 0, "token": "", "message": message}


def _prepare(data: dict):
    """Parse the melody, attach words, and read the canon settings."""
    try:
        melody = parse_melody(data.get("melody", ""))
    except ParseError as err:
        raise InputProblem([
            {"line": i.line, "index": i.index, "token": i.token, "message": i.message} for i in err.issues
        ])
    if len(melody) == 0:
        raise InputProblem([_error("type some notes")])
    melody, word_warnings = apply_words(melody, data.get("words", ""))

    ts = data.get("time_signature") or "4/4"
    try:
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
    except Exception as exc:
        raise InputProblem([_error(str(exc))])
    problems = settings.validate()
    if problems:
        raise InputProblem([_error(p) for p in problems])
    info = PieceInfo(data.get("title", ""), data.get("composer", ""), data.get("dedication", ""))
    return melody, settings, bar, ts, data.get("key", "C"), info, word_warnings


@app.post("/api/render")
def api_render():
    data = request.get_json(force=True) or {}
    try:
        melody, settings, bar, ts, key_text, info, word_warnings = _prepare(data)
        voices = build_canon(melody, settings)
        xml = to_musicxml(build_score(voices, ts, key_text))
        rendered = render_score(xml, width=int(data.get("width", 2100)))
    except InputProblem as p:
        return jsonify(ok=False, errors=p.errors)
    except Exception as exc:  # show problems in the page, not as a crash
        return jsonify(ok=False, errors=[_error(str(exc))])

    warnings = check_barlines(melody, bar) + word_warnings
    if settings.voices > 1 and settings.delay >= melody.duration:
        warnings.append("the entry delay is as long as the melody, so voices never overlap")

    findings, texture = check_canon(
        voices, ts, key_text, unison=(settings.interval == "P1"), melody_length=melody.duration
    )
    ids = note_ids(rendered)
    found = []
    for f in findings:
        d = f.to_dict(texture)
        d["note_ids"] = [ids[k] for v, t in f.notes if (k := (v, float(t))) in ids]
        found.append(d)

    return jsonify(
        ok=True,
        svg=rendered["pages"],
        timemap=rendered["timemap"],
        playback=playback_data(voices),
        findings=found,
        warnings=warnings,
        summary={
            "notes": len(melody.notes()),
            "melody_bars": float(melody.duration / bar),
            "delay_beats": float(settings.delay),
        },
    )


# ---- exports ----

EXPORTS = {
    # kind: (file extension, MIME type)
    "musicxml": ("musicxml", "application/vnd.recordare.musicxml+xml"),
    "midi": ("mid", "audio/midi"),
    "ly-round": ("ly", "text/plain; charset=utf-8"),
    "ly-score": ("ly", "text/plain; charset=utf-8"),
    "pdf-round": ("pdf", "application/pdf"),
    "pdf-score": ("pdf", "application/pdf"),
}


@app.post("/api/export/<kind>")
def api_export(kind: str):
    if kind not in EXPORTS:
        abort(404)
    data = request.get_json(force=True) or {}
    try:
        melody, settings, bar, ts, key_text, info, _ = _prepare(data)
    except InputProblem as p:
        return jsonify(ok=False, errors=p.errors), 400

    ext, mime = EXPORTS[kind]
    layout = "score" if kind.endswith("score") else "round"
    name = slugify(info.title) or "canon"
    if kind.startswith(("ly", "pdf")):
        name += "-round" if layout == "round" else "-score"
    try:
        if kind in ("musicxml", "midi"):
            score = with_metadata(build_score(build_canon(melody, settings), ts, key_text), info)
            body = to_musicxml(score).encode("utf-8") if kind == "musicxml" else to_midi(
                score, bpm=int(data.get("tempo", 96)))
        else:
            source = lilypond_source(melody, settings, ts, key_text, info, layout)
            body = source.encode("utf-8") if kind.startswith("ly") else to_pdf(source)
    except LilyPondError as exc:
        return jsonify(ok=False, errors=[_error(str(exc))]), 500
    return Response(body, mimetype=mime,
                    headers={"Content-Disposition": f'attachment; filename="{name}.{ext}"'})


# ---- saved pieces ----

def slugify(title: str) -> str:
    """'Dona nobis pacem!' -> 'dona-nobis-pacem' (safe as a file name)."""
    import unicodedata

    ascii_title = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")[:80]


def _piece_path(slug: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", slug or ""):
        abort(400, "bad piece name")
    return PIECES_DIR / f"{slug}.json"


@app.get("/api/pieces")
def list_pieces():
    PIECES_DIR.mkdir(exist_ok=True)
    pieces = []
    for path in PIECES_DIR.glob("*.json"):
        try:
            piece = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pieces.append({"slug": path.stem, "title": piece.get("title") or path.stem,
                       "saved_at": piece.get("saved_at", "")})
    pieces.sort(key=lambda p: p["saved_at"], reverse=True)
    return jsonify(pieces)


@app.get("/api/pieces/<slug>")
def get_piece(slug: str):
    path = _piece_path(slug)
    if not path.exists():
        abort(404)
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


@app.post("/api/pieces")
def save_piece():
    data = request.get_json(force=True) or {}
    slug = slugify(data.get("title", ""))
    if not slug:
        return jsonify(ok=False, error="Give the piece a title before saving."), 400
    piece = {k: data[k] for k in PIECE_FIELDS if k in data}
    piece["saved_at"] = datetime.now().isoformat(timespec="seconds")
    PIECES_DIR.mkdir(exist_ok=True)
    path = _piece_path(slug)
    existed = path.exists()
    path.write_text(json.dumps(piece, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return jsonify(ok=True, slug=slug, replaced=existed, saved_at=piece["saved_at"])


@app.delete("/api/pieces/<slug>")
def delete_piece(slug: str):
    path = _piece_path(slug)
    if path.exists():
        path.unlink()
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(debug=True)
