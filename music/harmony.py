"""Chord progressions for writing rounds.

A round works because every phrase fits the same chords: all phrases sound at
once, so they must agree. Here a progression is a list of Roman numerals that
repeats under every phrase, e.g. "I V I I" for a 4-bar phrase (one chord per
bar), or "I V" for two chords spread evenly across the phrase.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from music21 import key as m21key
from music21 import roman

from .model import Melody, Note
from .render import parse_key

PRESETS = {
    "I V I I": "I – V – I – I (simplest)",
    "I IV V I": "I – IV – V – I",
    "I V": "I – V, half a phrase each",
    "I vi IV V": "I – vi – IV – V",
    "I I IV V": "I – I – IV – V",
    "i v i i": "i – v – i – i (minor)",
    "i iv V i": "i – iv – V – i (minor)",
}


@dataclass
class ChordSpan:
    start: Fraction  # within one phrase, in quarter notes
    end: Fraction
    symbol: str
    pitch_classes: frozenset[int]
    names: list[str]  # e.g. ["F", "A", "C"]
    midi: list[int]  # a voicing for the backing chords


class ProgressionError(ValueError):
    pass


def _key(key_text: str) -> m21key.Key:
    return parse_key(key_text) or m21key.Key("C")


def chord_spans(progression: str, phrase_length: Fraction, key_text: str) -> list[ChordSpan]:
    """Spread the progression's chords evenly over one phrase."""
    symbols = (progression or "").replace("–", " ").replace("-", " ").split()
    if not symbols:
        return []
    k = _key(key_text)
    each = phrase_length / len(symbols)
    spans = []
    for i, sym in enumerate(symbols):
        try:
            rn = roman.RomanNumeral(sym, k)
            pitches = rn.pitches
        except Exception as exc:
            raise ProgressionError(f"unknown chord '{sym}' (use Roman numerals like I IV V vi, or i iv V in minor)") from exc
        if not pitches:
            raise ProgressionError(f"unknown chord '{sym}'")
        # Backing voicing: root in octave 3, the rest stacked above it.
        root = pitches[0].pitchClass
        midi = [48 + root if root <= 7 else 36 + root]  # root between G#2 and G3
        for p in pitches[1:]:
            last = midi[-1]
            midi.append(last + ((p.pitchClass - last) % 12 or 12))  # next chord tone above
        spans.append(ChordSpan(each * i, each * (i + 1), sym,
                               frozenset(p.pitchClass for p in pitches),
                               [p.name.replace("-", "b") for p in pitches], midi))
    return spans


def chord_fit(melody: Melody, phrase_length: Fraction, progression: str, key_text: str, weight) -> list[dict]:
    """Strong-beat notes that aren't in the chord sounding under them.

    weight(t) gives the metric weight of time t (as Texture.weight does).
    Notes on weak beats may be passing tones, so only strong beats are checked.
    """
    spans = chord_spans(progression, phrase_length, key_text)
    if not spans:
        return []
    out = []
    pos = Fraction(0)
    tied = False
    for e in melody.events:
        if isinstance(e, Note) and not tied and weight(pos) >= 0.5:
            within = pos % phrase_length
            span = next((s for s in spans if s.start <= within < s.end), spans[-1])
            if e.pitch.midi % 12 not in span.pitch_classes:
                out.append({
                    "phrase": int(pos // phrase_length) + 1,
                    "start": float(pos),
                    "note": str(e.pitch),
                    "chord": span.symbol,
                    "chord_notes": span.names,
                })
        tied = isinstance(e, Note) and e.tie_to_next
        pos += e.duration
    return out


def backing_events(phrase_length: Fraction, progression: str, key_text: str, total: Fraction) -> list[dict]:
    """Chord events for the player, repeating the progression for the whole piece."""
    spans = chord_spans(progression, phrase_length, key_text)
    events = []
    t = Fraction(0)
    while spans and t < total:
        for s in spans:
            start = t + s.start
            if start >= total:
                break
            end = min(t + s.end, total)
            events.append({"midi": s.midi, "start": float(start), "dur": float(end - start)})
        t += phrase_length
    return events
