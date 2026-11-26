"""Turn voices into a music21 score, MusicXML, and SVG (via Verovio)."""

from __future__ import annotations

import os
from fractions import Fraction

import verovio
from music21 import clef, key, meter, note, stream, tie
from music21 import pitch as m21pitch
from music21.musicxml.m21ToXml import GeneralObjectExporter

from .canon import Voice
from .model import Note, Pitch

VEROVIO_DATA = os.path.join(os.path.dirname(verovio.__file__), "data")
LOW_FOR_TREBLE = 55  # below G3: switch to the "tenor" treble clef (sounds an octave lower)


def parse_key(text: str) -> key.Key | None:
    """'C', 'F', 'Bb', 'f#' (lowercase = minor), or '' / 'none' for no key."""
    text = (text or "").strip()
    if not text or text.lower() == "none":
        return None
    tonic = text[0] + text[1:].replace("b", "-")
    try:
        return key.Key(tonic)
    except Exception as exc:  # music21 raises various errors here
        raise ValueError(f"unknown key '{text}' (try C, F, Bb, a, f#)") from exc


def measure_length(time_signature: str) -> Fraction:
    """Length of one bar in quarter lengths: '4/4' -> 4, '3/4' -> 3, '6/8' -> 3."""
    ts = meter.TimeSignature(time_signature)
    return Fraction(ts.barDuration.quarterLength).limit_denominator(64)


def _m21_pitch(p: Pitch) -> m21pitch.Pitch:
    m = m21pitch.Pitch(step=p.step, octave=p.octave)
    if p.alter:
        m.accidental = p.alter
    return m


def build_score(
    voices: list[Voice],
    time_signature: str = "4/4",
    key_text: str = "C",
    title: str | None = None,
) -> stream.Score:
    score = stream.Score()
    if title:
        from music21 import metadata

        score.metadata = metadata.Metadata(title=title)
    k = parse_key(key_text)

    for v in voices:
        part = stream.Part(id=f"voice{v.number}")
        part.partName = f"Voice {v.number}"
        part.partAbbreviation = str(v.number)

        midis = [e.pitch.midi for e in v.events if isinstance(e, Note)]
        part.append(clef.Treble8vbClef() if midis and min(midis) < LOW_FOR_TREBLE else clef.TrebleClef())
        if k is not None:
            part.append(key.KeySignature(k.sharps))
        part.append(meter.TimeSignature(time_signature))

        tied_from_prev = False
        for e in v.events:
            if isinstance(e, Note):
                n = note.Note(_m21_pitch(e.pitch), quarterLength=e.duration)
                if tied_from_prev and e.tie_to_next:
                    n.tie = tie.Tie("continue")
                elif tied_from_prev:
                    n.tie = tie.Tie("stop")
                elif e.tie_to_next:
                    n.tie = tie.Tie("start")
                tied_from_prev = e.tie_to_next
                part.append(n)
            else:
                part.append(note.Rest(quarterLength=e.duration))
                tied_from_prev = False

        part.makeNotation(inPlace=True)  # bars, ties across barlines, beams
        score.insert(0, part)
    return score


def to_musicxml(score: stream.Score) -> str:
    return GeneralObjectExporter(score).parse().decode("utf-8")


def render_svg(musicxml: str, width: int = 2100, scale: int = 40) -> list[str]:
    """Render MusicXML to one SVG string per page."""
    # Point Verovio at its bundled fonts explicitly: it can't find them on its own
    # when called from a web server's worker thread.
    tk = verovio.toolkit(False)
    tk.setResourcePath(VEROVIO_DATA)
    tk.setOptions(
        {
            "pageWidth": width,
            "scale": scale,
            "adjustPageHeight": True,
            "header": "none",
            "footer": "none",
            "breaks": "auto",
            "svgViewBox": True,
        }
    )
    if not tk.loadData(musicxml):
        raise RuntimeError("Verovio could not read the MusicXML")
    return [tk.renderToSVG(page) for page in range(1, tk.getPageCount() + 1)]
