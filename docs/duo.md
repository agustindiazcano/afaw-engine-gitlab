# GitLab Duo agent and flows

How the loop (issue to merge request to pipeline to fix to review to merge to deploy to monitor)
uses GitLab Duo Agent Platform: what lives in this repository, what has to be switched on in the
GitLab UI by a person with the right role, and what the documentation does not let us automate.
Nothing here is claimed to run until a human has enabled it and a real session has been seen.

## The loop, step by step

| # | Step | Mechanism | How it starts (documented) | Status |
|---|---|---|---|---|
| 1 | Issue to merge request | Developer Flow (foundational) | Assign the issue to `duo developer`, mention `@duo-developer-<namespace>`, the **Implement** button, or a work item status change | Needs the group switches below |
| 2 | Merge request to pipeline | `.gitlab-ci.yml` (task 009) | A push | Done |
| 3 | Pipeline failure to fix | Fix CI/CD Pipeline Flow (foundational) | The **Fix pipeline with Duo** button; automatic only if a trigger for **Pipeline events > Failed** can be created | Button documented, automatic trigger to confirm in the UI |
| 4 | Review | Code Review Flow (foundational), reading `.gitlab/duo/mr-review-instructions.yaml` | Assign `@GitLabDuo` as reviewer, mention it, or automatic reviews | Needs the group switches below |
| 5 | Merge | The deterministic policy (task 012), not Duo | Every gate green | Task 012 |
| 6 | Deploy | `publish_image` and `deploy_cloud_run` (task 013) | A merge to `main` | Needs task 013 applied |
| 7 | Monitor | `monitor_live` (task 013) | After the deploy | Needs task 013 applied |
| 8 | Summary on the issue | Custom flow "AFAW loop reporter" | A person mentions its service account | See the gap below |

Steps 1, 3 and 4 use GitLab's foundational flows as they are. A custom flow cannot call a custom
agent or another flow (the documentation says each custom flow creates its own agents), so the
custom flow covers only step 8.

## What is in this repository

| File | What it is | Who reads it |
|---|---|---|
| `.gitlab/duo/agent-config.yml` | Image, setup script, cache and network policy of the flow sandbox | All flows; read from the default branch only |
| `.gitlab/duo/mr-review-instructions.yaml` | AFAW review rules (TDD, no estimated numbers, English, human-only files, least privilege) | Code Review Flow. Guidance for the reviewer, not enforced policy |
| `.agents/agents/afaw-reviewer.md` | Workspace subagent that checks a change against `AGENTS.md`; tools `read_file` and `grep` only | Developer Flow; an experiment, read from the default branch only |
| `duo/custom-flow.yaml` | Source of the custom flow, pasted in **AI > Flows > New flow** | Not read by GitLab from here |
| `duo/triage-flow.yaml` | Source of the custom flow "AFAW triage": on a failed pipeline it opens one issue per failing job (the one flow allowed to create issues), pasted in **AI > Flows > New flow**. Design and UI steps: [`autohealing.md`](autohealing.md) | Not read by GitLab from here |
| `.gitlab/issue_templates/duo-feature.md` | Issue template whose last line assigns the Duo Developer account; whether the quick action starts the flow is an experiment (see [`autohealing.md`](autohealing.md)) | GitLab, from the default branch |
| `duo/custom-agent.md` | Source of the custom agent "AFAW auditor" (reads only; 26 read tools, plus two optional note tools), pasted in **AI > Agents > New agent** | Not read by GitLab from here |
| `duo/custom-planner.md` | Source of the custom agent "AFAW planner" (9 tools; it leaves a plan as a note on an issue and creates no issue), pasted in **AI > Agents > New agent** | Not read by GitLab from here |
| `scripts/check_duo_config.py` | CI check (`duo_config` job) that these files use only documented keys, tools and limits, and that each custom agent and each custom flow keeps to its allow list and uses no forbidden or IDE-only tool | CI |

The custom agents and the custom flow are created in the UI because the documentation describes no
repository file for them. The files in `duo/` are the reviewed source, not something GitLab loads.

## Tools of the custom agents

Names and availability were checked on docs.gitlab.com/user/duo_agent_platform/agents/tools on
2026-10-25: all 44 tools below exist; six are available only in the IDE.

| Agent | Tools | Optional |
|---|---|---|
| AFAW auditor | `get_merge_request`, `list_merge_request_diffs`, `build_review_merge_request_context`, `list_all_merge_request_notes`, `list_mr_discussions`, `get_pipeline_errors`, `get_pipeline_failing_jobs`, `get_job_logs`, `ci_linter`, `get_repository_file`, `get_repository_files`, `list_repository_tree`, `gitlab_blob_search`, `get_commit`, `get_commit_diff`, `list_commits`, `get_issue`, `list_issues`, `list_security_findings`, `get_security_finding_details`, `list_vulnerabilities`, `gitlab_api_get`, `get_commit_comments`, `get_failing_bridge_jobs`, `get_issue_note`, `gitlab_issue_search` | `create_merge_request_note`, `create_merge_request_diff_note`: findings go in the chat, or as a merge request note when these are selected |
| AFAW planner | `create_plan`, `add_new_task`, `set_task_status`, `get_plan`, `get_issue`, `list_issues`, `get_repository_file`, `list_repository_tree`, `create_issue_note` | None |

| Group | Tools | Rule |
|---|---|---|
| IDE only | `find_files`, `grep`, `read_file`, `read_files`, `list_dir`, `run_command` | Not used by the custom agents, which run from the Web UI |
| Forbidden for both agents | `create_commit`, `create_branch`, `create_merge_request`, `update_merge_request`, `create_issue`, `update_issue`, `confirm_vulnerability`, `dismiss_vulnerability`, `revert_to_detected_vulnerability`, `update_vulnerability_severity`, `submit_mr_review`, `set_discussion_resolved`, `run_tests` | They change code, a merge request, an issue or a vulnerability, or run tests. This is the project's rule, not something the tools page states |

The tools page marks the Read or Write behavior of no tool; that column is this project's reading of
each tool's description. `scripts/check_duo_config.py` enforces both lists on `duo/custom-agent.md`
and `duo/custom-planner.md`.

## What exists in GitLab (read on 2026-10-26)

| Name | Kind | Runs as | Started by | What ran, and when |
|---|---|---|---|---|
| Developer Flow | Foundational flow | `duo-developer-gitlab-ai-hackathon` (id 33073386) | A person or a script assigning an issue to the account | Dozens of sessions. Example: issues #37 to #43 became [!75](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/75) to [!81](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/81) in 95 to 132 s |
| Fix CI/CD Pipeline Flow | Foundational flow | `duo-fix-ci-cd-pipeline-gitlab-ai-hackathon` (id 33073387) | Trigger "AFAW fix on failed pipeline" (event Pipeline events, Failed), created 2026-10-26 | Ran once by hand on 2026-10-24 (pipeline 2985662569). The trigger has not been seen to fire yet |
| Code Review Flow | Foundational flow | `@GitLabDuo` | A person assigning `@GitLabDuo` as reviewer | Once: [session 10028468](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/automate/agent-sessions/10028468) on [!118](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/118), 2026-10-26, 1 min 51 s, three comments |
| AFAW loop reporter | Custom flow (`duo/custom-flow.yaml`) | `ai-afaw-loop-reporter-gitlab-ai-hackathon` (id 43732366) | Trigger on Mention: a person mentions the account in a merge request or issue | Once: [!110](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/110), sessions 10028680 and 10028682, 2026-10-26, 1 min 23 s. Two sessions started for one mention, so every note is posted twice |
| AFAW auditor | Custom agent (`duo/custom-agent.md`) | Chat in the Duo sidebar | A person, from a merge request | Created 2026-10-26; not run yet |
| AFAW planner | Custom agent (`duo/custom-planner.md`) | Chat in the Duo sidebar | A person, from an issue | Created 2026-10-26; not run yet |

Code, not agents, does the rest of the loop: `scripts/orchestrator.py` picks the next task and files the issue, `request_fix` opens an issue when a pipeline fails, `repair_check` compares the jobs an issue lists with the jobs of its repair, `merge_guard` decides and performs the merge, `telemetry_report` writes the event report and `handoff` writes the hand-over file for the next session.

## What a person has to do (and our role may not allow)

| # | Priority | Step | Role the documentation asks for |
|---|---|---|---|
| 1 | 🔴 | Turn on **Allow flow execution** and **Allow foundational flows**, and the individual flows **Developer**, **Code Review** and **Fix CI/CD Pipeline**, under **Settings > GitLab Duo** of the **top-level group** | Owner of the top-level group. Here that is `gitlab-ai-hackathon`, which is not ours; the organizers may already have set it. Check in the project: **Settings > General > GitLab Duo** |
| 2 | 🔴 | Have a runner for the flows: GitLab hosted runners enabled for the project, or one tagged `gitlab--duo` with a Docker-capable executor | Maintainer. Hosted runners already run our pipelines |
| 3 | 🔴 | Push rules that allow the flows' service account | Maintainer. Push rules need Premium or Ultimate |
| 4 | 🟡 | Create the custom agents, the AFAW auditor and the AFAW planner (**AI > Agents**), and the custom flow (**AI > Flows**), enable the flow in the project and add its trigger | Maintainer or Owner |
| 5 | 🟡 | Create the trigger for Fix CI/CD Pipeline (**AI > Triggers**, event **Pipeline events**, action **Failed**) | Maintainer or Owner; triggers need Premium or Ultimate |
| 6 | 🟡 | Read the ids of the flows' service accounts and put them in the group-level CI/CD variable `AFAW_BOT_USER_IDS` (comma-separated), so `human_only_files` treats them as non-human | Maintainer |
| 7 | 🟢 | Credits: the account has 500 GitLab Credits a month and each session spends them | Owner |

A trigger runs as the flow's service account (`ai-<flow>-<group>`, with the Developer role), and a
human has to perform the triggering action: bots, service accounts and other flows cannot start a
trigger.

## Gaps and the closest real alternative

| Gap | Why | Closest real alternative |
|---|---|---|
| No automatic summary after the merge | A custom flow starts by mention, assignment, reviewer assignment or a merge request or work item event. There is no "merged" event, and a bot or another flow cannot start a trigger | A person mentions the flow's service account once the deploy is green. A later task can add a deterministic CI job that posts the summary with a project access token |
| No cap of 3 automatic fix attempts | The Fix CI/CD Pipeline documentation names no attempt cap | The cap is enforced by the deterministic engine in task 012 (count the flow's commits on the merge request through the API and stop) |
| Foundational flows cannot be customized from the repository | They can be influenced with `AGENTS.md` (which the Code Review Flow does not read) and `agent-config.yml` | Rely on the CI gates, not on the flows obeying instructions |
| `AGENTS.md` section 6.1 says the LLM never executes tools with side effects | Duo flows exist to call tools | The custom flow is limited to writing notes by `check_duo_config.py`. The Developer and Fix flows write code, but only into a merge request that must pass every deterministic gate. Section 6.1 now states the exception for Duo flows (task 018) |
| A malformed subagent can stop the Developer Flow from starting | The documentation says an unavailable tool in a subagent prevents the session from starting | The subagent uses only the two tools of the documented example, and `duo_config` validates the file |

## What was verified, and what was not

Read on docs.gitlab.com on 2026-10-24 (pages under `user/duo_agent_platform`): custom agents,
custom flows, the custom flow YAML schema, the Flow Registry v1 reference, triggers, foundational
flows, the Developer, Code Review and Fix CI/CD Pipeline flows, `agent-config.yml`, review
instructions, workspace subagents, `AGENTS.md` customization, and the agent tools list.

Not verified until a human enables the flows and a real session runs:

| Open point | Note |
|---|---|
| The tool names in the custom flow's `toolset` | They are taken from the agent tools page; the flow editor validates them on creation |
| A trigger for Pipeline events > Failed on the Fix CI/CD Pipeline Flow | Two pages disagree on whether it is automatic; confirm in **AI > Triggers** |
| Whether the flows' service accounts are excluded by the `humans=true` user filter | Until confirmed, `AFAW_BOT_USER_IDS` lists them explicitly |
| The tier of the namespace | Push rules, triggers and `AGENTS.md` customization need Premium or Ultimate |
| `ui_log_events` and the optional component keys | Not used: only keys named in the documentation appear in the flow |
| `get_job`, `get_pipeline` and `get_merge_request_conflicts` | The agent created in the UI has them; the tools page does not list them. Rejected by `check_duo_config` until the description shown in the tool selector is read and checked |
| `read_file` and `grep` in `.agents/agents/afaw-reviewer.md` | The tools page lists both as IDE-only. The subagent follows the documented example, but whether the Developer Flow's sandbox provides them is not verified; a session that does not start would show it |
| The merge request author of a flow | With composite identity the merge request is attributed to the person who triggered the flow and the commits to the service account ([Composite identity](https://docs.gitlab.com/user/duo_agent_platform/composite_identity/)). How `human_only_files` sees this is confirmed only with the first merge request of a flow |
