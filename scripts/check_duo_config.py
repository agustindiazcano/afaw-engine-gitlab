"""Check the GitLab Duo configuration files against what docs.gitlab.com documents.

Only documented keys, tools and limits are accepted, so a typo or a guessed key fails here
instead of at the first flow run. The sources (verified on 2026-10-24):
  - .gitlab/duo/agent-config.yml: docs/user/duo_agent_platform/flows/execution/agent-config-yaml
  - .gitlab/duo/mr-review-instructions.yaml: .../customize/review_instructions
  - .agents/agents/*.md (workspace subagents of the Developer Flow):
    .../customize/workspace_subagents
  - duo/custom-flow.yaml (Flow Registry v1, pasted in AI > Flows): .../flows/custom_flows_schema
    and .../flows/claude-edit-v1-flow-registry
  - tool names: .../agents/tools

The custom flow may write notes only: it never changes code or the merge request, because the
merge decision belongs to the deterministic engine (ADR 0007). The custom agents of duo/ (the
AFAW auditor and the AFAW planner) may use only the tools of their allow list, none of the
forbidden tools and none of the IDE-only tools, which a Web UI session does not have.

Run in CI: python -m scripts.check_duo_config
Exit codes: 0 ok, 1 a problem was found.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

AGENT_CONFIG = ".gitlab/duo/agent-config.yml"
REVIEW_INSTRUCTIONS = ".gitlab/duo/mr-review-instructions.yaml"
SUBAGENT_DIR = ".agents/agents"
CUSTOM_FLOW = "duo/custom-flow.yaml"
AUDITOR_SPEC = "duo/custom-agent.md"
PLANNER_SPEC = "duo/custom-planner.md"
TRIAGE_FLOW = "duo/triage-flow.yaml"

# Tools documented on docs.gitlab.com/user/duo_agent_platform/agents/tools.
DOCUMENTED_TOOLS = frozenset(
    """add_merge_request_reviewers build_review_merge_request_context create_merge_request
    create_merge_request_diff_note create_merge_request_note get_merge_request
    gitlab_merge_request_search link_vulnerability_to_merge_request list_all_merge_request_notes
    list_merge_request_diffs list_mr_discussions reply_to_discussion set_discussion_resolved
    submit_mr_review update_merge_request create_issue create_issue_note
    create_vulnerability_issue get_issue get_issue_note gitlab_issue_search
    link_vulnerability_to_issue list_issue_notes list_issues update_issue create_work_item
    create_work_item_note get_work_item get_work_item_notes get_work_item_statuses
    list_work_items update_work_item create_epic get_epic get_epic_note list_epics
    list_epic_notes update_epic ci_linter get_downstream_pipelines get_failing_bridge_jobs
    get_job_logs get_pipeline_errors get_pipeline_failing_jobs extract_lines_from_text
    get_repository_file get_repository_files list_repository_tree gitlab_blob_search
    create_branch create_commit get_commit get_commit_comments get_commit_diff
    gitlab_commit_search list_commits gitlab_documentation_search gitlab_group_project_search
    gitlab_milestone_search gitlab_note_search gitlab__user_search gitlab_wiki_blob_search
    add_new_task create_plan get_plan remove_task set_task_status update_task_description
    get_wiki_page get_current_user get_project get_session_context run_glql_query
    gitlab_api_get gitlab_graphql run_tests confirm_vulnerability dismiss_vulnerability
    get_security_finding_details get_vulnerability_details list_security_findings
    list_vulnerabilities post_sast_fp_analysis_to_gitlab revert_to_detected_vulnerability
    update_vulnerability_severity list_group_audit_events list_instance_audit_events
    list_project_audit_events create_file_with_contents edit_file find_files grep list_dir mkdir
    notify_me_when read_file read_files run_command run_git_command""".split()
)
# Tools that change code, the merge request or the issue state: not allowed in the custom flow.
FLOW_FORBIDDEN_TOOLS = frozenset(
    """create_commit create_branch create_merge_request update_merge_request update_issue
    create_issue create_file_with_contents edit_file mkdir run_command run_git_command
    add_merge_request_reviewers submit_mr_review set_discussion_resolved""".split()
)

# Custom agents (duo/custom-agent.md, duo/custom-planner.md), created in the GitLab UI. Tools
# verified on docs.gitlab.com/user/duo_agent_platform/agents/tools on 2026-10-25.
AUDITOR_TOOLS = frozenset(
    """get_merge_request list_merge_request_diffs build_review_merge_request_context
    list_all_merge_request_notes list_mr_discussions get_pipeline_errors
    get_pipeline_failing_jobs get_job_logs ci_linter get_repository_file get_repository_files
    list_repository_tree gitlab_blob_search get_commit get_commit_diff list_commits get_issue
    list_issues list_security_findings get_security_finding_details list_vulnerabilities
    gitlab_api_get get_commit_comments get_failing_bridge_jobs get_issue_note
    gitlab_issue_search""".split()
)
AUDITOR_OPTIONAL_TOOLS = frozenset({"create_merge_request_note", "create_merge_request_diff_note"})
PLANNER_TOOLS = frozenset(
    """create_plan add_new_task set_task_status get_plan get_issue list_issues
    get_repository_file list_repository_tree create_issue_note""".split()
)
# Never given to a custom agent: they change code, the merge request, an issue or a
# vulnerability, or run tests.
AGENT_FORBIDDEN_TOOLS = frozenset(
    """create_commit create_branch create_merge_request update_merge_request create_issue
    update_issue confirm_vulnerability dismiss_vulnerability revert_to_detected_vulnerability
    update_vulnerability_severity submit_mr_review set_discussion_resolved run_tests""".split()
)
# Available only in the IDE; a custom agent used from the Web UI does not have them.
IDE_ONLY_TOOLS = frozenset(
    {"find_files", "grep", "read_file", "read_files", "list_dir", "run_command"}
)

# The autohealing triage flow (duo/triage-flow.yaml) reads a failed pipeline and opens one issue per
# failing job. It is the one flow that may create an issue; it changes nothing else.
TRIAGE_TOOLS = frozenset(
    """gitlab_api_get get_pipeline_failing_jobs get_job_logs list_issues create_issue
    create_issue_note""".split()
)
TRIAGE_FORBIDDEN_TOOLS = (FLOW_FORBIDDEN_TOOLS | AGENT_FORBIDDEN_TOOLS | IDE_ONLY_TOOLS) - {
    "create_issue"
}

FLOW_KEYS = {"version", "environment", "components", "prompts", "routers", "flow"}
FLOW_REJECTED = {"name", "description", "product_group"}
COMPONENT_TYPES = {
    "AgentComponent",
    "OneOffComponent",
    "DeterministicStepComponent",
    "HumanInputComponent",
}
FLOW_MAX_BYTES = 40 * 1024
SUBAGENT_MAX_FILES = 10
SUBAGENT_MAX_FILE_BYTES = 64 * 1024
SUBAGENT_MAX_TOTAL_BYTES = 112 * 1024
AGENT_CONFIG_KEYS = {"image", "setup_script", "network_policy", "cache"}
NETWORK_KEYS = {
    "allowed_domains",
    "denied_domains",
    "include_recommended_allowed",
    "allow_all_unix_sockets",
}
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def check_agent_config(data: Any) -> list[str]:
    """Problems of an agent-config.yml (documented keys only)."""
    if not isinstance(data, dict):
        return [f"{AGENT_CONFIG}: must be a mapping"]
    problems = [
        f"{AGENT_CONFIG}: unsupported key {k!r}" for k in data if k not in AGENT_CONFIG_KEYS
    ]
    image = data.get("image")
    if "image" in data and (not isinstance(image, str) or not 1 <= len(image) <= 512):
        problems.append(f"{AGENT_CONFIG}: image must be a string of 1 to 512 characters")
    script = data.get("setup_script")
    if "setup_script" in data and not (
        isinstance(script, str)
        or (isinstance(script, list) and all(isinstance(s, str) for s in script))
    ):
        problems.append(f"{AGENT_CONFIG}: setup_script must be a string or a list of strings")
    network = data.get("network_policy", {})
    if not isinstance(network, dict):
        problems.append(f"{AGENT_CONFIG}: network_policy must be a mapping")
    else:
        problems += [
            f"{AGENT_CONFIG}: unsupported network_policy key {k!r}"
            for k in network
            if k not in NETWORK_KEYS
        ]
    cache = data.get("cache", {})
    if not isinstance(cache, dict) or ("cache" in data and "paths" not in cache):
        problems.append(f"{AGENT_CONFIG}: cache needs paths")
    return problems


def check_review_instructions(data: Any) -> list[str]:
    """Problems of an mr-review-instructions.yaml."""
    where = REVIEW_INSTRUCTIONS
    if not isinstance(data, dict) or set(data) != {"instructions"}:
        return [f"{where}: the only top-level key must be 'instructions'"]
    entries = data["instructions"]
    if not isinstance(entries, list) or not entries:
        return [f"{where}: 'instructions' must be a non-empty list"]
    problems: list[str] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            problems.append(f"{where}: entry {i} must be a mapping")
            continue
        problems += [
            f"{where}: entry {i} lacks {k!r}" for k in ("name", "instructions") if not entry.get(k)
        ]
        problems += [
            f"{where}: entry {i} has unsupported key {k!r}"
            for k in entry
            if k not in {"name", "instructions", "fileFilters"}
        ]
        filters = entry.get("fileFilters", [])
        if not isinstance(filters, list):
            problems.append(f"{where}: entry {i} fileFilters must be a list")
    return problems


def _front_matter(text: str) -> tuple[dict[str, Any], str] | None:
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text.replace("\r\n", "\n"), re.S)
    if not match:
        return None
    meta = yaml.safe_load(match.group(1)) or {}
    return (meta, match.group(2)) if isinstance(meta, dict) else None


def check_subagent(filename: str, text: str) -> list[str]:
    """Problems of one workspace subagent file."""
    parsed = _front_matter(text)
    if parsed is None:
        return [f"{filename}: must start with YAML front matter between --- lines"]
    meta, body = parsed
    problems = [
        f"{filename}: unsupported front matter key {k!r}"
        for k in meta
        if k not in {"name", "description", "tools"}
    ]
    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        problems.append(f"{filename}: description is required")
    elif len(description) > 1024:
        problems.append(f"{filename}: description is over 1024 characters")
    if len(str(meta.get("name", Path(filename).stem))) > 64:
        problems.append(f"{filename}: name is over 64 characters")
    tools = meta.get("tools", [])
    names = [t.strip() for t in tools.split(",")] if isinstance(tools, str) else list(tools)
    problems += [f"{filename}: unknown tool {t!r}" for t in names if t not in DOCUMENTED_TOOLS]
    if not body.strip() or len(body) > 10_000:
        problems.append(f"{filename}: the prompt must be 1 to 10000 characters")
    if len(text.encode("utf-8")) > SUBAGENT_MAX_FILE_BYTES:
        problems.append(f"{filename}: file is over 64 KB")
    return problems


def _tool_row(text: str, label: str) -> list[str] | None:
    """The backticked tool names of the ``| label | ... |`` row of a spec, None if absent."""
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|", 1)]
        if len(cells) == 2 and cells[0] == label:
            return re.findall(r"`([A-Za-z0-9_]+)`", cells[1])
    return None


def check_agent_spec(
    filename: str, text: str, allowed: frozenset[str], optional: frozenset[str]
) -> list[str]:
    """Problems of a custom agent spec: its tools must follow the allow and forbidden lists."""
    required = _tool_row(text, "Tools")
    if required is None:
        return [f"{filename}: no Tools row in the field table"]
    extra = _tool_row(text, "Optional tools") or []
    problems: list[str] = []
    rows = (("Tools", required, allowed), ("Optional tools", extra, optional))
    for row, tools, permitted in rows:
        for tool in tools:
            if tool in AGENT_FORBIDDEN_TOOLS:
                problems.append(f"{filename}: {tool!r} is forbidden for a custom agent")
            elif tool in IDE_ONLY_TOOLS:
                problems.append(f"{filename}: {tool!r} is IDE-only and not used")
            elif tool not in DOCUMENTED_TOOLS:
                problems.append(f"{filename}: unknown tool {tool!r}")
            elif tool not in permitted:
                problems.append(f"{filename}: {tool!r} is not in the allow list of the {row} row")
    return problems


def check_flow(
    flow: Any,
    size: int = 0,
    where: str = CUSTOM_FLOW,
    allowed: frozenset[str] | None = None,
    forbidden: frozenset[str] = FLOW_FORBIDDEN_TOOLS,
) -> list[str]:
    """Problems of a custom flow (Flow Registry v1) against the documented schema.

    ``where`` names the file in the messages. With ``allowed`` the toolset must stay inside that
    list; ``forbidden`` tools are rejected by name either way.
    """
    if size > FLOW_MAX_BYTES:
        return [f"{where}: the flow is over 40 KiB"]
    if not isinstance(flow, dict):
        return [f"{where}: must be a mapping"]
    problems = [f"{where}: {k!r} is rejected in a custom flow" for k in flow if k in FLOW_REJECTED]
    problems += [
        f"{where}: unsupported top-level key {k!r}"
        for k in flow
        if k not in FLOW_KEYS | FLOW_REJECTED
    ]
    if flow.get("version") != "v1":
        problems.append(f"{where}: version must be 'v1'")
    if flow.get("environment") != "ambient":
        problems.append(f"{where}: environment must be ambient (the only one custom flows support)")
    prompts = {p.get("prompt_id"): p for p in flow.get("prompts", []) if isinstance(p, dict)}
    components = [c for c in flow.get("components", []) if isinstance(c, dict)]
    names = {c.get("name") for c in components}
    for comp in components:
        problems += _check_component(comp, prompts, where, allowed, forbidden)
    for prompt in prompts.values():
        problems += _check_prompt(prompt, components, where)
    for router in flow.get("routers", []):
        if router.get("from") not in names:
            problems.append(f"{where}: router starts at unknown component {router.get('from')!r}")
        if router.get("to") not in names | {"end", "abort"}:
            problems.append(f"{where}: router goes to unknown component {router.get('to')!r}")
    entry = (flow.get("flow") or {}).get("entry_point")
    if entry not in names:
        problems.append(f"{where}: entry_point {entry!r} is not a component")
    return problems


def _check_component(
    comp: dict[str, Any],
    prompts: dict[Any, Any],
    where: str,
    allowed: frozenset[str] | None,
    forbidden: frozenset[str],
) -> list[str]:
    name = comp.get("name")
    problems: list[str] = []
    if comp.get("type") not in COMPONENT_TYPES:
        problems.append(f"{where}: component {name!r} has unsupported type {comp.get('type')!r}")
    for key in ("response_schema_id", "response_schema_version", "ui_role_as"):
        if key in comp:
            problems.append(
                f"{where}: component {name!r} uses {key}, which custom flows do not support"
            )
    if comp.get("type") == "AgentComponent":
        if comp.get("prompt_id") not in prompts:
            problems.append(f"{where}: component {name!r} uses an undefined prompt")
        sources = {i.get("from") for i in comp.get("inputs", []) if isinstance(i, dict)}
        if "context:project_id" not in sources:
            problems.append(f"{where}: component {name!r} must receive context:project_id")
    for tool in comp.get("toolset", []):
        tool_name = tool if isinstance(tool, str) else next(iter(tool), "")
        if tool_name not in DOCUMENTED_TOOLS:
            problems.append(f"{where}: component {name!r} uses unknown tool {tool_name!r}")
        elif tool_name in forbidden:
            problems.append(
                f"{where}: component {name!r} may not use {tool_name!r} (it changes code or the MR)"
            )
        elif allowed is not None and tool_name not in allowed:
            problems.append(
                f"{where}: component {name!r} uses {tool_name!r}, which is not in the allow list"
            )
    return problems


def _check_prompt(
    prompt: dict[str, Any], components: list[dict[str, Any]], where: str
) -> list[str]:
    pid = prompt.get("prompt_id")
    problems: list[str] = []
    if "unit_primitives" not in prompt:
        problems.append(f"{where}: prompt {pid!r} lacks unit_primitives (use [] when empty)")
    if "model" in prompt:
        problems.append(f"{where}: prompt {pid!r} sets model, which is not supported")
    if "stop" in (prompt.get("params") or {}):
        problems.append(f"{where}: prompt {pid!r} sets params.stop, which is not supported")
    template = prompt.get("prompt_template") or {}
    system, user = str(template.get("system", "")), str(template.get("user", ""))
    if PLACEHOLDER.search(system):
        problems.append(
            f"{where}: prompt {pid!r} uses a {{{{ }}}} placeholder in the system prompt"
        )
    if not re.search(r"\bstop\b", system, re.I):
        problems.append(f"{where}: prompt {pid!r} system prompt must say when to stop")
    provided = {
        i.get("as")
        for c in components
        if c.get("prompt_id") == pid
        for i in c.get("inputs", [])
        if isinstance(i, dict)
    }
    problems += [
        f"{where}: prompt {pid!r} uses {{{{ {v} }}}} but no input provides it"
        for v in PLACEHOLDER.findall(user)
        if v not in provided
    ]
    return problems


def _load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    """Validate every Duo configuration file of the repository."""
    parser = argparse.ArgumentParser(description="Validate the GitLab Duo configuration files.")
    parser.add_argument("--root", default=".", help="repository root (default: current directory)")
    root = Path(parser.parse_args(argv).root)
    problems: list[str] = []
    checks = (
        (AGENT_CONFIG, check_agent_config),
        (REVIEW_INSTRUCTIONS, check_review_instructions),
    )
    for rel, check in checks:
        path = root / rel
        problems += check(_load(path)) if path.is_file() else [f"{rel} does not exist"]
    flow_path = root / CUSTOM_FLOW
    if flow_path.is_file():
        problems += check_flow(_load(flow_path), flow_path.stat().st_size)
    else:
        problems.append(f"{CUSTOM_FLOW} does not exist")
    triage_path = root / TRIAGE_FLOW
    if triage_path.is_file():
        problems += check_flow(
            _load(triage_path),
            triage_path.stat().st_size,
            where=TRIAGE_FLOW,
            allowed=TRIAGE_TOOLS,
            forbidden=TRIAGE_FORBIDDEN_TOOLS,
        )
    else:
        problems.append(f"{TRIAGE_FLOW} does not exist")
    for rel, allowed, optional in (
        (AUDITOR_SPEC, AUDITOR_TOOLS, AUDITOR_OPTIONAL_TOOLS),
        (PLANNER_SPEC, PLANNER_TOOLS, frozenset[str]()),
    ):
        spec_path = root / rel
        if spec_path.is_file():
            problems += check_agent_spec(
                rel, spec_path.read_text(encoding="utf-8"), allowed, optional
            )
        else:
            problems.append(f"{rel} does not exist")
    agents = sorted((root / SUBAGENT_DIR).glob("*.md")) if (root / SUBAGENT_DIR).is_dir() else []
    if not agents:
        problems.append(f"{SUBAGENT_DIR} has no subagent")
    if len(agents) > SUBAGENT_MAX_FILES:
        problems.append(f"{SUBAGENT_DIR} has more than {SUBAGENT_MAX_FILES} subagents")
    total = sum(p.stat().st_size for p in agents)
    if total > SUBAGENT_MAX_TOTAL_BYTES:
        problems.append(f"{SUBAGENT_DIR} is over 112 KB in total")
    for agent in agents:
        problems += check_subagent(agent.name, agent.read_text(encoding="utf-8"))
    for item in problems:
        sys.stderr.write(f"PROBLEM: {item}\n")
    if problems:
        return 1
    sys.stdout.write("OK: Duo configuration files match the documented schemas\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
