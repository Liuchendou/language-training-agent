"""Tests for Settings.from_env() and whisper-model resolution.

These guard the environment -> Settings mapping, which is easy to break
silently: a missing ``os.getenv`` line just yields the dataclass default and
no test notices unless it is asserted explicitly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.config import Settings
from app.core.media_tools import resolve_whisper_model


def test_from_env_reads_whisper_model_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """LTA_WHISPER_MODEL_DIR must reach Settings.whisper_model_dir.

    Regression guard: from_env() used to omit this field entirely, so a
    user-configured model directory silently fell back to the bundled copy.
    """
    monkeypatch.setenv("LTA_WHISPER_MODEL_DIR", "/opt/whisper-custom")

    assert Settings.from_env().whisper_model_dir == "/opt/whisper-custom"


def test_from_env_whisper_model_dir_defaults_to_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset means "no override", not a broken path or a crash."""
    monkeypatch.delenv("LTA_WHISPER_MODEL_DIR", raising=False)

    assert Settings.from_env().whisper_model_dir == ""


def test_resolve_whisper_model_prefers_explicit_dir(tmp_path: Path) -> None:
    """A configured directory wins over the size name."""
    explicit = tmp_path / "custom-model"
    explicit.mkdir()
    (explicit / "model.bin").write_bytes(b"stub")
    settings = Settings(project_root=tmp_path, whisper_model_dir=str(explicit))

    assert resolve_whisper_model(settings, "base") == str(explicit)


def test_resolve_whisper_model_ignores_dir_without_model(tmp_path: Path) -> None:
    """A configured but incomplete directory is skipped, not returned."""
    incomplete = tmp_path / "half-downloaded"
    incomplete.mkdir()
    settings = Settings(project_root=tmp_path, whisper_model_dir=str(incomplete))

    assert resolve_whisper_model(settings, "base") == "base"


def test_resolve_whisper_model_falls_back_to_size_name(tmp_path: Path) -> None:
    """With nothing configured or bundled, WhisperModel() gets the size name."""
    settings = Settings(project_root=tmp_path)

    assert resolve_whisper_model(settings, "base") == "base"
