"""Gate on the scanners' reports: the GitLab SAST and secret-detection jobs only fail when the
scanner itself breaks, not when it finds something, so this reads the reports and decides.

Any secret finding blocks (a leaked secret has no tolerable false positive). SAST findings of
the blocking severities (default Critical and High) block; lower ones are counted and printed
so they stay visible without blocking. A missing or malformed report fails loudly.

Run in CI: python -m scripts.security_gate --sast gl-sast-report.json \
    --secrets gl-secret-detection-report.json [--summary-json summary.json]
The optional summary file holds the number of secret findings and of SAST findings per
severity; it is written also when the gate blocks, and never changes the decision.
Exit codes: 0 ok, 1 blocking findings, 2 report missing or malformed.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def severities(path: Path) -> Counter[str]:
    """Count the findings of a GitLab security report by severity."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return Counter(str(v.get("severity", "Unknown")) for v in data["vulnerabilities"])


def write_summary(path: Path, sast: Counter[str], secrets: Counter[str]) -> None:
    """Write the secret count and the SAST count per severity as JSON to ``path``."""
    summary = {"secrets": sum(secrets.values()), "sast": dict(sorted(sast.items()))}
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Block on any secret finding and on SAST findings of the blocking severities."""
    parser = argparse.ArgumentParser(description="Gate on the security scanners' reports.")
    parser.add_argument("--sast", required=True, type=Path, help="gl-sast-report.json")
    parser.add_argument("--secrets", required=True, type=Path, help="secret detection report")
    parser.add_argument("--block", nargs="*", default=["Critical", "High"], help="SAST severities")
    parser.add_argument("--summary-json", type=Path, help="write the finding counts as JSON")
    args = parser.parse_args(argv)
    try:
        sast, secrets = severities(args.sast), severities(args.secrets)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        sys.stderr.write(f"ERROR: cannot read a security report ({exc!r})\n")
        return 2
    if args.summary_json is not None:
        try:
            write_summary(args.summary_json, sast, secrets)
        except OSError as exc:
            sys.stderr.write(f"ERROR: cannot write the summary ({exc!r})\n")
            return 2
    blocking_sast = sum(count for sev, count in sast.items() if sev in args.block)
    other_sast = sum(sast.values()) - blocking_sast
    sys.stdout.write(
        f"{sum(secrets.values())} secret finding(s); SAST: {blocking_sast} blocking "
        f"({'/'.join(args.block)}), {other_sast} non-blocking {dict(sorted(sast.items()))}\n"
    )
    if secrets:
        sys.stderr.write("PROBLEM: secret detection found a possible secret\n")
    if blocking_sast:
        sys.stderr.write(f"PROBLEM: SAST found {blocking_sast} finding(s) of a blocking severity\n")
    return 1 if secrets or blocking_sast else 0


if __name__ == "__main__":
    raise SystemExit(main())
