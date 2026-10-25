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
| A Duo tool that merges a merge request, for a custom agent or flow | Not documented on the agent tools page. Duo Chat reports its own tool `gitlab_accept_merge_request` (parameters `sha`, `strategy` = `merge_when_checks_pass`, `merge_train` or `add_to_merge_train_when_checks_pass`, `squash`, `should_remove_source_branch`); the GitLab MCP server page documents `accept_merge_request` since GitLab 19.4, for external clients. The agent tool list read on 2026-10-25 (merge request tools: `add_merge_request_reviewers`, `build_review_merge_request_context`, `create_merge_request`, `create_merge_request_diff_note`, `create_merge_request_note`, `get_merge_request`, `gitlab_merge_request_search`, `link_vulnerability_to_merge_request`, `list_all_merge_request_notes`, `list_merge_request_diffs`, `update_merge_request`, plus `submit_mr_review`, `list_mr_discussions`, `reply_to_discussion`, `set_discussion_resolved`, `get_pipeline_errors`, `run_glql_query`) has **no tool that accepts or arms a merge**; `update_merge_request` can retarget, retitle or close; `gitlab_api_get` is read-only. So a Duo agent or flow cannot merge, and the merge stays with `merge_guard` and its token. The merge itself is done by `merge_guard` in this repository | [Tools](https://docs.gitlab.com/user/duo_agent_platform/agents/tools/), [MCP server tools](https://docs.gitlab.com/user/gitlab_duo/model_context_protocol/mcp_server_tools/), Duo Chat (not documentation) |
| Arm auto-merge by API | `PUT /projects/:id/merge_requests/:iid/merge` with `auto_merge=true` (the call `merge_guard` makes). `sha` may be required by a group setting. The token scope is **not stated** in what was read; `api` is unverified. A job token cannot call it; composite-identity tokens are limited to `ai_workflows` and `mcp` | [Merge requests API](https://docs.gitlab.com/api/merge_requests/) |
| Auto-merge by push option | `merge_request.auto_merge` (`merge_request.merge_when_pipeline_succeeds` is deprecated since 17.11), a `git push -o` option. Unknown whether the commit or branch API honours push options | [Stage, commit, and push](https://docs.gitlab.com/topics/git/commit/) |
| Protected branch and the merging account | Merging needs the account under **Allowed to merge** or **Allowed to push and merge**; by default only Maintainers. Unknown which identity a composite-identity service account is checked as | [Protected branches](https://docs.gitlab.com/user/project/repository/branches/protected/) |
| Trigger events on a merge request | `Merge request` with actions Marked ready, Approved, Created, Merge conflict; `Pipeline events` with Passed. Every one needs a human user; a bot, a service account or another flow cannot start it. Which user counts as the actor of a pipeline event is unknown | [Triggers](https://docs.gitlab.com/user/duo_agent_platform/triggers/) |
| Leaving Draft without a person | The Developer Flow opens a draft and has no setting to open it ready. `/ready` does not work through `create_merge_request_note` or `update_work_item`. Removing `Draft:` through `update_merge_request` is an inference, **not verified** (experiment B). A flow that marks it ready cannot start a trigger | [Developer Flow](https://docs.gitlab.com/user/project/merge_requests/developer/), [Draft MRs](https://docs.gitlab.com/user/project/merge_requests/drafts/) |
| A comment on the issue after the merge | `create_issue_note` is available to custom agents. No event runs after a merge (documented: Mention, Assign, Assign reviewer, Pipeline events, Merge request, Work item) | [Triggers](https://docs.gitlab.com/user/duo_agent_platform/triggers/) |
| Fix CI/CD commits instead of suggesting | No setting found. In an MR pipeline it applies inline suggestions; outside the diff it opens a new MR; sometimes it only comments | [Fix pipeline](https://docs.gitlab.com/ci/pipelines/fix_pipeline/) |
| Fields of the trigger form | Description; Event, Run when and per-event Instructions (4096 characters at most); Service account; Configuration source; for work items, Status and Type. No branch, label or user field, so `main` cannot be excluded | [Triggers](https://docs.gitlab.com/user/duo_agent_platform/triggers/) |

These rows come from Duo Chat's answer of 2026-10-25, which tagged each one as documentation or as
its own toolset. They were not re-read page by page here, except the tools page and the auto-merge
page, which were fetched directly and agree.
| Automatic review | Runs when a merge request is created and is not a draft, when a draft is marked ready, on a manual request, and on a push if **Start a new review on push** is on | [Duo in merge requests](https://docs.gitlab.com/user/project/merge_requests/duo_in_merge_requests/) |

Three consequences, each to be confirmed by running it:

1. A pipeline started by a service account cannot trigger anything, so only the first failure of a
   change made by a person starts the repair. A flow's own failing push does not start a second
   attempt. The cap of 3 in `merge_guard` stays as a backstop and may never be reached.
2. In a merge request pipeline the Fix CI/CD Pipeline Flow suggests and a person applies, so the
   path with no person is the new merge request it opens for a pipeline with no merge request.
3. There is no filter that keeps a trigger away from `main`. A failure on `main` starts the repair
   as well, and the fix arrives as a new merge request, never as a push.

## Autoheal without triggers: `request_fix`

The triggers need a person and have no branch filter, so the repair is asked for by a CI job. It
rests on two facts observed on 2026-10-25: a note on a merge request that mentions the Developer
Flow account starts a flow session (pipeline 2986992512, from a note on !29), and assigning an
issue to the account through the API starts it too (issues #6 and #12).

`scripts/request_fix.py`, the `request_fix` job (stage `monitor`, `when: on_failure`, only when
`AFAW_AUTO_MERGE` is `true`):

| Where the pipeline failed | What the job writes | Cap |
|---|---|---|
| A merge request pipeline | One note that mentions the flow, with the failed jobs and the end of each log | 3 requests per merge request; one per commit |
| A branch with no merge request, or `main` | One issue assigned to the flow, labelled `afaw-autoheal`, titled `autoheal: <jobs> @ <sha8>` | 3 per branch and 6 open for the whole project |

The note and the issue are written with `AFAW_MERGE_TOKEN`, which belongs to a person: a bot or
another flow cannot start a flow. When the flow pushes a fix, its pipeline fails or passes on its
own, and the same job asks again after a new failure until the cap. The pipeline gates and
`merge_guard` still judge whatever the flow writes. Never run on a real failure of the project
until this merge request is in `main`.

## Delivery or deployment: the merge is a setting, not a click

Duo has no tool that merges (see the table above), but the repository does not need one: `merge_guard` runs in
the merge request pipeline and merges through the API when its verdict is yes. Both modes are
supported; the mode is the CI/CD variable `AFAW_AUTO_MERGE`.

| Mode | `AFAW_AUTO_MERGE` | Who merges | Status |
|---|---|---|---|
| Continuous delivery | unset or not `true` | A person, after `merge_guard` prints `merge: yes` | Every merge so far (!1 to !25) |
| Continuous deployment | `true`, with `AFAW_MERGE_TOKEN` and `AFAW_BOT_USER_IDS` set | `merge_guard`, with no person, then release, deploy and monitor run on `main` | Code and tests exist; **never run on a real merge request** |

Only the token is a secret. `AFAW_AUTO_MERGE` (the literal `true`) and `AFAW_BOT_USER_IDS` (ids
separated by commas) must not be masked: GitLab masks only values of 8 or more characters from a
restricted alphabet, with no comma, so a masked `true` is refused and `truetrue` is read as off,
because the guard compares with exactly `true`. Leave both variables unmasked and unprotected.

The verdict is the same in both modes: green pipeline including `red_check`, `mutation_gate` and
`security_gate`, no protected file, no draft, cap of 3 automatic fixes, and a pipeline user and
commit authors that are all service accounts. Only the last step differs.

The token is the cost of continuous deployment: `AFAW_MERGE_TOKEN` must be allowed to merge, so
it should be a project access token with the Developer role and the `api` scope, masked. It cannot
be protected: a protected variable is not passed to merge request pipelines of unprotected
branches, so any pipeline of the project can read it ([`merge-guard.md`](merge-guard.md)). Two
more conditions: ADR 0007 must be `accepted` by the human, and the merge request must be made by
a Duo flow, because `merge_guard` never merges a person's merge request. The human decides whether
to create the token.

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
