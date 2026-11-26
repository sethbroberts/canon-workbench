"""Interval arithmetic for the rules.

Intervals are measured two ways at once: by letter names ("generic": a third
is 3, whatever its quality) and by semitones. Together they distinguish a
perfect fifth (5, 7 semitones) from a diminished fifth (5, 6 semitones).
"""

from __future__ import annotations

from .texture import Sound


def generic(a: Sound, b: Sound) -> int:
    """Generic interval size: unison 1, second 2, ... octave 8, ninth 9."""
    return abs(a.diatonic - b.diatonic) + 1


def simple_generic(a: Sound, b: Sound) -> int:
    """Generic size reduced to within an octave; octaves and unisons both report 8 or 1."""
    g = generic(a, b)
    if g == 1:
        return 1
    r = (g - 1) % 7 + 1
    return 8 if r == 1 else r


def semitones(a: Sound, b: Sound) -> int:
    return abs(a.midi - b.midi)


def is_perfect_fifth(a: Sound, b: Sound) -> bool:
    return simple_generic(a, b) == 5 and semitones(a, b) % 12 == 7


def is_octave_or_unison(a: Sound, b: Sound) -> bool:
    return simple_generic(a, b) in (1, 8) and semitones(a, b) % 12 == 0


def is_perfect(a: Sound, b: Sound) -> bool:
    return is_perfect_fifth(a, b) or is_octave_or_unison(a, b)


def is_consonant(a: Sound, b: Sound, against_bass: bool) -> bool:
    """Consonance in the Renaissance sense.

    Unisons, octaves, perfect fifths, thirds and sixths are consonant.
    A perfect fourth (or a tritone) counts as consonant only between upper
    voices; against the lowest sounding voice it is a dissonance.
    """
    g = simple_generic(a, b)
    s = semitones(a, b) % 12
    if g in (1, 8):
        return s == 0
    if g == 5:
        return s == 7 or (s == 6 and not against_bass)  # d5 between upper voices
    if g == 3:
        return s in (3, 4)
    if g == 6:
        return s in (8, 9)
    if g == 4:
        return s in (5, 6) and not against_bass  # P4 or A4 between upper voices
    return False


def name(a: Sound, b: Sound) -> str:
    """A readable interval name like 'perfect fifth' or 'minor seventh'."""
    g = simple_generic(a, b)
    s = semitones(a, b) % 12
    names = {
        (1, 0): "unison", (8, 0): "octave", (2, 1): "minor second", (2, 2): "major second",
        (3, 3): "minor third", (3, 4): "major third", (4, 5): "perfect fourth",
        (4, 6): "augmented fourth", (5, 6): "diminished fifth", (5, 7): "perfect fifth",
        (6, 8): "minor sixth", (6, 9): "major sixth", (7, 10): "minor seventh",
        (7, 11): "major seventh", (2, 3): "augmented second", (7, 9): "diminished seventh",
        (5, 8): "augmented fifth", (4, 4): "diminished fourth",
    }
    return names.get((g, s), f"{g}th ({s} semitones)")


# ---- melodic motion ----

def direction(a: Sound, b: Sound) -> int:
    """+1 up, -1 down, 0 repeated pitch (by staff position)."""
    d = b.diatonic - a.diatonic
    return (d > 0) - (d < 0)


def is_step(a: Sound, b: Sound) -> bool:
    return generic(a, b) == 2 and 1 <= semitones(a, b) <= 2


def is_leap(a: Sound, b: Sound) -> bool:
    return generic(a, b) >= 3
