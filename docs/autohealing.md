# Autohealing and the hands-off loop

The loop has two entries. Nothing of entry B has run: until a real failure goes through it, the
README says so, and no step here is claimed to work.

| Entry | Path | Status |
|---|---|---|
| A, feature | An issue starts the Developer Flow, which opens a merge request; the pipeline gates judge it | Ran three times by hand (!16, !17, !18): [evidence](submission/evidence.md) |
| B, autohealing | A failed pipeline starts everything: issue with the diagnosis, a fix, a merge request, review, merge when the gates are green, release, deploy, monitor, summary on the issue | Not run |

## What the documentation allows

Read on docs.gitlab.com on 2026-10-25.

| Question | Answer | Source |
|---|---|---|
| Trigger on a failed pipeline | Event type **Pipeline events**, actions Running, Passed, Failed, Canceled. The flow receives the address of the project and the action, not a pipeline id | [Triggers](https://docs.gitlab.com/user/duo_agent_platform/triggers/) |
| Fix CI/CD Pipeline from a trigger | The triggers page says it accepts only pipeline events; its own page describes only the **Fix pipeline with Duo** button | [Triggers](https://docs.gitlab.com/user/duo_agent_platform/triggers/), [Fix pipeline](https://docs.gitlab.com/ci/pipelines/fix_pipeline/) |
| What Fix CI/CD produces | In a merge request pipeline: inline code suggestions on the source branch, which a person applies; a new merge request if the fix is outside the diff. In a pipeline with no merge request: a new merge request. Sometimes only a comment. No attempt cap is documented | [Fix pipeline](https://docs.gitlab.com/ci/pipelines/fix_pipeline/) |
| Who can start a trigger | A person only. A bot, a service account or another flow cannot | [Triggers](https://docs.gitlab.com/user/duo_agent_platform/triggers/) |
| Branch or label filter on a trigger | Not documented (only status and type for work items) | [Triggers](https://docs.gitlab.com/user/duo_agent_platform/triggers/) |
| A flow opens or comments on an issue | `create_issue` and `create_issue_note` | [Tools](https://docs.gitlab.com/user/duo_agent_platform/agents/tools/) |
| A CI job opens or comments on an issue | `CI_JOB_TOKEN` cannot create an issue or a note on an issue | [Job token](https://docs.gitlab.com/ci/jobs/ci_job_token/) |
| Start the Developer Flow with no click | Not documented. Assign, mention, the **Implement** button or a status change; a trigger on work item created does not start it | [Developer Flow](https://docs.gitlab.com/user/project/merge_requests/developer/) |
| A Duo tool that merges a merge request | None, and none sets auto-merge. This is about Duo only: the merge is done by `merge_guard`, see the section on delivery and deployment | [Tools](https://docs.gitlab.com/user/duo_agent_platform/agents/tools/) |
| Automatic review | Runs when a merge request is created and is not a draft, when a draft is marked ready, on a manual request, and on a push if **Start a new review on push** is on | [Duo in merge requests](https://docs.gitlab.com/user/project/merge_requests/duo_in_merge_requests/) |

Three consequences, each to be confirmed by running it:

1. A pipeline started by a service account cannot trigger anything, so only the first failure of a
   change made by a person starts the repair. A flow's own failing push does not start a second
   attempt. The cap of 3 in `merge_guard` stays as a backstop and may never be reached.
2. In a merge request pipeline the Fix CI/CD Pipeline Flow suggests and a person applies, so the
   path with no person is the new merge request it opens for a pipeline with no merge request.
3. There is no filter that keeps a trigger away from `main`. A failure on `main` starts the repair
   as well, and the fix arrives as a new merge request, never as a push.

## Delivery or deployment: the merge is a setting, not a click

Duo has no tool that merges (see the table above), but the repository does not need one: `merge_guard` runs in
the merge request pipeline and merges through the API when its verdict is yes. Both modes are
supported; the mode is the CI/CD variable `AFAW_AUTO_MERGE`.

| Mode | `AFAW_AUTO_MERGE` | Who merges | Status |
|---|---|---|---|
| Continuous delivery | unset or not `true` | A person, after `merge_guard` prints `merge: yes` | Every merge so far (!1 to !25) |
| Continuous deployment | `true`, with `AFAW_MERGE_TOKEN` and `AFAW_BOT_USER_IDS` set | `merge_guard`, with no person, then release, deploy and monitor run on `main` | Code and tests exist; **never run on a real merge request** |

The verdict is the same in both modes: green pipeline including `red_check`, `mutation_gate` and
`security_gate`, no protected file, no draft, cap of 3 automatic fixes, and a pipeline user and
commit authors that are all service accounts. Only the last step differs.

The token is the cost of continuous deployment: `AFAW_MERGE_TOKEN` must be allowed to merge, so
it should be a project access token with the Developer role and the `api` scope, masked and
protected so that only pipelines on protected refs read it. The human decides whether to create it.

## The smallest design

Two triggers on the same event, because one flow cannot start another:

| # | Trigger | Starts | Does |
|---|---|---|---|
| 1 | Pipeline events > Failed | Foundational flow **Fix CI/CD Pipeline** | Suggests a fix or opens a merge request with it |
| 2 | Pipeline events > Failed | Custom flow **AFAW triage** ([`duo/triage-flow.yaml`](../duo/triage-flow.yaml)) | Opens one issue per failing job and short sha, titled `autoheal: <job> @ <sha8>`, with the label `afaw-autoheal`; adds a note to the issue instead if an open one has that title |

Loop protection:

* One open issue per `autoheal: <job> @ <sha8>`: the flow searches the open issues for the title
  before it creates one, and creates at most 5 per run.
* A flow cannot start a trigger, so neither flow starts the other and a fix push does not start
  another repair.
* The cap of 3 automatic fix attempts is counted by `merge_guard` from the pipelines started by the
  service accounts in `AFAW_BOT_USER_IDS` (33073387, 33073386 and any new account). When it is passed
  the job fails and the merge request cannot merge. The issue stays open with its label.
* The custom flow can only read and write issues and notes; `scripts/check_duo_config.py` enforces
  its allow list (`gitlab_api_get`, `get_pipeline_failing_jobs`, `get_job_logs`, `list_issues`,
  `create_issue`, `create_issue_note`) and the forbidden list (anything that changes code, a
  merge request, an existing issue or a vulnerability, or runs tests).

Not verified: that `create_issue` applies a label (the flow writes `/label ~afaw-autoheal` as the last
line of the description for that reason), that a quick action in an issue description is run when a
tool creates the issue, and that a pipeline started by a person's push is the event a trigger sees.

## What a person sets in the UI

| # | Menu path | Setting | How you know it worked |
|---|---|---|---|
| 1 | Project **Manage > Labels > New label** | Create `afaw-autoheal` | The label is listed |
| 2 | **Automate > Flows** (or **AI > Flows**) **> New flow** | Paste [`duo/triage-flow.yaml`](../duo/triage-flow.yaml); name it "AFAW triage". The editor validates the tool names: report any it refuses | The flow is saved; enable it in the project |
| 3 | **AI > Triggers > New trigger** | Event type Pipeline events, action Failed, flow Fix CI/CD Pipeline | The trigger is listed |
| 4 | **AI > Triggers > New trigger** | Event type Pipeline events, action Failed, flow AFAW triage | The trigger is listed |
| 5 | Report what the trigger form shows | Any field for branch, label or user; the owner of the trigger (service account) | It tells us whether `main` can be excluded |

Triggers need Premium or Ultimate. If **AI > Triggers** does not exist, the tier does not allow it
and the autohealing path has no start: say so in the README.

### How to provoke one failure

Push a change that breaks one job to a branch with no merge request, after the triggers exist. The
branch `demo/task-028-lint-failure` (one unused import, only `lint` fails) has no merge request. A
new push to it makes a new pipeline that fails and is the event. Check, in this order: an issue
`autoheal: lint @ <sha8>` with the label; a Fix CI/CD session; a merge request from the flow; its
pipeline; the verdict of `merge_guard`.

## Experiments, one at a time

### A. Merge by an agent

The tools page lists no tool that merges (checked 2026-10-25). In **AI > Agents > New agent**, look in
the tool selector for one that accepts or merges a merge request, and report its exact name and
description. If it exists, create "AFAW merger" with the read tools of the AFAW auditor plus that tool
and this prompt, and invoke it from the chat on one merge request:

```text
You merge one merge request only if every condition holds, otherwise you comment and stop.
Conditions: the whole pipeline of the head commit is green (every job success); no changed
file is .gitlab-ci.yml, AGENTS.md, state/equivalent_mutants.json, state/config.json or under
deploy/; the merge_guard job printed "merge: yes"; fewer than 3 commits were pushed by service accounts
after the first failed pipeline. Read the jobs and the merge_guard log before deciding. Copy every
status exactly. If you cannot verify a condition, write "not verified", comment the reason on the merge
request and stop. Never merge a draft. Write in English.
```

What to report: whether the merge request merged, and whether it merged with the pipeline still
running or red (that shows whether the tool honors **Pipelines must succeed**, a Maintainer setting
under **Settings > Merge requests > Merge checks**). Nothing here creates or needs a token.

### B. Clear the Draft state

Create a throwaway agent with `get_merge_request`, `update_merge_request` and
`create_merge_request_note`. Ask it, on !16, to remove the `Draft:` prefix from the title. Then ask it
to post a note containing only `/ready`. Expected from the tools page: the title edit can work; the
note cannot, since `create_merge_request_note` states that quick actions are not supported. Report
which of the two changed the merge request. `update_merge_request` can also close the merge request or
change its target branch, so adopting it needs a decision on that risk.

### C. Start the Developer Flow from an issue template

Create an issue from the template [`.gitlab/issue_templates/duo-feature.md`](../.gitlab/issue_templates/duo-feature.md)
once it is on the default branch (or paste its last line into a new issue). The template assigns the
Duo Developer account. It works if the issue shows that assignee and a Developer Flow session starts
with no further click. It needs the Assign trigger of the Developer Flow to exist (**AI > Triggers**).
