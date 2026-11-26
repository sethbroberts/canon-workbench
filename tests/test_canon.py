from fractions import Fraction

import pytest

from music.canon import CanonSettings, build_canon, transpose_pitch
from music.model import Note, Pitch, Rest
from music.parser import parse_melody
from music.render import build_score, measure_length, parse_key, render_svg, to_musicxml

FRERE = "F4 G4 A4 F4 | F4 G4 A4 F4 | A4 Bb4 C5/2 | A4/4 Bb4 C5/2"


def durations(voice):
    return sum((e.duration for e in voice.events), Fraction(0))


def test_round_entries_and_equal_lengths():
    m = parse_melody(FRERE)  # 16 beats
    voices = build_canon(m, CanonSettings(voices=3, delay=Fraction(8)))
    assert [v.start for v in voices] == [0, 8, 16]
    # stagger: each sings once, last voice ends at 16 + 16 = 32
    assert all(durations(v) == 32 for v in voices)
    assert isinstance(voices[1].events[0], Rest) and voices[1].events[0].duration == 8
    assert voices[0].events[-1].duration == 16  # leader rests at the end


def test_together_ending_cuts_all_voices_at_once():
    m = parse_melody(FRERE)
    voices = build_canon(m, CanonSettings(voices=3, delay=Fraction(8), ending="together"))
    assert all(durations(v) == 32 for v in voices)
    # leader keeps singing (no trailing rest)
    assert isinstance(voices[0].events[-1], Note)


def test_repeats():
    m = parse_melody(FRERE)
    voices = build_canon(m, CanonSettings(voices=2, delay=Fraction(4), repeats=2))
    assert durations(voices[0]) == 4 + 32


def test_canon_at_the_fifth_spelling():
    assert transpose_pitch(Pitch("B", -1, 4), "P5").name == "F5"
    assert transpose_pitch(Pitch("F", 0, 4), "P5", times=2).name == "G5"
    assert transpose_pitch(Pitch("C", 0, 4), "P-4").name == "G3"


def test_canon_interval_applied_per_voice():
    m = parse_melody("C4 D4 E4 F4")
    voices = build_canon(m, CanonSettings(voices=2, delay=Fraction(2), interval="P5"))
    first_note = next(e for e in voices[1].events if isinstance(e, Note))
    assert first_note.pitch.name == "G4"


def test_octave_shift():
    m = parse_melody("C5 D5")
    voices = build_canon(m, CanonSettings(voices=2, delay=Fraction(1), octave_shifts=[0, -1]))
    assert next(e for e in voices[1].events if isinstance(e, Note)).pitch.name == "C4"


def test_bad_settings():
    with pytest.raises(ValueError):
        build_canon(parse_melody("C4"), CanonSettings(interval="Q7"))


def test_key_and_meter_helpers():
    assert parse_key("Bb").sharps == -2
    assert parse_key("f#").mode == "minor"
    assert parse_key("") is None
    assert measure_length("3/4") == 3
    assert measure_length("6/8") == 3


def test_score_musicxml_and_svg():
    m = parse_melody(FRERE + " | A4~ A4 G4/2")
    voices = build_canon(m, CanonSettings(voices=4, delay=Fraction(4)))
    score = build_score(voices, "4/4", "F")
    assert len(score.parts) == 4
    xml = to_musicxml(score)
    assert xml.count("<part ") == 4
    assert '<tie type="start"' in xml
    pages = render_svg(xml)
    assert pages and pages[0].lstrip().startswith("<svg")


def test_svg_renders_in_a_worker_thread():
    """Flask serves requests on threads; Verovio must still find its fonts."""
    import threading

    xml = to_musicxml(build_score(build_canon(parse_melody("C4 D4"), CanonSettings(voices=2, delay=Fraction(1)))))
    result = {}
    t = threading.Thread(target=lambda: result.update(pages=render_svg(xml)))
    t.start()
    t.join()
    assert result["pages"][0].lstrip().startswith("<svg")
