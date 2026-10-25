"""Tests for scripts.check_duo_config: only documented keys, tools and limits are accepted."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from scripts import check_duo_config as duo
from tests.tooling.conftest import REPO_ROOT

FLOW: dict[str, Any] = {
    "version": "v1",
    "environment": "ambient",
    "components": [
        {
            "name": "reporter",
            "type": "AgentComponent",
            "prompt_id": "reporter_prompt",
            "inputs": [
                {"from": "context:goal", "as": "goal"},
                {"from": "context:project_id", "as": "project_id"},
            ],
            "toolset": ["get_merge_request", "create_issue_note"],
        }
    ],
    "prompts": [
        {
            "prompt_id": "reporter_prompt",
            "name": "Reporter",
            "unit_primitives": [],
            "prompt_template": {
                "system": "Report the merge request state. Stop after posting the note.",
                "user": "Project: {{ project_id }}\nRequest: {{ goal }}",
                "placeholder": "history",
            },
        }
    ],
    "routers": [{"from": "reporter", "to": "end"}],
    "flow": {"entry_point": "reporter"},
}


def _flow(**changes: Any) -> dict[str, Any]:
    flow = copy.deepcopy(FLOW)
    flow.update(changes)
    return flow


def test_a_valid_flow_has_no_problems() -> None:
    assert duo.check_flow(FLOW) == []


@pytest.mark.parametrize("key", ["name", "description", "product_group", "surprise"])
def test_unsupported_top_level_keys_are_rejected(key: str) -> None:
    assert any(key in p for p in duo.check_flow(_flow(**{key: "x"})))


def test_environment_must_be_ambient() -> None:
    assert any("ambient" in p for p in duo.check_flow(_flow(environment="chat")))


def test_an_unknown_tool_is_rejected() -> None:
    flow = _flow()
    flow["components"][0]["toolset"] = ["made_up_tool"]
    assert any("made_up_tool" in p for p in duo.check_flow(flow))


@pytest.mark.parametrize("tool", ["create_commit", "create_merge_request", "update_merge_request"])
def test_the_flow_may_not_change_code_or_the_merge_request(tool: str) -> None:
    flow = _flow()
    flow["components"][0]["toolset"] = [tool]
    assert any(tool in p for p in duo.check_flow(flow))


def test_the_agent_must_receive_the_project_id() -> None:
    flow = _flow()
    flow["components"][0]["inputs"] = [{"from": "context:goal", "as": "goal"}]
    assert any("project_id" in p for p in duo.check_flow(flow))


def test_unit_primitives_must_be_declared_even_when_empty() -> None:
    flow = _flow()
    del flow["prompts"][0]["unit_primitives"]
    assert any("unit_primitives" in p for p in duo.check_flow(flow))


def test_the_model_cannot_be_set_in_a_prompt() -> None:
    flow = _flow()
    flow["prompts"][0]["model"] = "x"
    assert any("model" in p for p in duo.check_flow(flow))


def test_jinja_placeholders_are_not_allowed_in_the_system_prompt() -> None:
    flow = _flow()
    flow["prompts"][0]["prompt_template"]["system"] = "Use {{ goal }}. Stop when done."
    assert any("system" in p for p in duo.check_flow(flow))


def test_the_system_prompt_must_say_when_to_stop() -> None:
    flow = _flow()
    flow["prompts"][0]["prompt_template"]["system"] = "Report the state."
    assert any("stop" in p.lower() for p in duo.check_flow(flow))


def test_every_user_placeholder_needs_an_input() -> None:
    flow = _flow()
    flow["prompts"][0]["prompt_template"]["user"] = "{{ unknown_variable }}"
    assert any("unknown_variable" in p for p in duo.check_flow(flow))


def test_routers_and_the_entry_point_must_name_real_components() -> None:
    flow = _flow(routers=[{"from": "reporter", "to": "nowhere"}], flow={"entry_point": "ghost"})
    problems = duo.check_flow(flow)
    assert any("nowhere" in p for p in problems) and any("ghost" in p for p in problems)


def test_a_flow_over_40_kib_is_rejected() -> None:
    assert any("40 KiB" in p for p in duo.check_flow(FLOW, size=40 * 1024 + 1))


def test_agent_config_accepts_only_documented_keys() -> None:
    good = {"image": "python:3.12", "setup_script": ["pip install x"], "cache": {"paths": ["a"]}}
    assert duo.check_agent_config(good) == []
    assert any("variables" in p for p in duo.check_agent_config({"variables": {"A": "b"}}))
    assert any("image" in p for p in duo.check_agent_config({"image": ""}))


def test_review_instructions_need_a_name_and_instructions() -> None:
    assert (
        duo.check_review_instructions({"instructions": [{"name": "a", "instructions": "b"}]}) == []
    )
    assert duo.check_review_instructions({"instructions": [{"name": "a"}]})
    assert duo.check_review_instructions({"rules": []})


def test_subagent_needs_a_description_and_known_tools() -> None:
    ok = "---\nname: a\ndescription: Does a thing.\ntools: read_file, grep\n---\nPrompt body.\n"
    assert duo.check_subagent("a.md", ok) == []
    assert duo.check_subagent("a.md", "---\nname: a\n---\nBody.\n")
    bad_tool = "---\ndescription: d\ntools: read_file, nope\n---\nBody.\n"
    assert any("nope" in p for p in duo.check_subagent("a.md", bad_tool))
    assert duo.check_subagent("a.md", "No front matter")


def test_the_repository_configuration_is_valid(capsys: pytest.CaptureFixture[str]) -> None:
    assert duo.main(["--root", str(REPO_ROOT)]) == 0
    assert "OK" in capsys.readouterr().out


def test_a_missing_configuration_fails_loudly(
    tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    assert duo.main(["--root", str(tmp_path)]) == 1
    assert "PROBLEM" in capsys.readouterr().err


def spec(tools: list[str], optional: list[str] | None = None) -> str:
    """A custom agent spec the way duo/custom-agent.md writes it."""
    rows = "| Tools | " + ", ".join(f"`{t}`" for t in tools) + " |\n"
    if optional is not None:
        rows += "| Optional tools | " + ", ".join(f"`{t}`" for t in optional) + " |\n"
    return "# Custom agent\n\n| Field | Value |\n|---|---|\n" + rows + "\n## System prompt\n"


def test_the_agent_allow_lists_are_documented_and_never_forbidden() -> None:
    allowed = duo.AUDITOR_TOOLS | duo.AUDITOR_OPTIONAL_TOOLS | duo.PLANNER_TOOLS
    assert allowed <= duo.DOCUMENTED_TOOLS
    assert not allowed & duo.AGENT_FORBIDDEN_TOOLS
    assert not allowed & duo.IDE_ONLY_TOOLS


def test_the_auditor_may_use_its_read_tools_and_the_optional_note_tools() -> None:
    text = spec(sorted(duo.AUDITOR_TOOLS), sorted(duo.AUDITOR_OPTIONAL_TOOLS))
    assert (
        duo.check_agent_spec("auditor", text, duo.AUDITOR_TOOLS, duo.AUDITOR_OPTIONAL_TOOLS) == []
    )


def test_a_documented_tool_outside_the_allow_list_is_rejected() -> None:
    text = spec(["get_issue", "get_wiki_page"])
    problems = duo.check_agent_spec("auditor", text, duo.AUDITOR_TOOLS, duo.AUDITOR_OPTIONAL_TOOLS)
    assert any("get_wiki_page" in p and "allow list" in p for p in problems)


@pytest.mark.parametrize("tool", sorted(duo.AGENT_FORBIDDEN_TOOLS))
def test_a_forbidden_tool_is_rejected_by_name(tool: str) -> None:
    problems = duo.check_agent_spec(
        "auditor", spec(["get_issue", tool]), duo.AUDITOR_TOOLS, duo.AUDITOR_OPTIONAL_TOOLS
    )
    assert any(tool in p and "forbidden" in p for p in problems)


@pytest.mark.parametrize("tool", sorted(duo.IDE_ONLY_TOOLS))
def test_an_ide_only_tool_is_rejected_by_name(tool: str) -> None:
    problems = duo.check_agent_spec(
        "auditor", spec(["get_issue", tool]), duo.AUDITOR_TOOLS, duo.AUDITOR_OPTIONAL_TOOLS
    )
    assert any(tool in p and "IDE-only" in p for p in problems)


def test_a_note_tool_must_sit_in_the_optional_row() -> None:
    text = spec(["get_issue", "create_merge_request_note"])
    problems = duo.check_agent_spec("auditor", text, duo.AUDITOR_TOOLS, duo.AUDITOR_OPTIONAL_TOOLS)
    assert any("create_merge_request_note" in p for p in problems)


def test_an_agent_spec_without_a_tools_row_is_rejected() -> None:
    problems = duo.check_agent_spec("auditor", "# no table\n", duo.AUDITOR_TOOLS, frozenset())
    assert any("Tools row" in p for p in problems)


def test_the_planner_may_use_only_its_own_tools() -> None:
    assert (
        duo.check_agent_spec(
            "planner", spec(sorted(duo.PLANNER_TOOLS)), duo.PLANNER_TOOLS, frozenset()
        )
        == []
    )
    problems = duo.check_agent_spec(
        "planner", spec(["create_plan", "get_job_logs"]), duo.PLANNER_TOOLS, frozenset()
    )
    assert any("get_job_logs" in p for p in problems)


def test_the_repository_agent_specs_follow_the_lists() -> None:
    root = REPO_ROOT
    auditor = (root / "duo" / "custom-agent.md").read_text(encoding="utf-8")
    planner = (root / "duo" / "custom-planner.md").read_text(encoding="utf-8")
    assert (
        duo.check_agent_spec("auditor", auditor, duo.AUDITOR_TOOLS, duo.AUDITOR_OPTIONAL_TOOLS)
        == []
    )
    assert duo.check_agent_spec("planner", planner, duo.PLANNER_TOOLS, frozenset()) == []


def test_a_missing_planner_spec_fails_loudly(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    import shutil

    for rel in (".gitlab", ".agents", "duo"):
        shutil.copytree(REPO_ROOT / rel, tmp_path / rel)
    (tmp_path / "duo" / "custom-planner.md").unlink(missing_ok=True)
    assert duo.main(["--root", str(tmp_path)]) == 1
    assert "duo/custom-planner.md does not exist" in capsys.readouterr().err
