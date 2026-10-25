"""sci_estimate: the SCI of a CI run as a pure function and a command line."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

import pytest

from scripts import sci_estimate

BASE: dict[str, Any] = {
    "job_seconds": 1800,
    "vcpus": 2,
    "utilization": 0.5,
    "min_watts": 0.71,
    "max_watts": 4.26,
    "pue": 1.1,
    "grid_g_per_kwh": 579,
    "embodied_g": 0.5,
    "functional_units": 4,
}

CLI_ARGS = [
    "--job-seconds", "1800",
    "--vcpus", "2",
    "--utilization", "0.5",
    "--min-watts", "0.71",
    "--max-watts", "4.26",
    "--pue", "1.1",
    "--grid", "579",
    "--embodied-g", "0.5",
    "--units", "4",
]  # fmt: skip


def test_result_has_exactly_the_specified_keys() -> None:
    assert set(sci_estimate.estimate(**BASE)) == {
        "avg_watts",
        "energy_kwh",
        "operational_g",
        "embodied_g",
        "sci_g_per_unit",
        "inputs",
    }


def test_formulas_follow_the_specification() -> None:
    result = sci_estimate.estimate(**BASE)
    avg_watts = 0.71 + 0.5 * (4.26 - 0.71)
    energy = (1800 / 3600) * 2 * avg_watts / 1000 * 1.1
    operational = energy * 579
    assert result["avg_watts"] == avg_watts
    assert result["energy_kwh"] == energy
    assert result["operational_g"] == operational
    assert result["embodied_g"] == 0.5
    assert result["sci_g_per_unit"] == (operational + 0.5) / 4


def test_known_values_without_rounding() -> None:
    result = sci_estimate.estimate(
        job_seconds=3600,
        vcpus=1,
        utilization=0,
        min_watts=1000,
        max_watts=2000,
        pue=1,
        grid_g_per_kwh=100,
        embodied_g=10,
        functional_units=2,
    )
    assert result["avg_watts"] == 1000
    assert result["energy_kwh"] == 1.0
    assert result["operational_g"] == 100.0
    assert result["sci_g_per_unit"] == 55.0


def test_inputs_travel_with_the_result_unchanged() -> None:
    assert sci_estimate.estimate(**BASE)["inputs"] == BASE


def test_arguments_may_be_positional_or_keyword() -> None:
    assert sci_estimate.estimate(*BASE.values()) == sci_estimate.estimate(**BASE)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("job_seconds", -1),
        ("vcpus", 0),
        ("utilization", -0.1),
        ("utilization", 1.1),
        ("min_watts", -1),
        ("max_watts", 0.5),
        ("pue", 0.99),
        ("grid_g_per_kwh", -1),
        ("embodied_g", -0.1),
        ("functional_units", 0),
        ("job_seconds", float("nan")),
        ("utilization", float("nan")),
    ],
)
def test_invalid_value_names_the_argument(name: str, value: float) -> None:
    with pytest.raises(ValueError, match=name):
        sci_estimate.estimate(**{**BASE, name: value})


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("job_seconds", 0),
        ("vcpus", 1),
        ("utilization", 0),
        ("utilization", 1),
        ("min_watts", 0),
        ("max_watts", 0.71),
        ("pue", 1),
        ("grid_g_per_kwh", 0),
        ("embodied_g", 0),
        ("functional_units", 1),
    ],
)
def test_boundary_values_are_valid(name: str, value: float) -> None:
    sci_estimate.estimate(**{**BASE, name: value})


def test_main_prints_the_result_as_json_and_returns_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert sci_estimate.main(CLI_ARGS) == 0
    out = capsys.readouterr()
    assert json.loads(out.out) == sci_estimate.estimate(**BASE)
    assert out.err == ""


def test_main_reports_an_invalid_value_on_stderr_and_returns_two(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = [*CLI_ARGS]
    args[args.index("--pue") + 1] = "0.5"
    assert sci_estimate.main(args) == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert "pue" in out.err


def test_main_rejects_a_non_numeric_value_with_exit_two(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = [*CLI_ARGS]
    args[args.index("--vcpus") + 1] = "many"
    with pytest.raises(SystemExit) as exc:
        sci_estimate.main(args)
    assert exc.value.code == 2
    assert capsys.readouterr().out == ""


def test_main_requires_every_option(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        sci_estimate.main(CLI_ARGS[:-2])
    assert exc.value.code == 2
    assert capsys.readouterr().out == ""


def test_main_rejects_a_non_finite_value(capsys: pytest.CaptureFixture[str]) -> None:
    args = [*CLI_ARGS]
    args[args.index("--grid") + 1] = "inf"
    assert sci_estimate.main(args) == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert "grid_g_per_kwh" in out.err


def test_module_runs_as_a_command() -> None:
    done = subprocess.run(
        [sys.executable, "-m", "scripts.sci_estimate", *CLI_ARGS],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert done.returncode == 0
    assert json.loads(done.stdout)["inputs"]["vcpus"] == 2
