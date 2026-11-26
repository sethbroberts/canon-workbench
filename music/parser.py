"""Parse the Canon Workbench text syntax into a Melody.

Syntax (tokens separated by spaces or line breaks):

    C4/4 D4/8 E4 F#4/2 R/4 G4/4. A4/8 ~A4/2 | B3/1

    C4      pitch letter (A-G, either case), optional accidental, octave.
            Accidentals: # or ## (sharp), b or bb (flat). Middle C is C4.
    /4      duration as a fraction of a whole note: /1 /2 /4 /8 /16 /32.
            A trailing '.' dots it ('..' double-dots it).
            If left out, the previous duration is reused (starts at /4).
    R       a rest (also 'r'), e.g. R/2.
    ~       tie. '~A4' means "tied from the previous note"; 'A4~' means
            "tied into the next note". Both spellings mean the same thing.
    |       optional barline, checked against the meter.
    %       starts a comment that runs to the end of the line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from .model import Melody, Note, Pitch, Rest

ALLOWED_DENOMINATORS = {1, 2, 4, 8, 16, 32}

TOKEN_RE = re.compile(
    r"""^
    (?P<tie_in>~)?
    (?:
        (?P<step>[A-Ga-g])(?P<acc>\#{1,2}|b{1,2})?(?P<octave>-?\d)
      | (?P<rest>[Rr])
    )
    (?:/(?P<denom>\d+)(?P<dots>\.{0,2}))?
    (?P<tie_out>~)?
    $""",
    re.VERBOSE,
)


@dataclass
class ParseIssue:
    index: int  # 1-based token number, as the user would count them
    token: str
    message: str
    line: int = 0  # 1-based line number

    def __str__(self) -> str:
        return f"line {self.line}, token {self.index} '{self.token}': {self.message}"


class ParseError(Exception):
    def __init__(self, issues: list[ParseIssue]):
        self.issues = issues
        super().__init__("; ".join(str(i) for i in issues))


def _tokens(text: str):
    """Yield (line_number, token) pairs, skipping comments."""
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.split("%", 1)[0]
        # Allow '|' to touch neighbouring tokens: "C4 D4|E4" -> "C4 D4 | E4"
        line = line.replace("|", " | ")
        for tok in line.split():
            yield line_no, tok


def _duration(denom: int, dots: int) -> Fraction:
    base = Fraction(4, denom)  # quarter lengths: /4 -> 1, /8 -> 1/2, /1 -> 4
    total = base
    add = base
    for _ in range(dots):
        add /= 2
        total += add
    return total


def parse_melody(text: str) -> Melody:
    """Parse text into a Melody. Raises ParseError listing every problem found."""
    events: list = []
    barlines: list[Fraction] = []
    issues: list[ParseIssue] = []
    current = Fraction(1)  # default duration: quarter note
    position = Fraction(0)
    pending_tie = False  # previous token ended with '~'

    for index, (line_no, tok) in enumerate(_tokens(text), start=1):
        if tok == "|":
            barlines.append(position)
            continue

        m = TOKEN_RE.match(tok)
        if not m:
            issues.append(ParseIssue(index, tok, _explain_bad_token(tok), line_no))
            continue

        if m.group("denom"):
            denom = int(m.group("denom"))
            if denom not in ALLOWED_DENOMINATORS:
                issues.append(
                    ParseIssue(index, tok, f"duration /{denom} is not one of /1 /2 /4 /8 /16 /32", line_no)
                )
                continue
            current = _duration(denom, len(m.group("dots")))

        tie_in = bool(m.group("tie_in")) or pending_tie
        pending_tie = bool(m.group("tie_out"))

        if m.group("rest"):
            if tie_in:
                issues.append(ParseIssue(index, tok, "a rest cannot be tied", line_no))
            if pending_tie:
                issues.append(ParseIssue(index, tok, "a rest cannot be tied", line_no))
                pending_tie = False
            events.append(Rest(current))
        else:
            acc = m.group("acc") or ""
            alter = len(acc) if acc.startswith("#") else -len(acc)
            pitch = Pitch(m.group("step").upper(), alter, int(m.group("octave")))
            if tie_in:
                prev = events[-1] if events else None
                if not isinstance(prev, Note):
                    issues.append(ParseIssue(index, tok, "tie has no note before it", line_no))
                elif prev.pitch.midi != pitch.midi:
                    issues.append(
                        ParseIssue(index, tok, f"tie joins different pitches ({prev.pitch} to {pitch})", line_no)
                    )
                else:
                    events[-1] = Note(prev.pitch, prev.duration, tie_to_next=True)
            events.append(Note(pitch, current))

        position += current

    if pending_tie:
        issues.append(ParseIssue(index, tok, "tie at the end has no note after it", line_no))

    if issues:
        raise ParseError(issues)
    return Melody(events, barlines)


def _explain_bad_token(tok: str) -> str:
    """Give a specific hint for the most common typing mistakes."""
    core = tok.strip("~")
    if re.fullmatch(r"[A-Ga-g](#{1,2}|b{1,2})?(/\d+\.{0,2})?", core):
        return "missing octave number (e.g. C4 for middle C)"
    if core[:1].isalpha() and core[:1].upper() not in "ABCDEFGR":
        return f"unknown pitch letter '{core[:1]}' (use A-G, or R for a rest)"
    if "/" in core and not re.search(r"/\d", core):
        return "a duration needs a number after '/', e.g. /4"
    if re.search(r"/\d+\.{3,}", core):
        return "at most two dots"
    return "could not read this token (expected something like C4/4, Bb3/8., or R/2)"


def check_barlines(melody: Melody, measure_length: Fraction, pickup: Fraction = Fraction(0)) -> list[str]:
    """Return warnings for barlines that don't fall on a bar boundary.

    measure_length is in quarter lengths (4/4 -> 4, 3/4 -> 3, 6/8 -> 3).
    pickup is the length of an anacrusis before the first full bar.
    """
    warnings = []
    for n, pos in enumerate(melody.barlines, start=1):
        if (pos - pickup) % measure_length != 0:
            beats = float(pos)
            warnings.append(
                f"barline {n} falls {beats:g} quarter notes in, which is not the end of a bar"
            )
    return warnings
