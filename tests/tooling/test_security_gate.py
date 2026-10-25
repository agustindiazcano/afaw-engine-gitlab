"""Tests for scripts.security_gate: the scanners' reports decide, not the scanner jobs' status."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import security_gate


def _report(path: Path, severities: list[str]) -> str:
    vulns = [{"id": f"v{i}", "severity": s} for i, s in enumerate(severities)]
    path.write_text(json.dumps({"vulnerabilities": vulns}), encoding="utf-8")
    return str(path)


def _run(tmp_path: Path, sast: list[str], secrets: list[str]) -> int:
    args = ["--sast", _report(tmp_path / "sast.json", sast)]
    args += ["--secrets", _report(tmp_path / "secrets.json", secrets)]
    return security_gate.main(args)


def test_clean_reports_pass_and_say_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(tmp_path, [], []) == 0
    assert "0 secret finding(s)" in capsys.readouterr().out


def test_any_secret_finding_blocks(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(tmp_path, [], ["Low"]) == 1
    assert "PROBLEM" in capsys.readouterr().err


@pytest.mark.parametrize("severity", ["Critical", "High"])
def test_high_and_critical_sast_findings_block(tmp_path: Path, severity: str) -> None:
    assert _run(tmp_path, [severity], []) == 1


def test_lower_sast_findings_are_reported_but_do_not_block(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(tmp_path, ["Medium", "Low", "Info"], []) == 0
    assert "3 non-blocking" in capsys.readouterr().out


def test_missing_report_fails_loudly(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = security_gate.main(
        ["--sast", str(tmp_path / "nope.json"), "--secrets", _report(tmp_path / "s.json", [])]
    )
    assert code == 2 and "ERROR" in capsys.readouterr().err


def test_report_without_the_vulnerabilities_list_fails_loudly(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    ok = _report(tmp_path / "s.json", [])
    assert security_gate.main(["--sast", str(bad), "--secrets", ok]) == 2


def _summary(tmp_path: Path, sast: list[str], secrets: list[str]) -> tuple[int, dict[str, object]]:
    out = tmp_path / "summary.json"
    args = ["--sast", _report(tmp_path / "sast.json", sast)]
    args += ["--secrets", _report(tmp_path / "secrets.json", secrets)]
    code = security_gate.main([*args, "--summary-json", str(out)])
    return code, json.loads(out.read_text(encoding="utf-8"))


def test_summary_json_counts_secrets_and_sast_per_severity(tmp_path: Path) -> None:
    code, summary = _summary(tmp_path, ["Medium", "Low", "Medium"], [])
    assert code == 0
    assert summary == {"secrets": 0, "sast": {"Low": 1, "Medium": 2}}


def test_summary_json_is_written_when_the_gate_blocks(tmp_path: Path) -> None:
    code, summary = _summary(tmp_path, ["High", "Low"], ["Critical", "Low"])
    assert code == 1
    assert summary == {"secrets": 2, "sast": {"High": 1, "Low": 1}}


def test_summary_json_of_clean_reports_has_an_empty_sast_object(tmp_path: Path) -> None:
    assert _summary(tmp_path, [], []) == (0, {"secrets": 0, "sast": {}})


def test_summary_json_does_not_change_the_exit_code(tmp_path: Path) -> None:
    plain = _run(tmp_path, ["Critical"], [])
    assert plain == _summary(tmp_path, ["Critical"], [])[0]


@pytest.mark.characterization(
    reason="the old code never writes a summary; the test pins that it stays opt-in"
)
def test_no_summary_file_is_written_without_the_argument(tmp_path: Path) -> None:
    _run(tmp_path, ["Low"], [])
    assert not (tmp_path / "summary.json").exists()


def test_summary_json_is_not_written_when_a_report_is_unreadable(tmp_path: Path) -> None:
    out = tmp_path / "summary.json"
    code = security_gate.main(
        [
            "--sast",
            str(tmp_path / "nope.json"),
            "--secrets",
            _report(tmp_path / "s.json", []),
            "--summary-json",
            str(out),
        ]
    )
    assert code == 2 and not out.exists()
