"""Turn voices into simple note events for the browser player.

Each event is a sounding note: MIDI number, start and length in quarter
notes. Tied notes are merged into one longer event, so they sound as one.
Rests produce no events. Times are in quarter notes (not seconds) so the
player can change tempo freely.
"""

from __future__ import annotations

from fractions import Fraction

from .canon import Voice
from .model import Note


def voice_events(voice: Voice) -> list[dict]:
    events: list[dict] = []
    pos = Fraction(0)
    tied_from_prev = False
    for e in voice.events:
        if isinstance(e, Note):
            if tied_from_prev and events:
                events[-1]["dur"] += float(e.duration)
            else:
                events.append({"midi": e.pitch.midi, "start": float(pos), "dur": float(e.duration)})
            tied_from_prev = e.tie_to_next
        else:
            tied_from_prev = False
        pos += e.duration
    return events


def playback_data(voices: list[Voice]) -> dict:
    total = max((sum((e.duration for e in v.events), Fraction(0)) for v in voices), default=Fraction(0))
    return {
        "length": float(total),  # quarter notes
        "voices": [{"number": v.number, "events": voice_events(v)} for v in voices],
    }
