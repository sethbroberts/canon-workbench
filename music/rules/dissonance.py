"""Dissonance treatment.

Every dissonant pair of notes is classified by its context. A dissonance is
fine if it is one of the style's recognized figures:

  suspension     the note was consonant before (prepared), is held while the
                 other voice moves against it on a stronger beat, then
                 resolves down by step to a consonance
  passing tone   approached and left by step in the same direction, weak beat
  neighbor tone  steps away and back to the same note, weak beat
  anticipation   arrives early on the next note's pitch, weak beat
  cambiata       step down, leap down a third, step up
  échappée       step, then a leap of a third the other way

Anything else is an error. Recognized figures are reported as "info".
"""

from __future__ import annotations

from fractions import Fraction

from . import Finding, Profile
from .intervals import direction, generic, is_consonant, is_leap, is_step, name, simple_generic
from .texture import Sound, Texture


def check(tx: Texture, profile: Profile) -> list[Finding]:
    out: list[Finding] = []
    for t in tx.moments:
        sounding = tx.sounding(t)
        if len(sounding) < 2:
            continue
        low = min(s.midi for s in sounding)
        for i in range(len(sounding)):
            for j in range(i + 1, len(sounding)):
                a, b = sounding[i], sounding[j]
                if a.start != t and b.start != t:
                    continue  # nothing new here
                lower, upper = (a, b) if a.midi <= b.midi else (b, a)
                if is_consonant(lower, upper, against_bass=(lower.midi == low)):
                    continue
                out.append(_classify(tx, a, b, t, profile, against_bass=(lower.midi == low)))
    return out


def _consonant(tx: Texture, x: Sound, y: Sound, t: Fraction) -> bool:
    lower, upper = (x, y) if x.midi <= y.midi else (y, x)
    low = tx.lowest_midi(t)
    return is_consonant(lower, upper, against_bass=(low is not None and lower.midi == low))


def _classify(tx: Texture, a: Sound, b: Sound, t: Fraction, profile: Profile, against_bass: bool) -> Finding:
    voices = tuple(sorted((a.voice, b.voice)))
    what = name(a, b)
    if what == "perfect fourth" and against_bass:
        what = "perfect fourth against the lowest voice"
    attacked = [s for s in (a, b) if s.start == t]
    held = [s for s in (a, b) if s.start < t]
    notes = [(a.voice, a.start), (b.voice, b.start)]
    end = max(a.end, b.end)

    # 1. Is the newly arriving note a recognized figure?
    for n in attacked:
        fig = figure(tx, n)
        if fig and fig in profile.figures:
            return Finding("dissonance_" + fig.replace(" ", "_").replace("é", "e"), "info",
                           f"{what} handled as a {fig} in voice {n.voice}", t, n.end, voices,
                           [(n.voice, n.start)], label=fig)

    # 2. Is the held note a suspension? (A fourth over the bass is the upper
    #    note's dissonance, so only an upper held note can be suspended there.)
    fourth_with_bass_held = (len(held) == 1 and against_bass and simple_generic(a, b) == 4
                             and held[0].midi < attacked[0].midi)
    if len(held) == 1 and not fourth_with_bass_held:
        h, n = held[0], attacked[0]
        result = suspension(tx, h, n, t)
        if result is not None:
            ok, label, problem = result
            if ok:
                return Finding("suspension", "info",
                               f"{label} suspension in voice {h.voice}, prepared and resolved down by step",
                               t, h.end, voices, [(h.voice, h.start)], label=f"{label} suspension")
            return Finding("bad_suspension", "error",
                           f"{what} in voice {h.voice} looks like a suspension but {problem}",
                           t, end, voices, notes, label="suspension problem")

    # 3. Unexplained.
    if len(attacked) == 2:
        msg = f"both voices move into a {what} at once; neither note is a passing or neighbor tone on a weak beat"
    else:
        n = attacked[0]
        strong = tx.weight(t) >= 0.5
        why = "it falls on a strong beat" if strong else "it isn't approached and left by step"
        msg = f"{what}: voice {n.voice} arrives on a dissonance that isn't prepared, and {why}"
    return Finding("unprepared_dissonance", "error", msg, t, end, voices, notes, label="unprepared dissonance")


def figure(tx: Texture, n: Sound) -> str | None:
    """Name the melodic figure that explains dissonant note n, if any."""
    w = tx.weight(n.start)
    p, q = tx.prev(n), tx.next(n)
    if w >= 1.0:
        return None  # no figures on the downbeat in this style
    if p is not None and w > tx.weight(p.start):
        return None  # arrives on a stronger beat than the note before it (accented)
    if p and q and is_step(p, n) and is_step(n, q):
        if direction(p, n) == direction(n, q):
            return "passing tone"
        if q.midi == p.midi:
            return "neighbor tone"
    if q and q.midi == n.midi and (n.end - n.start) <= (q.end - q.start):
        return "anticipation"
    if p and q and is_step(p, n) and direction(p, n) == -1 and generic(n, q) == 3 and direction(n, q) == -1:
        r = tx.next(q)
        if r and is_step(q, r) and direction(q, r) == 1:
            return "cambiata"
    if p and q and is_step(p, n) and is_leap(n, q) and generic(n, q) == 3 and direction(n, q) == -direction(p, n):
        return "échappée"
    return None


def suspension(tx: Texture, h: Sound, n: Sound, t: Fraction) -> tuple[bool, str, str] | None:
    """Check held note h against newly arrived note n at time t.

    Returns None if h is not a suspension at all (e.g. it was never consonant),
    otherwise (ok, label like "7–6", problem description).
    """
    # Preparation: h was consonant with whatever the other voice sang just before.
    before = tx.just_before(n.voice, t)
    if before is not None and before.start >= h.start and not _consonant(tx, h, before, before.start):
        return None
    if before is not None and before.start < h.start and not _consonant(tx, h, before, h.start):
        return None

    # A suspension is syncopated: the held note began on a beat no stronger than
    # the one where the dissonance sounds. A note held from a downbeat to a weaker
    # beat is just a long note with something moving against it.
    if tx.weight(h.start) > tx.weight(t):
        return None
    diss = _number(h, n)

    r = tx.next(h)
    if r is None:
        return False, str(diss), "it never resolves (the voice stops)"
    other = tx.at(n.voice, r.start)
    if is_step(h, r) and direction(h, r) == -1:
        if other is None:
            return True, str(diss), ""
        if _consonant(tx, r, other, r.start):
            return True, f"{diss}–{_number(r, other)}", ""
        return False, str(diss), "it resolves down by step into another dissonance"
    if is_step(h, r) and direction(h, r) == 1:
        return False, str(diss), "it resolves upward (in this style suspensions resolve down by step)"
    return False, str(diss), "it leaves by leap instead of resolving down by step"


def _number(x: Sound, y: Sound) -> int:
    """Figured-bass style number for the interval: 7, 6, 4, 3, and 9 for a compound second above."""
    g = simple_generic(x, y)
    if g == 2 and x.midi > y.midi and generic(x, y) > 8:
        return 9
    return g
