"""Tests for scripts.release_notes: Markdown release notes from merged merge requests."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

from scripts import release_notes


def _mr(iid: int, title: str, author: str = "ana") -> dict[str, Any]:
    return {"iid": iid, "title": title, "author": {"username": author}}


def test_empty_list_has_heading_and_zero_count() -> None:
    assert release_notes.render([], "v1.0.0") == "## v1.0.0\n\n0 merge requests\n"


def test_one_merge_request_uses_the_singular_count() -> None:
    text = release_notes.render([_mr(7, "Add login", "bo")], "v1.0.1")
    assert text == "## v1.0.1\n\n- !7 Add login (bo)\n\n1 merge request\n"


def test_bullets_are_sorted_by_iid_not_by_input_order() -> None:
    text = release_notes.render([_mr(12, "c"), _mr(3, "a"), _mr(9, "b")], "v2")
    bullets = [line for line in text.splitlines() if line.startswith("- ")]
    assert bullets == ["- !3 a (ana)", "- !9 b (ana)", "- !12 c (ana)"]
    assert text.splitlines()[-1] == "3 merge requests"


def test_title_with_markdown_characters_is_kept_verbatim() -> None:
    title = "Fix `parse()` for *nested* [links](http://x) and _under_scores_ #1"
    text = release_notes.render([_mr(5, title)], "v3")
    assert f"- !5 {title} (ana)" in text.splitlines()


def test_render_does_not_modify_its_input() -> None:
    mrs = [_mr(2, "b"), _mr(1, "a")]
    release_notes.render(mrs, "v1")
    assert [mr["iid"] for mr in mrs] == [2, 1]


def test_cli_prints_the_notes_of_a_json_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "mrs.json"
    path.write_text(json.dumps([_mr(2, "Two"), _mr(1, "One")]), encoding="utf-8")
    code = release_notes.main(["--merge-requests", str(path), "--tag", "v9"])
    assert code == 0
    assert capsys.readouterr().out == release_notes.render([_mr(1, "One"), _mr(2, "Two")], "v9")


def test_cli_reports_a_missing_file_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = release_notes.main(["--merge-requests", str(tmp_path / "none.json"), "--tag", "v1"])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "ERROR" in captured.err


def test_cli_tag_defaults_to_unreleased(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "mrs.json"
    path.write_text("[]", encoding="utf-8")
    assert release_notes.main(["--merge-requests", str(path)]) == 0
    assert capsys.readouterr().out == "## unreleased\n\n0 merge requests\n"
