"""Puzzle canons: load them, hide their answers, and grade attempts.

Each puzzle is a JSON file in puzzles/. Three kinds:

  complete  A round with one phrase missing. Write a phrase that fits.
            Graded by the errors *your* phrase causes, so any good answer
            counts, not only the one in the file.
  entries   A melody that works as a canon. Find when (and at what interval)
            the next voice comes in. Graded against the list of answers.
  fix       A canon with planted mistakes. Change notes until the checker
            finds no errors (the length must stay the same).

Common fields: id, title, type, level (1-3), order, intro, hints, source,
settings {time_signature, key, voices, delay_bars, delay_beats, interval,
ending, repeats}, words (optional).
complete: phrases (a list of melody texts, null for the missing one),
          phrase_bars, progression (optional), solution
entries:  melody, answers [{delay_beats, interval}] (delay in quarter notes)
fix:      melody, solution
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

from .canon import CanonSettings, build_canon
from .lyrics import apply_words
from .parser import ParseError, parse_melody
from .render import measure_length
from .rules import check_canon

PUZZLES_DIR = Path(__file__).resolve().parent.parent / "puzzles"
SECRET_FIELDS = ("solution", "answers")


def load_all(folder: Path = PUZZLES_DIR) -> list[dict]:
    puzzles = []
    for path in sorted(folder.glob("*.json")):
        p = json.loads(path.read_text(encoding="utf-8"))
        p.setdefault("id", path.stem)
        puzzles.append(p)
    puzzles.sort(key=lambda p: (p.get("order", 99), p["id"]))
    return puzzles


def find(puzzle_id: str, folder: Path = PUZZLES_DIR) -> dict | None:
    return next((p for p in load_all(folder) if p["id"] == puzzle_id), None)


def public(p: dict) -> dict:
    """The puzzle without its answers (sent to the page until you ask to see them)."""
    return {k: v for k, v in p.items() if k not in SECRET_FIELDS}


# ---- building the music ----

def _settings(p: dict, delay: Fraction | None = None, interval: str | None = None) -> tuple[CanonSettings, Fraction]:
    s = p.get("settings", {})
    ts = s.get("time_signature", "4/4")
    bar = measure_length(ts)
    if delay is None:
        delay = Fraction(str(s.get("delay_bars", 0))) * bar + Fraction(str(s.get("delay_beats", 0)))
    settings = CanonSettings(voices=int(s.get("voices", 2)), delay=delay, interval=interval or s.get("interval", "P1"),
                             repeats=int(s.get("repeats", 1)), ending=s.get("ending", "stagger"))
    return settings, bar


def _check(p: dict, melody_text: str, settings: CanonSettings):
    s = p.get("settings", {})
    melody = parse_melody(melody_text)
    melody, _ = apply_words(melody, p.get("words", ""))
    voices = build_canon(melody, settings)
    findings, _ = check_canon(voices, s.get("time_signature", "4/4"), s.get("key", ""),
                              unison=(settings.interval == "P1"), melody_length=melody.duration)
    return melody, voices, findings


def compose(p: dict, missing_text: str) -> str:
    """The full melody of a 'complete' puzzle with the missing phrase filled in."""
    return "\n".join(missing_text if t is None else t for t in p["phrases"])


def _errors(findings) -> list:
    return [f for f in findings if f.severity == "error"]


def _brief(findings) -> list[dict]:
    return [{"rule": f.rule, "label": f.label, "message": f.message, "start": float(f.start)} for f in findings]


# ---- grading ----

def grade(p: dict, attempt: dict) -> dict:
    """attempt: {"text": ...} for complete/fix, {"delay_beats", "interval"} for entries."""
    kind = p["type"]
    try:
        if kind == "complete":
            return _grade_complete(p, attempt.get("text", ""))
        if kind == "entries":
            return _grade_entries(p, Fraction(str(attempt.get("delay_beats", 0))), attempt.get("interval", "P1"))
        if kind == "fix":
            return _grade_fix(p, attempt.get("text", ""))
    except ParseError as err:
        return {"solved": False, "message": f"The notes couldn't be read: {err.issues[0]}"}
    except ValueError as err:
        return {"solved": False, "message": str(err)}
    return {"solved": False, "message": f"unknown puzzle type '{kind}'"}


def _grade_complete(p: dict, text: str) -> dict:
    s = p.get("settings", {})
    bar = measure_length(s.get("time_signature", "4/4"))
    phrase_length = Fraction(str(p["phrase_bars"])) * bar
    if not text.strip():
        return {"solved": False, "message": "Write the missing phrase first."}
    length = parse_melody(text).duration
    if length != phrase_length:
        return {"solved": False,
                "message": f"Your phrase is {float(length / bar):g} bars long; it needs to be {p['phrase_bars']}."}
    settings, _ = _settings(p, delay=phrase_length)
    melody, voices, findings = _check(p, compose(p, text), settings)

    # Which stretches of each voice are singing your phrase?
    index = p["phrases"].index(None)
    spans = []
    for v in voices:
        for r in range(settings.repeats):
            a = v.start + r * melody.duration + index * phrase_length
            spans.append((v.number, a, a + phrase_length))

    def yours(f) -> bool:
        return any(n == v and a <= t < b for v, t in f.notes for n, a, b in spans)

    mine = [f for f in _errors(findings) if yours(f)]
    if mine:
        return {"solved": False, "message": f"Your phrase causes {len(mine)} error(s) against the other voices.",
                "findings": _brief(mine)}
    warnings = [f for f in findings if f.severity == "warning" and yours(f)]
    msg = "Solved! Your phrase fits against every other phrase."
    if warnings:
        msg += f" ({len(warnings)} warning(s) worth a look, but no errors.)"
    return {"solved": True, "message": msg, "findings": _brief(warnings)}


def _grade_entries(p: dict, delay: Fraction, interval: str) -> dict:
    if delay <= 0:
        return {"solved": False, "message": "Choose when the next voice comes in."}
    for ans in p.get("answers", []):
        if Fraction(str(ans["delay_beats"])) == delay and ans.get("interval", "P1") == interval:
            return {"solved": True, "message": "Solved! That's where the next voice comes in."}
    settings, bar = _settings(p, delay=delay, interval=interval)
    _, _, findings = _check(p, p["melody"], settings)
    errors = _errors(findings)
    if delay % bar == 0:
        n = delay / bar
        where = f"{float(n):g} bar{'s' if n != 1 else ''}"
    else:
        where = f"{float(delay):g} beat{'s' if delay != 1 else ''}"
    if errors:
        return {"solved": False, "message": f"With the next voice entering after {where}, the checker finds "
                                            f"{len(errors)} error(s). Listen to it and try another entry.",
                "findings": _brief(errors[:5])}
    return {"solved": False, "message": f"That works without errors, but it isn't the entry this puzzle is after. "
                                        f"Try a closer (or a different) entry."}


def _grade_fix(p: dict, text: str) -> dict:
    original = parse_melody(p["melody"])
    attempt = parse_melody(text)
    if attempt.duration != original.duration:
        return {"solved": False, "message": "Keep the melody the same length: change notes, don't add or remove time."}
    if [(e.duration, getattr(e, "pitch", None)) for e in attempt.events] == \
            [(e.duration, getattr(e, "pitch", None)) for e in original.events]:
        return {"solved": False, "message": "Nothing has changed yet. Find the notes that cause the errors."}
    settings, _ = _settings(p)
    _, _, findings = _check(p, text, settings)
    errors = _errors(findings)
    if errors:
        return {"solved": False, "message": f"{len(errors)} error(s) left.", "findings": _brief(errors[:5])}
    return {"solved": True, "message": "Solved! The canon is clean."}


def verify(p: dict) -> list[str]:
    """Problems with a puzzle file itself (used by the tests)."""
    problems = []
    kind = p.get("type")
    if kind == "complete":
        if p["phrases"].count(None) != 1:
            problems.append("needs exactly one missing phrase (null)")
        if not _grade_complete(p, p["solution"])["solved"]:
            problems.append("its own solution doesn't pass")
    elif kind == "entries":
        for ans in p["answers"]:
            if not _grade_entries(p, Fraction(str(ans["delay_beats"])), ans.get("interval", "P1"))["solved"]:
                problems.append(f"answer {ans} doesn't pass")
            settings, _ = _settings(p, delay=Fraction(str(ans["delay_beats"])), interval=ans.get("interval", "P1"))
            _, _, findings = _check(p, p["melody"], settings)
            if _errors(findings):
                problems.append(f"answer {ans} has errors: {[f.message for f in _errors(findings)]}")
    elif kind == "fix":
        settings, _ = _settings(p)
        if not _errors(_check(p, p["melody"], settings)[2]):
            problems.append("the broken melody has no errors to fix")
        if not _grade_fix(p, p["solution"])["solved"]:
            problems.append("its own solution doesn't pass")
    else:
        problems.append(f"unknown type {kind}")
    return problems
