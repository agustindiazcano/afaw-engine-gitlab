"""Tests for the deterministic keyword search: exact records, titles, order and excerpts."""

from __future__ import annotations

from pathlib import Path

import pytest

from afaw_web.search import MAX_EXCERPTS, Hit, records, search


def _write(data_dir: Path, relative: str, text: str) -> None:
    path = data_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_records_lists_adrs_then_gotchas_sorted_then_the_last_context(tmp_path: Path) -> None:
    _write(tmp_path, "docs/adr/0002-b.md", "# b\n")
    _write(tmp_path, "docs/adr/0001-a.md", "# a\n")
    _write(tmp_path, "docs/gotchas/0001-g.md", "# g\n")
    _write(tmp_path, "live/context/global/LASTCONTEXT.md", "# last\n")
    _write(tmp_path, "docs/adr/notes.txt", "not markdown")
    assert [p.relative_to(tmp_path).as_posix() for p in records(tmp_path)] == [
        "docs/adr/0001-a.md",
        "docs/adr/0002-b.md",
        "docs/gotchas/0001-g.md",
        "live/context/global/LASTCONTEXT.md",
    ]


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_records_omits_the_last_context_when_it_does_not_exist(tmp_path: Path) -> None:
    _write(tmp_path, "docs/adr/0001-a.md", "# a\n")
    assert [p.name for p in records(tmp_path)] == ["0001-a.md"]


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_records_ignores_a_last_context_that_is_a_directory(tmp_path: Path) -> None:
    (tmp_path / "live" / "context" / "global" / "LASTCONTEXT.md").mkdir(parents=True)
    assert records(tmp_path) == []


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_records_of_an_empty_directory_is_empty(tmp_path: Path) -> None:
    assert records(tmp_path) == []


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_search_returns_the_whole_hit_with_title_excerpts_and_score(tmp_path: Path) -> None:
    _write(tmp_path, "docs/adr/0001-a.md", "# The Title\nmutation gate\nother\nmutation again\n")
    assert search(tmp_path, "mutation") == [
        Hit("docs/adr/0001-a.md", "The Title", ["mutation gate", "mutation again"], 2)
    ]


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_the_title_is_the_first_level_one_heading_without_the_marker(tmp_path: Path) -> None:
    _write(tmp_path, "docs/adr/0001-a.md", "## Not a title\n#nospace\n#  First  \n# Second\nword\n")
    assert search(tmp_path, "word")[0].title == "First"


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_a_record_without_a_heading_is_titled_by_its_relative_path(tmp_path: Path) -> None:
    _write(tmp_path, "docs/gotchas/0001-g.md", "## Symptom\nbroken thing\n")
    hit = search(tmp_path, "broken")[0]
    assert hit.title == "docs/gotchas/0001-g.md" == hit.path


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_search_reads_the_records_as_utf8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, "docs/adr/0001-a.md", "# Título\ncobertura média\n")
    encodings: list[str | None] = []
    original = Path.read_text

    def spy(self: Path, encoding: str | None = None, errors: str | None = None) -> str:
        encodings.append(encoding)
        return original(self, encoding="utf-8", errors=errors)

    monkeypatch.setattr(Path, "read_text", spy)
    hit = search(tmp_path, "cobertura")[0]
    assert hit.title == "Título" and hit.excerpts == ["cobertura média"]
    assert encodings == ["utf-8"]


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_search_is_case_insensitive_in_both_the_question_and_the_file(tmp_path: Path) -> None:
    _write(tmp_path, "docs/adr/0001-a.md", "# T\nThe MUTATION Gate\n")
    assert search(tmp_path, "mUtAtIoN")[0].excerpts == ["The MUTATION Gate"]


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_excerpts_are_stripped_blank_free_and_capped(tmp_path: Path) -> None:
    lines = ["# T", "   word one  ", "   ", "word two", "word three", "word four", "word five"]
    _write(tmp_path, "docs/adr/0001-a.md", "\n".join(lines) + "\n")
    hit = search(tmp_path, "word")[0]
    assert MAX_EXCERPTS == 3
    assert hit.excerpts == ["word one", "word two", "word three"]
    assert hit.score == 5


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_the_score_counts_every_occurrence_of_every_term_on_matching_lines(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "docs/adr/0001-a.md", "# T\nalpha alpha beta\ngamma\nbeta\n")
    assert search(tmp_path, "alpha beta")[0].score == 4


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_a_repeated_word_in_the_question_is_counted_once(tmp_path: Path) -> None:
    _write(tmp_path, "docs/adr/0001-a.md", "# T\nalpha\n")
    assert search(tmp_path, "alpha alpha ALPHA")[0].score == 1


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_words_shorter_than_two_characters_are_ignored(tmp_path: Path) -> None:
    _write(tmp_path, "docs/adr/0001-a.md", "# T\na b c\nok\n")
    assert search(tmp_path, "a b c") == []
    assert search(tmp_path, "a ok")[0].excerpts == ["ok"]


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_underscores_and_digits_are_part_of_a_word(tmp_path: Path) -> None:
    _write(tmp_path, "docs/adr/0001-a.md", "# T\nfiles_touched is task_049\n")
    assert search(tmp_path, "files_touched, task_049!")[0].score == 2


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_a_question_without_words_matches_nothing(tmp_path: Path) -> None:
    _write(tmp_path, "docs/adr/0001-a.md", "# T\nanything\n")
    assert search(tmp_path, "?! - .") == []


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_a_record_with_no_matching_line_is_not_a_hit(tmp_path: Path) -> None:
    _write(tmp_path, "docs/adr/0001-a.md", "# Title only\nnothing here\n")
    assert search(tmp_path, "kubernetes") == []


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_hits_are_ordered_by_score_descending_then_by_path(tmp_path: Path) -> None:
    _write(tmp_path, "docs/adr/0001-low.md", "# low\nword\n")
    _write(tmp_path, "docs/adr/0002-high.md", "# high\nword word word\n")
    _write(tmp_path, "docs/gotchas/0001-tie.md", "# tie\nword\n")
    _write(tmp_path, "live/context/global/LASTCONTEXT.md", "# last\nword word\n")
    ordered = [(h.path, h.score) for h in search(tmp_path, "word")]
    assert ordered == [
        ("docs/adr/0002-high.md", 3),
        ("live/context/global/LASTCONTEXT.md", 2),
        ("docs/adr/0001-low.md", 1),
        ("docs/gotchas/0001-tie.md", 1),
    ]


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_search_is_deterministic(tmp_path: Path) -> None:
    _write(tmp_path, "docs/adr/0001-a.md", "# a\nword\n")
    _write(tmp_path, "docs/adr/0002-b.md", "# b\nword\n")
    assert search(tmp_path, "word") == search(tmp_path, "word")


@pytest.mark.characterization(
    reason="the search already behaved this way; the test pins it so a change is noticed"
)
def test_search_over_an_empty_directory_finds_nothing(tmp_path: Path) -> None:
    assert search(tmp_path, "anything") == []
