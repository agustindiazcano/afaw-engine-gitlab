"""Software Carbon Intensity estimate of a CI run, as a pure function and a command line.

SCI = (O + M) per R, with O = E x I (docs/adr/0009-measure-sustainability-with-sci.md). Every
coefficient is an input, never a constant: the assumptions travel with the result.

Run: python -m scripts.sci_estimate --job-seconds S --vcpus N --utilization U --min-watts A
     --max-watts B --pue P --grid G --embodied-g E --units R
Prints the result as JSON on stdout. Exit codes: 0 ok, 2 invalid value (message on stderr).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any

Number = int | float

ARGUMENTS = (
    "job_seconds",
    "vcpus",
    "utilization",
    "min_watts",
    "max_watts",
    "pue",
    "grid_g_per_kwh",
    "embodied_g",
    "functional_units",
)


def validate(inputs: dict[str, Number]) -> None:
    """Raise ValueError naming the first invalid argument; NaN and infinity are invalid."""
    for name, value in inputs.items():
        if not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number, got {value}")
    rules = (
        ("job_seconds", inputs["job_seconds"] >= 0, "must be >= 0"),
        ("vcpus", inputs["vcpus"] >= 1, "must be >= 1"),
        ("utilization", 0 <= inputs["utilization"] <= 1, "must be within [0, 1]"),
        ("min_watts", inputs["min_watts"] >= 0, "must be >= 0"),
        ("max_watts", inputs["max_watts"] >= inputs["min_watts"], "must be >= min_watts"),
        ("pue", inputs["pue"] >= 1, "must be >= 1"),
        ("grid_g_per_kwh", inputs["grid_g_per_kwh"] >= 0, "must be >= 0"),
        ("embodied_g", inputs["embodied_g"] >= 0, "must be >= 0"),
        ("functional_units", inputs["functional_units"] >= 1, "must be >= 1"),
    )
    for name, ok, message in rules:
        if not ok:
            raise ValueError(f"{name} {message}, got {inputs[name]}")


def estimate(
    job_seconds: Number,
    vcpus: Number,
    utilization: Number,
    min_watts: Number,
    max_watts: Number,
    pue: Number,
    grid_g_per_kwh: Number,
    embodied_g: Number,
    functional_units: Number,
) -> dict[str, Any]:
    """Return the SCI terms of a CI run, unrounded, with the nine inputs under "inputs".

    Raises ValueError, naming the argument, when one is out of range. Writes no file.
    """
    inputs = {
        "job_seconds": job_seconds,
        "vcpus": vcpus,
        "utilization": utilization,
        "min_watts": min_watts,
        "max_watts": max_watts,
        "pue": pue,
        "grid_g_per_kwh": grid_g_per_kwh,
        "embodied_g": embodied_g,
        "functional_units": functional_units,
    }
    validate(inputs)
    avg_watts = min_watts + utilization * (max_watts - min_watts)
    energy_kwh = (job_seconds / 3600) * vcpus * avg_watts / 1000 * pue
    operational_g = energy_kwh * grid_g_per_kwh
    return {
        "avg_watts": avg_watts,
        "energy_kwh": energy_kwh,
        "operational_g": operational_g,
        "embodied_g": embodied_g,
        "sci_g_per_unit": (operational_g + embodied_g) / functional_units,
        "inputs": inputs,
    }


def number(text: str) -> Number:
    """Parse an int when the text is one, else a float; argparse reports a failure as usage."""
    try:
        return int(text)
    except ValueError:
        return float(text)


def main(argv: list[str] | None = None) -> int:
    """Print the SCI estimate as JSON on stdout; an invalid value goes to stderr, exit 2."""
    parser = argparse.ArgumentParser(description="Software Carbon Intensity of a CI run.")
    options = (
        ("--job-seconds", "job_seconds"),
        ("--vcpus", "vcpus"),
        ("--utilization", "utilization"),
        ("--min-watts", "min_watts"),
        ("--max-watts", "max_watts"),
        ("--pue", "pue"),
        ("--grid", "grid_g_per_kwh"),
        ("--embodied-g", "embodied_g"),
        ("--units", "functional_units"),
    )
    for flag, dest in options:
        parser.add_argument(flag, dest=dest, type=number, required=True)
    args = parser.parse_args(argv)
    try:
        result = estimate(**{name: getattr(args, name) for name in ARGUMENTS})
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
