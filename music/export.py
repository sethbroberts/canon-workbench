"""Exports: MusicXML, MIDI, LilyPond source, and PDF (via LilyPond).

Two printed layouts:
  round  the traditional way to print a round: the melody once, on one staff,
         with circled numbers where each new voice comes in
  score  every voice written out on its own staff
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from fractions import Fraction

from music21 import metadata, midi, stream, tempo

from .canon import INTERVAL_CHOICES, CanonSettings, Voice, build_canon
from .model import Melody
from .render import build_score, measure_length, parse_key

LY_DURATION = {"breve": "\\breve", "whole": "1", "half": "2", "quarter": "4",
               "eighth": "8", "16th": "16", "32nd": "32", "64th": "64"}
NUMBER_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}


@dataclass
class PieceInfo:
    title: str = ""
    composer: str = ""
    dedication: str = ""


# ---- MusicXML and MIDI ----

def with_metadata(score: stream.Score, info: PieceInfo) -> stream.Score:
    md = metadata.Metadata()
    if info.title:
        md.title = info.title
    if info.composer:
        md.composer = info.composer
    score.metadata = md
    return score


def to_midi(score: stream.Score, bpm: int = 96) -> bytes:
    s = score.__deepcopy__()
    s.parts[0].measure(1).insert(0, tempo.MetronomeMark(number=bpm))
    mf = midi.translate.streamToMidiFile(s)
    return mf.writestr()


# ---- LilyPond ----

def ly_pitch(p) -> str:
    """music21 pitch -> LilyPond absolute pitch (c' is middle C)."""
    step = p.step.lower()
    alter = int(p.accidental.alter) if p.accidental else 0
    if alter > 0:
        name = step + "is" * alter  # fis, fisis
    elif alter < 0 and step in ("e", "a"):
        name = step + "s" + "es" * (-alter - 1)  # es, eses; as, ases
    elif alter < 0:
        name = step + "es" * -alter  # bes, beses
    else:
        name = step
    if p.octave is None:  # a key's tonic has no octave
        return name
    octave = p.octave - 3
    return name + ("'" * octave if octave > 0 else "," * -octave)


def ly_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _ly_music(part: stream.Part, marks: dict | None = None) -> tuple[str, str]:
    """(LilyPond notes, LilyPond lyrics) for one music21 part made by build_score.

    marks maps a quarter-note offset to markup text placed above the note there.
    """
    marks = dict(marks or {})
    notes: list[str] = []
    words: list[str] = []
    measures = list(part.getElementsByClass(stream.Measure))
    bar_len = measures[0].barDuration.quarterLength if measures else 4
    for m in measures:
        bar: list[str] = []
        elements = list(m.notesAndRests)
        for el in elements:
            pieces = el.splitAtDurations() if el.duration.type in ("complex", "inexpressible") else [el]
            for k, x in enumerate(pieces):
                dur = LY_DURATION.get(x.duration.type, "4") + "." * x.duration.dots
                start = Fraction(m.offset + x.offset).limit_denominator(64)
                end = start + Fraction(x.quarterLength).limit_denominator(64)
                if x.isRest:
                    full_bar = len(elements) == 1 and x.quarterLength == bar_len
                    bar.append(("R" if full_bar else "r") + dur)
                    continue
                token = ly_pitch(x.pitch) + dur
                for at in sorted(marks):
                    if start <= at < end:
                        token += f"^\\markup {{ \\circle \\bold {ly_quote(marks.pop(at))} }}"
                        break
                tie = x.tie is not None and x.tie.type in ("start", "continue")
                if tie or k < len(pieces) - 1:
                    token += "~"
                bar.append(token)
                continuing = (x.tie is not None and x.tie.type in ("stop", "continue")) or k > 0
                if not continuing:
                    if x.lyrics:
                        ly = x.lyrics[0]
                        words.append(ly_quote(ly.text) + (" --" if ly.syllabic in ("begin", "middle") else ""))
                    else:
                        words.append("_")
        notes.append(" ".join(bar) + " |")
    # Trailing "_" placeholders add nothing.
    while words and words[-1] == "_":
        words.pop()
    if not any(w != "_" for w in words):
        words = []
    return "\n    ".join(notes), " ".join(words)


def _ly_header(info: PieceInfo, subtitle: str) -> str:
    lines = ["\\header {"]
    if info.dedication:
        lines.append(f"  dedication = {ly_quote(info.dedication)}")
    lines.append(f"  title = {ly_quote(info.title or 'Untitled')}")
    if subtitle:
        lines.append(f"  subtitle = {ly_quote(subtitle)}")
    if info.composer:
        lines.append(f"  composer = {ly_quote(info.composer)}")
    lines.append("  tagline = ##f")
    lines.append("}")
    return "\n".join(lines)


def _ly_key_time(key_text: str, time_signature: str) -> str:
    k = parse_key(key_text)
    out = f"\\time {time_signature}"
    if k is not None:
        tonic = ly_pitch(k.tonic).rstrip("',")
        out = f"\\key {tonic} \\{k.mode} " + out
    return out


def _clef(part: stream.Part) -> str:
    from music21 import clef

    c = part.recurse().getElementsByClass(clef.Clef).first()
    return "treble_8" if isinstance(c, clef.Treble8vbClef) else "treble"


def _interval_words(code: str) -> str:
    for words, c in INTERVAL_CHOICES.items():
        if c == code:
            return words
    return code


def instructions(settings: CanonSettings, melody_length: Fraction, bar: Fraction) -> str:
    n = settings.voices
    if n == 1:
        return ""
    count = NUMBER_WORDS.get(n, str(n))
    gap = settings.delay / bar
    gap_text = f"{gap:g} bar{'s' if gap != 1 else ''}" if gap == int(gap) else f"{float(settings.delay):g} beats"
    if settings.interval == "P1":
        text = (f"A round for {count} voices. Each voice starts at the beginning when the voice before it "
                f"reaches the next circled number ({gap_text} later).")
    else:
        text = (f"A canon for {count} voices. Each voice enters at the next circled number, "
                f"{_interval_words(settings.interval)} the voice before it.")
    if settings.repeats > 1:
        text += f" Sing it {NUMBER_WORDS.get(settings.repeats, settings.repeats)} times through."
    return text


def lilypond_source(
    melody: Melody,
    settings: CanonSettings,
    time_signature: str,
    key_text: str,
    info: PieceInfo,
    layout: str = "round",
) -> str:
    bar = measure_length(time_signature)
    key_time = _ly_key_time(key_text, time_signature)
    lines = ['\\version "2.24.0"', "", '#(set-paper-size "letter")', ""]

    if layout == "round":
        one = build_canon(melody, CanonSettings(voices=1, repeats=1))
        part = build_score(one, time_signature, key_text).parts[0]
        marks = {}
        for k in range(settings.voices):
            at = settings.delay * k
            if at < melody.duration:
                marks[at] = str(k + 1)
        music, words = _ly_music(part, marks)
        subtitle = (f"Round for {NUMBER_WORDS.get(settings.voices, settings.voices)} voices"
                    if settings.interval == "P1" else
                    f"Canon for {NUMBER_WORDS.get(settings.voices, settings.voices)} voices")
        lines += ["#(set-global-staff-size 22)", "", _ly_header(info, subtitle if settings.voices > 1 else ""), ""]
        lines += ["melody = {", f"  \\clef {_clef(part)} {key_time}", f"    {music}", '  \\bar "|."', "}", ""]
        lines += ["\\score {", "  <<", '    \\new Voice = "v" \\melody']
        if words:
            lines.append(f'    \\new Lyrics \\lyricsto "v" {{ {words} }}')
        lines += ["  >>", "  \\layout { indent = 0 }", "}"]
        text = instructions(settings, melody.duration, bar)
        if text:
            lines += ["", f"\\markup \\vspace #2", f"\\markup \\fill-line {{ \\wordwrap-string {ly_quote(text)} }}"]
    else:
        voices = build_canon(melody, settings)
        score = build_score(voices, time_signature, key_text)
        subtitle = instructions(settings, melody.duration, bar).split(".")[0] if settings.voices > 1 else ""
        lines += ["#(set-global-staff-size 18)", "", _ly_header(info, subtitle), ""]
        staves = []
        for i, part in enumerate(score.parts, start=1):
            music, words = _ly_music(part)
            name = f"v{i}"
            lines += [f"voice{chr(64 + i)} = {{", f"  \\clef {_clef(part)} {key_time}", f"    {music}", '  \\bar "|."', "}", ""]
            staff = (f'    \\new Staff \\with {{ instrumentName = "{i}" }} '
                     f'\\new Voice = "{name}" \\voice{chr(64 + i)}')
            staves.append(staff)
            if words:
                staves.append(f'    \\new Lyrics \\lyricsto "{name}" {{ {words} }}')
        lines += ["\\score {", "  \\new ChoirStaff <<"] + staves + ["  >>", "  \\layout { }", "}"]
    return "\n".join(lines) + "\n"


# ---- PDF ----

# Where Homebrew puts LilyPond on a Mac (Apple Silicon, then Intel), in case the
# app was started without Homebrew on the PATH.
HOMEBREW_LILYPOND = ["/opt/homebrew/bin/lilypond", "/usr/local/bin/lilypond"]


def install_hint() -> str:
    """How to install LilyPond on this computer."""
    if sys.platform == "darwin":
        return "brew install lilypond"
    return "pip install lilypond"


def lilypond_executable() -> str | None:
    """Find LilyPond: on the PATH, in Homebrew's folders, or from the 'lilypond' Python package."""
    found = shutil.which("lilypond")
    if found:
        return found
    for path in HOMEBREW_LILYPOND:
        if os.access(path, os.X_OK):
            return path
    try:
        import lilypond  # pip install lilypond

        return str(lilypond.executable())
    except Exception:
        return None


class LilyPondError(RuntimeError):
    pass


def to_pdf(ly_source: str, timeout: int = 120) -> bytes:
    exe = lilypond_executable()
    if exe is None:
        raise LilyPondError(f"LilyPond isn't installed. Run: {install_hint()}  (or get it from lilypond.org), "
                            "then restart the app.")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "piece.ly")
        with open(src, "w", encoding="utf-8") as f:
            f.write(ly_source)
        result = subprocess.run(
            [exe, "-dno-point-and-click", "-o", os.path.join(tmp, "piece"), src],
            capture_output=True, text=True, timeout=timeout,
        )
        pdf = os.path.join(tmp, "piece.pdf")
        if result.returncode != 0 or not os.path.exists(pdf):
            tail = "\n".join(result.stderr.strip().splitlines()[-8:])
            raise LilyPondError(f"LilyPond couldn't engrave the piece:\n{tail}")
        with open(pdf, "rb") as f:
            return f.read()
