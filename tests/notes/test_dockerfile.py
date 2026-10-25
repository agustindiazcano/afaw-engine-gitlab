"""Tests for the notes app Dockerfile: the HEALTHCHECK uses only the standard library."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DOCKERFILE = Path(__file__).resolve().parents[2] / "src" / "notes_app" / "Dockerfile"


def _text() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


def _healthcheck() -> str:
    """Return the HEALTHCHECK instruction with its line continuations joined."""
    joined = _text().replace("\\\n", " ")
    lines = [ln for ln in joined.splitlines() if ln.strip().startswith("HEALTHCHECK")]
    assert len(lines) == 1, "the Dockerfile must have exactly one HEALTHCHECK instruction"
    return lines[0]


def test_healthcheck_interval_and_timeout() -> None:
    instruction = _healthcheck()
    assert "--interval=30s" in instruction
    assert "--timeout=3s" in instruction


def test_healthcheck_calls_health_on_port_with_default() -> None:
    instruction = _healthcheck()
    assert "/health" in instruction
    assert "PORT" in instruction
    assert "8080" in instruction


def test_healthcheck_uses_python_standard_library_only() -> None:
    instruction = _healthcheck()
    assert "python" in instruction
    assert "urllib.request" in instruction
    assert "curl" not in instruction
    assert "wget" not in instruction


@pytest.mark.characterization(reason="the image already installs only requirements.txt")
def test_no_new_package_is_installed() -> None:
    text = _text()
    assert not re.search(r"apt-get|apt install|apk add|yum install", text)
    assert text.count("pip install") == 1
    assert "pip install --no-cache-dir -r requirements.txt" in text
