"""Each rule gets small examples that must pass and must fail.

Voices are written directly (not as a canon) so each example isolates one idea.
"""

from fractions import Fraction

from music.canon import CanonSettings, Voice, build_canon
from music.parser import parse_melody
from music.rules import check_canon


def voices(*lines):
    return [Voice(i + 1, Fraction(0), parse_melody(t).events) for i, t in enumerate(lines)]


def run(*lines, key="", ts="4/4"):
    findings, _ = check_canon(voices(*lines), ts, key_text=key, unison=False)
    return findings


def rules(findings, severity=None):
    """Rule names found, ignoring range warnings (many examples use low bass notes)."""
    return sorted(f.rule for f in findings
                  if (severity is None or f.severity == severity) and f.rule != "range")


def labels(findings):
    """Labels of recognized dissonances."""
    return sorted(f.label for f in findings if f.severity == "info")


# ---- consonance ----

def test_thirds_and_sixths_are_clean():
    assert rules(run("E5/1 F5/1", "C5/1 A4/1"), "error") == []


def test_fourth_against_the_bass_is_dissonant_but_not_between_upper_voices():
    # G4-C5 is a fourth between upper voices (C4 is the bass): consonant.
    assert rules(run("C5/1", "G4/1", "C4/1"), "error") == []
    # The same fourth with nothing below it is a dissonance against the bass.
    assert "unprepared_dissonance" in rules(run("C5/1", "G4/1"), "error")


# ---- suspensions ----

SUS_UPPER = "R/2 C5/2 ~C5/2 B4/2 | C5/1"
SUS_LOWER = "R/2 E4/2 | D4/1 | C4/1"


def test_seven_six_suspension_is_recognized():
    f = run(SUS_UPPER, SUS_LOWER)
    assert rules(f, "error") == []
    sus = [x for x in f if x.rule == "suspension"]
    assert len(sus) == 1 and sus[0].label == "7–6 suspension"


def test_four_three_suspension_is_recognized():
    # F4 held over C4 bass on the downbeat, resolving to E4.
    f = run("R/2 F4/2 ~F4/2 E4/2", "R/2 A3/2 | C4/1")
    assert [x.label for x in f if x.rule == "suspension"] == ["4–3 suspension"]


def test_suspension_resolving_upward_is_an_error():
    f = run("R/2 C5/2 ~C5/2 D5/2", SUS_LOWER)
    assert "bad_suspension" in rules(f, "error")
    assert "upward" in next(x.message for x in f if x.rule == "bad_suspension")


def test_suspension_leaving_by_leap_is_an_error():
    f = run("R/2 C5/2 ~C5/2 G4/2", SUS_LOWER)
    assert "bad_suspension" in rules(f, "error")


def test_upper_voice_leaping_to_a_fourth_over_held_bass_is_not_called_a_suspension():
    f = run("R/2 E4/2 | C5/1", "R/2 G3/2 ~G3/2 G3/2")
    assert "unprepared_dissonance" in rules(f, "error")
    assert "bad_suspension" not in rules(f)


def test_bass_suspension_two_three():
    # Bass D3 is held while the upper voice moves to E4 (a ninth, figured "2");
    # the bass then resolves down to C3, a tenth below E4 (figured "3").
    f = run("R/2 F4/2 | E4/1", "R/2 D3/2 ~D3/2 C3/2")
    assert [x.label for x in f if x.rule == "suspension"] == ["2–3 suspension"]


def test_unprepared_dissonance_on_the_beat():
    f = run("R/2 E4/2 | C5/1", "R/2 C4/2 | D4/1")
    assert "unprepared_dissonance" in rules(f, "error")


# ---- figures ----

def test_passing_tone():
    f = run("C5/4 D5/4 E5/2", "C4/1")
    assert rules(f, "error") == []
    assert labels(f) == ["passing tone"]


def test_accented_passing_tone_is_an_error():
    # D5 arrives on beat 3, stronger than the C5 before it.
    f = run("C5/4 C5/4 D5/4 E5/4", "C4/1")
    assert "unprepared_dissonance" in rules(f, "error")


def test_dissonance_on_the_downbeat_is_an_error_even_if_stepwise():
    f = run("C5/2 B4/2 | A4/1", "C4/2 E4/2 | B3/1")
    assert "unprepared_dissonance" in rules(f, "error")


def test_neighbor_tone():
    f = run("C5/4 D5/4 C5/2", "C4/1")
    assert labels(f) == ["neighbor tone"]


def test_cambiata():
    f = run("D5/4 C5/4 A4/4 B4/4", "D4/1")
    assert labels(f) == ["cambiata"]


def test_echappee():
    f = run("B4/4 C5/4 A4/2", "D4/1")
    assert labels(f) == ["échappée"]


def test_anticipation():
    f = run("E5/2 C5/4. B4/8 | B4/1", "C4/1 | G3/1")
    assert "anticipation" in labels(f)
    assert rules(f, "error") == []


# ---- parallels ----

def test_parallel_fifths():
    assert "parallel_fifths" in rules(run("G4/1 A4/1", "C4/1 D4/1"), "error")


def test_parallel_octaves_and_unisons():
    assert "parallel_octaves" in rules(run("C5/1 D5/1", "C4/1 D4/1"), "error")
    f = run("A4/1 F4/1", "A4/1 F4/1")
    assert "parallel_octaves" in rules(f, "error")
    assert "unisons" in next(x.message for x in f if x.rule == "parallel_octaves")


def test_oblique_motion_into_fifth_is_fine():
    assert rules(run("G4/1 A4/1", "C4/1 D4/2 D4/2"), "error") == rules(run("G4/1 A4/1", "C4/1 D4/1"), "error")
    assert rules(run("G4/1 G4/1", "C4/1 C4/1")) == []


def test_contrary_octaves_warning():
    f = run("C5/1 G4/1", "C4/1 G4/1")
    assert "contrary_octaves" in rules(f, "warning")


def test_rest_breaks_parallel_check():
    assert rules(run("G4/1 R/1 A4/1", "C4/1 R/1 D4/1"), "error") == []


def test_hidden_fifth_in_outer_voices():
    f = run("E5/1 G5/1", "G3/1 C4/1")
    assert "hidden_fifths" in rules(f, "warning")


# ---- melody ----

def test_bad_leaps():
    assert "augmented_leap" in rules(run("F4 G#4 A4"))
    assert "seventh_leap" in rules(run("C4 B4 A4"))
    assert "leap_over_octave" in rules(run("C4 E5 D5"))


def test_unrecovered_leap():
    assert "unrecovered_leap" in rules(run("E4 C5 D5"))
    assert "unrecovered_leap" not in rules(run("E4 C5 B4"))


def test_range():
    f = run("C4 D4 E4 G5")
    r = [x for x in f if x.rule == "range"]
    assert len(r) == 1 and len(r[0].notes) == 2


def test_final_tonic():
    assert "final_not_tonic" in rules(run("E4 F4 G4", key="C"))
    assert "final_not_tonic" not in rules(run("E4 D4 C4", key="C"))


# ---- whole canons ----

FRERE = """F4/4 G4 A4 F4 | F4 G4 A4 F4 | A4 Bb4 C5/2 | A4/4 Bb4 C5/2 |
C5/8 D5 C5 Bb4 A4/4 F4 | C5/8 D5 C5 Bb4 A4/4 F4 | F4 C4 F4/2 | F4/4 C4 F4/2"""


def test_frere_jacques_as_a_round():
    m = parse_melody(FRERE)
    v = build_canon(m, CanonSettings(voices=4, delay=Fraction(8)))
    f, _ = check_canon(v, "4/4", key_text="F", melody_length=m.duration)
    # Its only real faults: parallel unisons (A4-F4 in two voices at once) in bars 5-8.
    assert set(rules(f, "error")) == {"parallel_octaves"}
    assert labels([x for x in f if x.severity == "info"]).count("passing tone") == 18
    assert "suspension" not in rules(f)


def test_finding_dict_has_bar_and_playback_range():
    m = parse_melody(FRERE)
    v = build_canon(m, CanonSettings(voices=4, delay=Fraction(8)))
    f, tx = check_canon(v, "4/4", key_text="F", melody_length=m.duration)
    d = next(x for x in f if x.rule == "parallel_octaves").to_dict(tx)
    assert d["bar"] == 5 and d["beat"] == 3
    assert d["play_from"] == 16 and d["play_to"] == 20
