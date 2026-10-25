"""Tests for the service settings: environment variables prefixed AFAW_WEB_."""

from __future__ import annotations

from pathlib import Path

import pytest

from afaw_web.settings import Settings


def test_data_dir_defaults_to_the_baked_in_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AFAW_WEB_DATA_DIR", raising=False)
    assert Settings().data_dir == Path("/app/data")


def test_data_dir_is_read_from_the_prefixed_environment_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AFAW_WEB_DATA_DIR", str(tmp_path))
    settings = Settings()
    assert settings.data_dir == tmp_path
    assert isinstance(settings.data_dir, Path)


def test_the_unprefixed_variable_is_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("AFAW_WEB_DATA_DIR", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert Settings().data_dir == Path("/app/data")


def test_an_explicit_argument_wins_over_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AFAW_WEB_DATA_DIR", "/somewhere/else")
    assert Settings(data_dir=tmp_path).data_dir == tmp_path
