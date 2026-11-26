import sys

from music import export


def test_install_hint_matches_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert export.install_hint() == "brew install lilypond"
    monkeypatch.setattr(sys, "platform", "linux")
    assert export.install_hint() == "pip install lilypond"


def test_finds_homebrew_lilypond_when_not_on_path(monkeypatch, tmp_path):
    fake = tmp_path / "lilypond"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setattr(export.shutil, "which", lambda name: None)
    monkeypatch.setattr(export, "HOMEBREW_LILYPOND", [str(tmp_path / "missing"), str(fake)])
    assert export.lilypond_executable() == str(fake)


def test_missing_lilypond_gives_install_hint(monkeypatch):
    monkeypatch.setattr(export, "lilypond_executable", lambda: None)
    monkeypatch.setattr(sys, "platform", "darwin")
    try:
        export.to_pdf("{ c'4 }")
    except export.LilyPondError as exc:
        assert "brew install lilypond" in str(exc)
    else:
        raise AssertionError("expected LilyPondError")
