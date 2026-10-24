"""Fixtures: a throwaway data directory laid out like the one baked into the service image."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from afaw_web.app import create_app
from afaw_web.settings import Settings

METRICS = {
    "as_of": "2026-10-24T19:48:38-03:00",
    "ci_per_done_task": {"job_minutes": {"median": 3.5}},
}
PENDING = [{"id": "task_001", "light": "green"}]
HISTORY = [{"id": "task_000", "merged": 1}]
ADR = (
    "---\nstatus: proposed\ndate: 2026-10-24\n---\n# Measured coverage is 80% of lines\n\n"
    "## Context\nThe mutation gate requires 80.0 percent.\nUnrelated line.\n\n"
    "## Decision\nKeep it.\n"
)
GOTCHA = (
    "---\nstatus: active\ndate: 2026-10-24\n---\n# Empty delta\n\n"
    "## Symptom\nfiles_touched is empty.\n"
)
LASTCONTEXT = "# Last context\n\n- Progress: 10 of 10 tasks done (100%).\n"


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """A complete data directory: live views, the demo page and the knowledge records."""
    live = tmp_path / "live"
    (live / "context" / "global").mkdir(parents=True)
    (live / "metrics.json").write_text(json.dumps(METRICS), encoding="utf-8")
    (live / "pending.json").write_text(json.dumps(PENDING), encoding="utf-8")
    (live / "history.json").write_text(json.dumps(HISTORY), encoding="utf-8")
    (live / "dashboard.html").write_text("<html>live dashboard</html>", encoding="utf-8")
    (live / "context" / "global" / "LASTCONTEXT.md").write_text(LASTCONTEXT, encoding="utf-8")
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "index.html").write_text("<html>demo dashboard</html>", encoding="utf-8")
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "gotchas").mkdir()
    (tmp_path / "docs" / "adr" / "0001-coverage.md").write_text(ADR, encoding="utf-8")
    (tmp_path / "docs" / "gotchas" / "0001-delta.md").write_text(GOTCHA, encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(data_dir: Path) -> TestClient:
    """A test client over an application serving ``data_dir``."""
    return TestClient(create_app(Settings(data_dir=data_dir)))
