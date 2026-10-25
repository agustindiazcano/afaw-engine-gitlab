"""demo on / demo off: start and stop the hands-off demonstration."""

from __future__ import annotations

from typing import Any

import pytest

from scripts import demo
from scripts.afaw_state.facts import FactsError


class FakeApi:
    def __init__(
        self, variables=("AFAW_BOT_USER_IDS", "AFAW_MERGE_TOKEN", "AFAW_AUTO_MERGE"), issues=None
    ):
        self.variables = set(variables)
        self.issues = issues or []
        self.set_calls: list[tuple[str, str]] = []
        self.created: list[dict[str, Any]] = []
        self.closed: list[int] = []
        self.notes: list[tuple[int, str]] = []

    def variable_keys(self):
        return set(self.variables)

    def set_variable(self, key, value):
        self.set_calls.append((key, value))

    def user_id(self, username):
        assert username == demo.FLOW_USERNAME
        return 33073386

    def create_issue(self, title, description, assignee_id, labels):
        self.created.append(
            {"title": title, "description": description, "assignee": assignee_id, "labels": labels}
        )
        return {"iid": 99, "web_url": "https://gitlab.com/x/-/work_items/99"}

    def open_issues_with_label(self, label):
        return [i for i in self.issues if label in i["labels"]]

    def close_issue(self, iid, note):
        self.closed.append(iid)
        self.notes.append((iid, note))


def test_demo_on_turns_the_switch_on_and_opens_one_issue_for_the_flow(capsys):
    api = FakeApi()
    assert demo.on(api, issues=1, stamp="20261025-1500") == 0
    assert api.set_calls == [("AFAW_AUTO_MERGE", "true")]
    assert len(api.created) == 1
    issue = api.created[0]
    assert issue["assignee"] == 33073386 and "demo" in issue["labels"]
    assert "docs/submission/demo-run-20261025-1500-1.md" in issue["description"]
    assert "https://gitlab.com/x/-/work_items/99" in capsys.readouterr().out


def test_demo_on_can_open_several_issues_with_distinct_files():
    api = FakeApi()
    demo.on(api, issues=3, stamp="s")
    files = [i["description"].split("docs/submission/")[1].split(".md")[0] for i in api.created]
    assert files == ["demo-run-s-1", "demo-run-s-2", "demo-run-s-3"]


@pytest.mark.parametrize("missing", ["AFAW_BOT_USER_IDS", "AFAW_MERGE_TOKEN"])
def test_demo_on_refuses_to_start_when_a_required_variable_is_missing(missing, capsys):
    keys = {"AFAW_BOT_USER_IDS", "AFAW_MERGE_TOKEN", "AFAW_AUTO_MERGE"} - {missing}
    api = FakeApi(variables=keys)
    assert demo.on(api, issues=1, stamp="s") == 2
    assert api.set_calls == [] and api.created == []
    assert missing in capsys.readouterr().err


def test_demo_on_does_not_need_the_switch_to_exist_yet():
    api = FakeApi(variables={"AFAW_BOT_USER_IDS", "AFAW_MERGE_TOKEN"})
    assert demo.on(api, issues=1, stamp="s") == 0
    assert api.set_calls == [("AFAW_AUTO_MERGE", "true")]


def test_demo_off_turns_the_switch_off_and_closes_the_demo_and_autoheal_issues(capsys):
    api = FakeApi(
        issues=[
            {"iid": 5, "labels": ["demo"]},
            {"iid": 6, "labels": ["afaw-autoheal"]},
            {"iid": 7, "labels": ["experiment"]},
        ]
    )
    assert demo.off(api) == 0
    assert api.set_calls == [("AFAW_AUTO_MERGE", "false")]
    assert sorted(api.closed) == [5, 6]
    assert "off" in capsys.readouterr().out


def test_demo_off_with_nothing_open_still_turns_the_switch_off():
    api = FakeApi()
    assert demo.off(api) == 0
    assert api.set_calls == [("AFAW_AUTO_MERGE", "false")]
    assert api.closed == []


def test_an_api_failure_fails_closed(capsys):
    class Broken(FakeApi):
        def variable_keys(self):
            raise FactsError("GitLab refused the request: HTTP 401")

    api = Broken()
    assert demo.on(api, issues=1, stamp="s") == 2
    assert api.created == []
    assert "401" in capsys.readouterr().err


def test_a_failure_while_switching_off_is_reported_not_hidden(capsys):
    class Broken(FakeApi):
        def set_variable(self, key, value):
            raise FactsError("GitLab refused the request: HTTP 403")

    assert demo.off(Broken()) == 2
    assert "403" in capsys.readouterr().err


def test_the_token_is_read_from_the_environment_and_never_printed(capsys):
    assert demo.main(["on"], env={}) == 2
    err = capsys.readouterr().err
    assert "GITLAB_TOKEN" in err


def test_the_api_sets_a_variable_with_an_update_and_falls_back_to_a_create():
    calls = []

    def send(method, url, headers, body):
        calls.append((method, url.rsplit("/", 1)[-1], body))
        if method == "PUT":
            raise FactsError("GitLab refused the request: HTTP 404")
        return {}

    api = demo.Api("https://gitlab.com/api/v4", "88", "tok", get_json=lambda u: [], send=send)
    api.set_variable("AFAW_AUTO_MERGE", "true")
    assert calls[0][0] == "PUT" and calls[0][1] == "AFAW_AUTO_MERGE"
    assert calls[1][0] == "POST"
    assert calls[1][2]["key"] == "AFAW_AUTO_MERGE" and calls[1][2]["value"] == "true"
    assert calls[1][2]["protected"] is False and calls[1][2]["masked"] is False
