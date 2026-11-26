"""Turn one melody plus canon settings into several voices.

A round is the simplest case: interval "P1" (unison) and a delay equal to
one phrase. A canon at the fifth uses interval "P5", and so on.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from fractions import Fraction

from music21 import interval as m21interval
from music21 import pitch as m21pitch

from .model import Event, Melody, Note, Pitch, Rest

# Friendly names for the interval menu in the web page -> music21 interval names.
INTERVAL_CHOICES = {
    "unison": "P1",
    "octave above": "P8",
    "octave below": "P-8",
    "fifth above": "P5",
    "fifth below": "P-5",
    "fourth above": "P4",
    "fourth below": "P-4",
}

ENDINGS = ("stagger", "together")


@dataclass
class CanonSettings:
    voices: int = 3
    delay: Fraction = Fraction(8)  # quarter lengths between one entry and the next
    interval: str = "P1"  # each voice is this far from the voice before it
    repeats: int = 1  # how many times each voice sings the melody
    ending: str = "stagger"  # "stagger": voices finish in turn; "together": all stop with the last voice
    octave_shifts: list[int] = field(default_factory=list)  # per voice, e.g. [0, 0, -1] (optional)

    def validate(self) -> list[str]:
        problems = []
        if not 1 <= self.voices <= 8:
            problems.append("number of voices must be between 1 and 8")
        if self.delay <= 0:
            problems.append("entry delay must be greater than zero")
        if self.repeats < 1:
            problems.append("repeats must be at least 1")
        if self.ending not in ENDINGS:
            problems.append(f"ending must be one of {ENDINGS}")
        try:
            m21interval.Interval(self.interval)
        except Exception:
            problems.append(f"unknown interval '{self.interval}' (try P1, P5, P-4, P8)")
        return problems


@dataclass
class Voice:
    number: int  # 1-based
    start: Fraction  # where this voice enters, in quarter lengths
    events: list[Event]  # leading rest, the melody, trailing rest: all voices end together


def transpose_pitch(p: Pitch, interval_name: str, times: int = 1) -> Pitch:
    """Transpose a pitch by a named interval, keeping correct spelling."""
    if times == 0 or interval_name == "P1":
        return p
    m = m21pitch.Pitch(step=p.step, octave=p.octave)
    if p.alter:
        m.accidental = p.alter
    iv = m21interval.Interval(interval_name)
    for _ in range(times):
        m = iv.transposePitch(m)
    alter = int(m.accidental.alter) if m.accidental else 0
    return Pitch(m.step, alter, m.octave)


def _shift(event: Event, interval_name: str, times: int, octaves: int) -> Event:
    if isinstance(event, Rest):
        return event
    p = transpose_pitch(event.pitch, interval_name, times)
    if octaves:
        p = Pitch(p.step, p.alter, p.octave + octaves)
    return replace(event, pitch=p)  # keeps duration, tie and lyric


def _cycle(events: list[Event], length: Fraction) -> list[Event]:
    """Repeat events as needed to fill exactly `length`, cutting the last one short."""
    out: list[Event] = []
    if not events or length <= 0:
        return out
    filled = Fraction(0)
    while filled < length:
        for e in events:
            if filled >= length:
                break
            room = length - filled
            if e.duration <= room:
                out.append(e)
                filled += e.duration
            else:  # cut the final note to fit
                out.append(Rest(room) if isinstance(e, Rest) else replace(e, duration=room, tie_to_next=False))
                filled += room
    # A tie can't point past the end.
    if out and isinstance(out[-1], Note) and out[-1].tie_to_next:
        last = out[-1]
        out[-1] = replace(last, tie_to_next=False)
    return out


def build_canon(melody: Melody, settings: CanonSettings) -> list[Voice]:
    problems = settings.validate()
    if problems:
        raise ValueError("; ".join(problems))
    length = melody.duration
    n = settings.voices
    starts = [settings.delay * k for k in range(n)]

    if settings.ending == "together":
        end = starts[-1] + length * settings.repeats
        sung_lengths = [end - s for s in starts]
    else:
        sung_lengths = [length * settings.repeats] * n
        end = starts[-1] + sung_lengths[-1]

    voices = []
    for k in range(n):
        octaves = settings.octave_shifts[k] if k < len(settings.octave_shifts) else 0
        line = [_shift(e, settings.interval, k, octaves) for e in melody.events]
        body = _cycle(line, sung_lengths[k])
        events: list[Event] = []
        if starts[k] > 0:
            events.append(Rest(starts[k]))
        events.extend(body)
        tail = end - starts[k] - sung_lengths[k]
        if tail > 0:
            events.append(Rest(tail))
        voices.append(Voice(k + 1, starts[k], events))
    return voices
