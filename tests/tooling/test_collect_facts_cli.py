"""The collect_facts command chooses the forge by environment and fails loudly otherwise."""

import pytest

from scripts import collect_facts


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CI_API_V4_URL", "CI_PROJECT_ID", "GITHUB_REPOSITORY", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)


def test_fails_loudly_without_any_forge(capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    assert collect_facts.main(["--out", str(tmp_path / "facts.json")]) == 1
    err = capsys.readouterr().err
    assert "CI_API_V4_URL" in err and "GITHUB_REPOSITORY" in err
    assert not (tmp_path / "facts.json").exists()


def test_fails_loudly_when_both_forges_are_set(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path
) -> None:
    monkeypatch.setenv("CI_API_V4_URL", "https://gitlab.com/api/v4")
    monkeypatch.setenv("CI_PROJECT_ID", "7")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    assert collect_facts.main(["--out", str(tmp_path / "facts.json")]) == 1
    assert "both" in capsys.readouterr().err
