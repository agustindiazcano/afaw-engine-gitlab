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
| `duo/custom-agent.md` | Source of the custom agent "AFAW auditor" (read-only), pasted in **AI > Agents > New agent** | Not read by GitLab from here |
| `scripts/check_duo_config.py` | CI check (`duo_config` job) that these files use only documented keys, tools and limits | CI |

The custom agent and the custom flow are created in the UI because the documentation describes no
repository file for them. The files in `duo/` are the reviewed source, not something GitLab loads.

## What a person has to do (and our role may not allow)

| # | Priority | Step | Role the documentation asks for |
|---|---|---|---|
| 1 | 🔴 | Turn on **Allow flow execution** and **Allow foundational flows**, and the individual flows **Developer**, **Code Review** and **Fix CI/CD Pipeline**, under **Settings > GitLab Duo** of the **top-level group** | Owner of the top-level group. Here that is `gitlab-ai-hackathon`, which is not ours; the organizers may already have set it. Check in the project: **Settings > General > GitLab Duo** |
| 2 | 🔴 | Have a runner for the flows: GitLab hosted runners enabled for the project, or one tagged `gitlab--duo` with a Docker-capable executor | Maintainer. Hosted runners already run our pipelines |
| 3 | 🔴 | Push rules that allow the flows' service account | Maintainer. Push rules need Premium or Ultimate |
| 4 | 🟡 | Create the custom agent (**AI > Agents**) and the custom flow (**AI > Flows**), enable the flow in the project and add its trigger | Maintainer or Owner |
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
| `AGENTS.md` section 6.1 says the LLM never executes tools with side effects | Duo flows exist to call tools | The custom flow is limited to writing notes by `check_duo_config.py`. The Developer and Fix flows write code, but only into a merge request that must pass every deterministic gate. The section is reworded in the later `AGENTS.md` merge request listed in `PENDING.md` |
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
