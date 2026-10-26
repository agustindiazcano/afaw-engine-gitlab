"""telemetry_report: one block per self-healing issue, from recorded GitLab API payloads."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from scripts.telemetry_report import (
    NOT_AVAILABLE,
    build_block,
    collect_blocks,
    find_repair_mr,
    main,
    render,
)

ISSUE_TEXT = (
    "A pipeline failed on branch `feat/broken` at commit 0123abcd. Repair it: fix the cause on a "
    "new branch and open a merge request into the default branch.\n\n"
    "Failed jobs:\n- `lint` (stage verify)\n- `unit_tests` (stage verify)\n\n"
    "End of the log of `lint`:\n```text\nF401 unused import\n```\n\n<!-- afaw-autoheal:ref -->"
)
DESCRIPTION = "The import in scripts/x.py was unused.\n\n- removed it\n\nCloses #56"


def make_issue(**extra: Any) -> dict[str, Any]:
    return {
        "iid": 56,
        "title": "Autoheal: lint failed on feat/broken",
        "web_url": "https://gitlab.example/p/-/issues/56",
        "created_at": "2026-10-25T10:00:00.000Z",
        "description": ISSUE_TEXT,
        **extra,
    }


def make_mr(**extra: Any) -> dict[str, Any]:
    return {
        "iid": 60,
        "web_url": "https://gitlab.example/p/-/merge_requests/60",
        "state": "merged",
        "description": DESCRIPTION,
        "created_at": "2026-10-25T10:20:00.000Z",
        "merged_at": "2026-10-25T11:02:30.000Z",
        "merge_commit_sha": "feedface" * 5,
        **extra,
    }


CHANGES = [
    {"old_path": "scripts/x.py", "new_path": "scripts/x.py"},
    {"old_path": "tests/test_x.py", "new_path": "tests/test_x.py"},
]
PIPELINE = {"id": 900, "status": "success", "web_url": "https://gitlab.example/p/-/pipelines/900"}


def field(block: str, name: str) -> str:
    """The text after ``**name:**`` up to the end of that line."""
    match = re.search(rf"^\*\*{re.escape(name)}:\*\*[ ]?(.*)$", block, re.MULTILINE)
    assert match, f"no field {name!r} in:\n{block}"
    return match.group(1)


# ------------------------------------------------------------------ one issue with a merged repair


def test_a_merged_repair_fills_every_field_from_its_source():
    block = build_block(make_issue(), make_mr(), CHANGES, PIPELINE)
    assert "#56" in block and "Autoheal: lint failed on feat/broken" in block
    assert field(block, "Timestamp") == "2026-10-25T10:00:00.000Z"
    assert field(block, "Branch") == "`feat/broken`"
    assert field(block, "Trigger") == "`lint`, `unit_tests`"
    assert field(block, "Remediation") == "2 files: `scripts/x.py`, `tests/test_x.py`"
    assert field(block, "Merged at") == "2026-10-25T11:02:30.000Z"
    assert field(block, "Pipeline of the merge commit") == "success"
    assert NOT_AVAILABLE not in block


def test_minutes_are_computed_from_the_issue_and_the_merge_timestamps():
    block = build_block(make_issue(), make_mr(), CHANGES, PIPELINE)
    assert field(block, "Minutes from issue to merge") == "62.5"
    later = make_mr(merged_at="2026-10-26T10:00:00.000Z")
    assert (
        field(build_block(make_issue(), later, CHANGES, PIPELINE), "Minutes from issue to merge")
        == "1440.0"
    )


def test_the_description_is_quoted_verbatim_and_not_summarised():
    block = build_block(make_issue(), make_mr(), CHANGES, PIPELINE)
    assert DESCRIPTION in block
    assert block.index("Root cause") < block.index(DESCRIPTION) < block.index("Remediation")


def test_backticks_in_the_description_cannot_close_the_quote():
    text = "Fix:\n```python\nx = 1\n```\nand `inline`"
    block = build_block(make_issue(), make_mr(description=text), CHANGES, PIPELINE)
    assert text in block
    fences = re.findall(r"^(`{3,})text$", block, re.MULTILINE)
    assert len(fences) == 1 and len(fences[0]) >= 4
    assert block.count(fences[0]) == 2  # opened once, closed once


def test_backticks_in_a_name_are_escaped_in_inline_code():
    changes = [{"old_path": "a`b.py", "new_path": "a`b.py"}]
    block = build_block(make_issue(), make_mr(), changes, PIPELINE)
    assert field(block, "Remediation") == "1 file: ``a`b.py``"


# ------------------------------------------------------------------ an issue with no repair


def test_an_issue_with_no_repair_says_not_available_for_every_repair_field():
    block = build_block(make_issue(), None, None, None)
    for name in (
        "Root cause",
        "Remediation",
        "Merged at",
        "Minutes from issue to merge",
        "Pipeline of the merge commit",
    ):
        assert field(block, name) == NOT_AVAILABLE
    assert field(block, "Branch") == "`feat/broken`"
    assert field(block, "Trigger") == "`lint`, `unit_tests`"


def test_an_issue_that_names_no_branch_or_jobs_says_not_available():
    block = build_block(make_issue(description="Something else."), None, None, None)
    assert field(block, "Branch") == NOT_AVAILABLE
    assert field(block, "Trigger") == NOT_AVAILABLE


def test_a_repair_that_is_not_merged_has_no_merge_fields():
    block = build_block(make_issue(), make_mr(state="opened", merged_at=None), CHANGES, None)
    assert field(block, "Merged at") == NOT_AVAILABLE
    assert field(block, "Minutes from issue to merge") == NOT_AVAILABLE
    assert field(block, "Pipeline of the merge commit") == NOT_AVAILABLE
    assert DESCRIPTION in block


def test_an_empty_description_is_not_quoted():
    block = build_block(make_issue(), make_mr(description=""), CHANGES, PIPELINE)
    assert field(block, "Root cause") == NOT_AVAILABLE


# ------------------------------------------------------------------ which merge request repaired


def test_the_repair_is_the_merge_request_whose_description_closes_the_issue():
    other = make_mr(iid=61, description="Closes #5")
    longer = make_mr(iid=62, description="Closes #560")
    assert find_repair_mr(56, [other, longer, make_mr()])["iid"] == 60
    assert find_repair_mr(56, [other, longer]) is None


def test_the_repair_may_list_the_issue_in_closes_issues():
    by_list = make_mr(iid=63, description="no keyword", closes_issues=[{"iid": 56}])
    assert find_repair_mr(56, [by_list])["iid"] == 63


def test_a_merged_repair_is_preferred_to_an_open_one():
    opened = make_mr(iid=70, state="opened", merged_at=None)
    assert find_repair_mr(56, [opened, make_mr()])["iid"] == 60


# ------------------------------------------------------------------ the file


def test_render_joins_blocks_under_a_title_and_is_deterministic():
    blocks = [
        build_block(make_issue(), None, None, None),
        build_block(make_issue(iid=57), None, None, None),
    ]
    text = render(blocks)
    assert text.startswith("# AFAW telemetry")
    assert text.index("#56") < text.index("#57")
    assert text == render(blocks) and text.endswith("\n")


def test_render_of_no_blocks_says_there_is_no_event():
    assert "No self-healing event" in render([])


def fake_get(url: str) -> Any:
    routes: dict[str, Any] = {
        "/issues?": [make_issue()],
        "/issues/56/closed_by": [make_mr(description="no keyword")],
        "/issues/56/related_merge_requests": [make_mr(iid=61, description="mentions #56")],
        "/merge_requests/60/diffs": CHANGES,
        "/pipelines?": [PIPELINE],
    }
    for part, payload in routes.items():
        if part in url:
            return payload
    raise AssertionError(f"unexpected url {url}")


def test_collect_blocks_asks_for_the_label_and_the_merge_commit():
    urls: list[str] = []

    def spy(url: str) -> Any:
        urls.append(url)
        return fake_get(url)

    collect_blocks(spy, "https://gitlab.example/api/v4", "123")
    assert any("labels=afaw-autoheal" in u and "state=all" in u for u in urls)
    assert any("/pipelines?" in u and "sha=" + "feedface" * 5 in u for u in urls)


def test_collect_blocks_reads_the_api_and_builds_one_block_per_issue():
    blocks = collect_blocks(fake_get, "https://gitlab.example/api/v4", "123")
    assert len(blocks) == 1
    assert field(blocks[0], "Pipeline of the merge commit") == "success"
    assert field(blocks[0], "Remediation").startswith("2 files")


def test_the_cli_writes_the_file(tmp_path: Path):
    out = tmp_path / "build" / "AFAW_TELEMETRY.md"
    code = main(["--project", "123", "--out", str(out)], get_json=fake_get)
    assert code == 0
    assert out.read_text(encoding="utf-8").startswith("# AFAW telemetry")
