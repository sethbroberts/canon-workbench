"""Motion between pairs of voices: parallel and hidden fifths and octaves.

parallel   both voices move in the same direction from one perfect fifth
           (or octave/unison) to another                       -> error
contrary   the same, but the voices move in opposite directions -> warning
hidden     the outer voices move in the same direction into a perfect
           interval and the upper voice leaps                   -> warning
"""

from __future__ import annotations

from . import Finding
from .intervals import is_leap, is_octave_or_unison, is_perfect, is_perfect_fifth
from .texture import Texture


def _sign(x: int) -> int:
    return (x > 0) - (x < 0)


def check(tx: Texture) -> list[Finding]:
    out: list[Finding] = []
    nums = tx.voice_numbers
    for ai in range(len(nums)):
        for bi in range(ai + 1, len(nums)):
            out += _check_pair(tx, nums[ai], nums[bi])
    return out


def _check_pair(tx: Texture, va: int, vb: int) -> list[Finding]:
    out: list[Finding] = []
    prev = None
    for t in tx.moments:
        a, b = tx.at(va, t), tx.at(vb, t)
        if a is None or b is None:
            prev = None  # a rest breaks the line
            continue
        if prev == (a, b):
            continue
        if prev is not None:
            pa, pb = prev
            da, db = _sign(a.midi - pa.midi), _sign(b.midi - pb.midi)
            if a is not pa and b is not pb and da != 0 and db != 0:
                for kind, test in (("fifths", is_perfect_fifth), ("octaves", is_octave_or_unison)):
                    if test(pa, pb) and test(a, b):
                        voices = (va, vb)
                        notes = [(va, pa.start), (vb, pb.start), (va, a.start), (vb, b.start)]
                        said = "unisons" if a.midi == b.midi and pa.midi == pb.midi else kind
                        if da == db:
                            out.append(Finding(f"parallel_{kind}", "error",
                                               f"parallel {said} between voices {va} and {vb} "
                                               f"({pa.pitch}–{pb.pitch} to {a.pitch}–{b.pitch})",
                                               pa.start, max(a.end, b.end), voices, notes,
                                               label=f"parallel {said}"))
                        else:
                            out.append(Finding(f"contrary_{kind}", "warning",
                                               f"{kind} by contrary motion between voices {va} and {vb} "
                                               "(avoided in strict style)",
                                               pa.start, max(a.end, b.end), voices, notes,
                                               label=f"{kind} by contrary motion"))
                # Hidden (direct) fifths/octaves: outer voices only.
                if da == db and is_perfect(a, b) and not (is_perfect(pa, pb) and
                                                          is_perfect_fifth(pa, pb) == is_perfect_fifth(a, b)):
                    sounding = tx.sounding(t)
                    hi = max(s.midi for s in sounding)
                    lo = min(s.midi for s in sounding)
                    upper, upper_prev = (a, pa) if a.midi >= b.midi else (b, pb)
                    lower = b if upper is a else a
                    if upper.midi == hi and lower.midi == lo and is_leap(upper_prev, upper):
                        kind = "fifth" if is_perfect_fifth(a, b) else "octave"
                        out.append(Finding(f"hidden_{kind}s", "warning",
                                           f"hidden {kind}: the outer voices ({va} and {vb}) move the same way "
                                           f"into a {kind} with a leap in the upper voice",
                                           t, max(a.end, b.end), (va, vb),
                                           [(va, a.start), (vb, b.start)], label=f"hidden {kind}"))
        prev = (a, b)
    return out
