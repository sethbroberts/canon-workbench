"""Rules for a single melodic line, plus range and the final note.

In a round every voice sings the same line, so melodic rules are checked on
the first voice only (otherwise each problem would be reported once per voice).
"""

from __future__ import annotations

from . import Finding, Profile
from .intervals import direction, generic, is_leap, is_step, semitones
from .texture import Texture


def _leap_problem(a, b) -> tuple[str, str, str] | None:
    """(rule, severity, description) for a forbidden or doubtful leap, else None."""
    g, s = generic(a, b), semitones(a, b)
    up = b.midi > a.midi
    if g == 2 and s == 3:
        return "augmented_leap", "error", "augmented second"
    if g == 4 and s == 6:
        return "augmented_leap", "error", "augmented fourth (tritone)"
    if g == 5 and s == 6:
        return "diminished_fifth_leap", "warning", "diminished fifth"
    if g == 7:
        return "seventh_leap", "error", "seventh"
    if g > 8:
        return "leap_over_octave", "error", "leap larger than an octave"
    if g == 6 and s == 9:
        return "major_sixth_leap", "warning", "major sixth"
    if g == 6 and s == 8 and not up:
        return "descending_sixth_leap", "warning", "descending minor sixth (only the ascending one is usual)"
    return None


def check(tx: Texture, profile: Profile, key_text: str, unison: bool, melody_length=None) -> list[Finding]:
    out: list[Finding] = []
    first = tx.voice_numbers[0] if tx.voice_numbers else None
    if first is None:
        return out
    line = tx.sounds[first]

    for a in line:
        b = tx.next(a)
        if b is None:
            continue
        problem = _leap_problem(a, b)
        if problem:
            rule, sev, what = problem
            out.append(Finding(rule, sev, f"melodic leap of a {what} ({a.pitch} to {b.pitch})",
                               a.start, b.end, (first,), [(first, a.start), (first, b.start)],
                               label=f"{what.split(' (')[0]} leap"))
        c = tx.next(b)
        if c is None:
            continue
        # A leap of a fifth or more should be followed by a step back the other way.
        if generic(a, b) >= 5 and not (is_step(b, c) and direction(b, c) == -direction(a, b)):
            out.append(Finding("unrecovered_leap", "warning",
                               f"after the leap {a.pitch} to {b.pitch}, the line doesn't step back the other way",
                               a.start, c.end, (first,), [(first, a.start), (first, b.start), (first, c.start)],
                               label="unrecovered leap"))
        # Two leaps the same way that outline a seventh or more than an octave.
        if is_leap(a, b) and is_leap(b, c) and direction(a, b) == direction(b, c) != 0:
            span = generic(a, c)
            if span == 7 or span > 8:
                out.append(Finding("leaps_outline_dissonance", "warning",
                                   f"two leaps in the same direction span a {'seventh' if span == 7 else 'range over an octave'} "
                                   f"({a.pitch} to {c.pitch})",
                                   a.start, c.end, (first,), [(first, a.start), (first, b.start), (first, c.start)],
                                   label="leaps in one direction"))

    # Range: per voice; in a round all voices share the first voice's notes.
    for v in ([first] if unison else tx.voice_numbers):
        outside = [s for s in tx.sounds[v] if not profile.range_low <= s.midi <= profile.range_high]
        if outside:
            lo = min(outside, key=lambda s: s.midi)
            hi = max(outside, key=lambda s: s.midi)
            extreme = ", ".join(sorted({str(lo.pitch), str(hi.pitch)}))
            out.append(Finding("range", "warning",
                               f"voice {v}: {len(outside)} note(s) outside the comfortable range D4–F5 ({extreme})",
                               outside[0].start, outside[0].end, (v,), [(v, s.start) for s in outside],
                               label="outside singing range"))

    # The melody's last note should be the tonic.
    key = _key(key_text)
    if key is not None and line:
        last = line[-1]
        if melody_length is not None:  # the melody's own last note, even if the voice goes on
            within = [s for s in line if s.start < line[0].start + melody_length]
            last = within[-1] if within else last
        if last.midi % 12 != key.tonic.pitchClass:
            out.append(Finding("final_not_tonic", "warning",
                               f"the melody ends on {last.pitch}, not the tonic ({key.tonic.name.replace('-', 'b')})",
                               last.start, last.end, (first,), [(first, last.start)], label="doesn't end on the tonic"))
    return out


def _key(key_text: str):
    from ..render import parse_key

    try:
        return parse_key(key_text)
    except ValueError:
        return None
