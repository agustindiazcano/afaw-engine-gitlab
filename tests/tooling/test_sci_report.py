"""SCI of one flow (a merge request and the main pipeline of its merge), from measured seconds."""

from __future__ import annotations

from typing import Any

import pytest

from scripts.sci_report import flow_pipelines, flow_seconds, render, sci_range


def _job(seconds: float | None, name: str = "j") -> dict[str, Any]:
    return {"name": name, "duration": seconds}


def test_seconds_sum_every_job_including_retries_and_skip_unmeasured() -> None:
    jobs = [_job(10.5), _job(20), _job(None), _job(0.25, "retry")]
    assert flow_seconds(jobs) == pytest.approx(30.75)


def test_the_range_uses_the_cloud_carbon_footprint_and_google_figures() -> None:
    low, mid, high = sci_range(3600)
    # 1 h x 2 vCPUs x 0.71 W x PUE 1.1 = 1.562 Wh at 343 g/kWh
    assert low["energy_kwh"] == pytest.approx(0.001562)
    assert low["operational_g"] == pytest.approx(0.001562 * 343)
    assert mid["inputs"]["min_watts"] + 0.5 * (4.26 - 0.71) == pytest.approx(mid["avg_watts"])
    assert high["operational_g"] == pytest.approx(2 * 4.26 * 1.1 / 1000 * 579)
    assert low["embodied_g"] == 0


def test_zero_seconds_gives_zero_carbon() -> None:
    low, _, high = sci_range(0)
    assert low["sci_g_per_unit"] == 0 and high["sci_g_per_unit"] == 0


class FakeApi:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, path: str) -> Any:
        self.calls.append(path)
        if path.startswith("/merge_requests/7/pipelines"):
            return [{"id": 1, "sha": "aaa"}, {"id": 2, "sha": "bbb"}]
        if path == "/merge_requests/7":
            return {"merge_commit_sha": "mmm", "state": "merged"}
        if path.startswith("/pipelines?sha=mmm"):
            return [{"id": 3, "ref": "main"}]
        raise AssertionError(path)


def test_the_flow_is_the_mr_pipelines_plus_the_main_pipeline_of_the_merge() -> None:
    assert flow_pipelines(FakeApi(), 7) == [1, 2, 3]


def test_an_unmerged_mr_has_no_main_pipeline() -> None:
    class Open(FakeApi):
        def get(self, path: str) -> Any:
            if path == "/merge_requests/7":
                return {"merge_commit_sha": None, "state": "opened"}
            return super().get(path)

    assert flow_pipelines(Open(), 7) == [1, 2]


def test_render_states_the_assumptions_and_that_m_and_duo_are_missing() -> None:
    text = render([("!7", 3, 600.0)])
    assert "!7" in text and "600" in text
    assert "SCI without M" in text
    assert "Duo" in text and "not measured" in text
