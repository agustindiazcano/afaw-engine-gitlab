"""Stats of the merge requests made by agents: counted from the GitLab API, never declared."""

from __future__ import annotations

from typing import Any

from scripts.autonomy_stats import classify, render, summarize

BOT = "service_account_group_1_abc@noreply.gitlab.com"
HUMAN = "person@example.com"


def _mr(iid: int, state: str = "merged", created: str = "2026-10-25T10:00:00Z",
        merged: str | None = "2026-10-25T10:30:00Z") -> dict[str, Any]:
    return {"iid": iid, "state": state, "created_at": created, "merged_at": merged}


def _commits(*emails: str) -> list[dict[str, Any]]:
    return [{"author_email": e} for e in emails]


def _note(body: str, system: bool = True) -> dict[str, Any]:
    return {"body": body, "system": system}


def test_agent_only_needs_every_commit_from_a_service_account() -> None:
    assert classify(_mr(1), _commits(BOT, BOT), [])["agent_only"] is True
    assert classify(_mr(2), _commits(BOT, HUMAN), [])["agent_only"] is False


def test_a_merge_request_without_commits_is_not_agent_only() -> None:
    assert classify(_mr(3), [], [])["agent_only"] is False


def test_auto_merge_is_read_from_a_system_note_only() -> None:
    notes = [_note("enabled an automatic merge for abc123")]
    assert classify(_mr(4), _commits(BOT), notes)["auto_merged"] is True
    typed = [_note("enabled an automatic merge", system=False)]
    assert classify(_mr(5), _commits(BOT), typed)["auto_merged"] is False


def test_minutes_to_merge_is_the_gap_between_creation_and_merge() -> None:
    assert classify(_mr(6), _commits(BOT), [])["minutes_to_merge"] == 30.0
    assert classify(_mr(7, "opened", merged=None), _commits(BOT), [])["minutes_to_merge"] is None


def test_summarize_counts_each_group() -> None:
    rows = [
        classify(_mr(1), _commits(BOT), [_note("enabled an automatic merge")]),
        classify(_mr(2, merged="2026-10-25T11:00:00Z"), _commits(BOT), []),
        classify(_mr(3), _commits(HUMAN), []),
        classify(_mr(4, "closed", merged=None), _commits(BOT), []),
        classify(_mr(5, "opened", merged=None), _commits(HUMAN), []),
    ]
    s = summarize(rows)
    assert (s["total"], s["merged"], s["closed"], s["opened"]) == (5, 3, 1, 1)
    assert s["agent_only"] == 3 and s["agent_only_merged"] == 2
    assert s["auto_merged"] == 1
    assert s["median_minutes_agent_only_merged"] == 45.0


def test_summarize_of_nothing_reports_no_median() -> None:
    s = summarize([])
    assert s["total"] == 0 and s["median_minutes_agent_only_merged"] is None


def test_render_is_a_table_and_says_not_available_for_a_missing_median() -> None:
    text = render(summarize([]))
    assert text.startswith("| Measure | Value |")
    assert "not available" in text
