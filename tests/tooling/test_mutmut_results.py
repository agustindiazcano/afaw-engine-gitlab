"""mutmut_results: turn mutmut's .meta files into the results shape of the mutation gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import mutation_gate, mutmut_results

# The structure mutmut 3.8.0 wrote on the CI runner on 2026-10-25 (first mutants of app.py).
RECORDED_APP_META: dict[str, Any] = {
    "exit_code_by_key": {
        "afaw_web.app.x__missing__mutmut_1": 1,
        "afaw_web.app.x__missing__mutmut_2": 1,
        "afaw_web.app.x_create_app__mutmut_4": 1,
        "afaw_web.app.x_create_app__mutmut_5": 0,
        "afaw_web.app.x_create_app__mutmut_6": 0,
    },
    "hash_by_function_name": {},
    "type_check_error_by_key": {},
    "durations_by_key": {},
    "estimated_durations_by_key": {},
}
EMPTY_META: dict[str, Any] = {**RECORDED_APP_META, "exit_code_by_key": {}}


def write_meta(root: Path, rel: str, data: dict[str, Any]) -> None:
    path = root / "mutants" / f"{rel}.meta"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_exit_code_1_is_killed_and_0_is_survived(tmp_path: Path) -> None:
    write_meta(tmp_path, "src/afaw_web/app.py", RECORDED_APP_META)
    result = mutmut_results.convert(tmp_path / "mutants")
    mutants = result["files"]["src/afaw_web/app.py"]["mutants"]
    assert {m["id"]: m["status"] for m in mutants} == {
        "afaw_web.app.x__missing__mutmut_1": "killed",
        "afaw_web.app.x__missing__mutmut_2": "killed",
        "afaw_web.app.x_create_app__mutmut_4": "killed",
        "afaw_web.app.x_create_app__mutmut_5": "survived",
        "afaw_web.app.x_create_app__mutmut_6": "survived",
    }


def test_the_path_is_the_source_path_without_the_mutants_prefix_and_the_meta_suffix(
    tmp_path: Path,
) -> None:
    write_meta(tmp_path, "src/back/domain/fees.py", RECORDED_APP_META)
    assert list(mutmut_results.convert(tmp_path / "mutants")["files"]) == [
        "src/back/domain/fees.py"
    ]


def test_a_file_with_no_mutants_is_left_out(tmp_path: Path) -> None:
    write_meta(tmp_path, "src/afaw_web/main.py", EMPTY_META)
    write_meta(tmp_path, "src/afaw_web/app.py", RECORDED_APP_META)
    assert list(mutmut_results.convert(tmp_path / "mutants")["files"]) == ["src/afaw_web/app.py"]


@pytest.mark.parametrize("code", [None, 2, 33, 36, -11])
def test_any_other_exit_code_fails_loudly(tmp_path: Path, code: int | None) -> None:
    meta = {**RECORDED_APP_META, "exit_code_by_key": {"afaw_web.app.x_f__mutmut_1": code}}
    write_meta(tmp_path, "src/afaw_web/app.py", meta)
    with pytest.raises(mutmut_results.MutmutError, match="mutmut_1"):
        mutmut_results.convert(tmp_path / "mutants")


def test_no_meta_files_is_an_error_not_an_empty_pass(tmp_path: Path) -> None:
    (tmp_path / "mutants").mkdir()
    with pytest.raises(mutmut_results.MutmutError, match="no .meta"):
        mutmut_results.convert(tmp_path / "mutants")
    with pytest.raises(mutmut_results.MutmutError, match="does not exist"):
        mutmut_results.convert(tmp_path / "missing")


def test_a_meta_file_that_is_not_mutmuts_shape_fails_loudly(tmp_path: Path) -> None:
    write_meta(tmp_path, "src/afaw_web/app.py", {"something": "else"})
    with pytest.raises(mutmut_results.MutmutError, match="exit_code_by_key"):
        mutmut_results.convert(tmp_path / "mutants")


def test_the_gate_scores_the_converted_results(tmp_path: Path) -> None:
    write_meta(tmp_path, "src/afaw_web/app.py", RECORDED_APP_META)
    mutants = mutmut_results.convert(tmp_path / "mutants")["files"]["src/afaw_web/app.py"][
        "mutants"
    ]
    report = mutation_gate.score(mutants, accepted=set())
    assert report == {"generated": 5, "killed": 3, "equivalent": 0, "raw": 60.0, "gated": 60.0}


def test_the_command_writes_the_json_the_gate_reads(tmp_path: Path) -> None:
    write_meta(tmp_path, "src/afaw_web/app.py", RECORDED_APP_META)
    out = tmp_path / "build" / "mutation.json"
    code = mutmut_results.main(["--mutants", str(tmp_path / "mutants"), "--out", str(out)])
    assert code == 0
    assert list(json.loads(out.read_text(encoding="utf-8"))["files"]) == ["src/afaw_web/app.py"]


def test_the_command_exits_2_and_writes_nothing_when_it_cannot_convert(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "mutation.json"
    assert mutmut_results.main(["--mutants", str(tmp_path / "nope"), "--out", str(out)]) == 2
    assert not out.exists() and "ERROR" in capsys.readouterr().err
