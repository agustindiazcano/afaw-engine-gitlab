# Evidence

What ran, where to see it, when, and the result. Only things that were observed are listed; each
row was read from the public GitLab API or from the live service. Dates are GMT-3, like the rest of
the history. Nothing here is an estimate. Rows are added only after the thing has run.

## Deploy and live service

| What ran | Link | Date (GMT-3) | Result |
|---|---|---|---|
| Pipeline started by hand on `main`: build, publish image, deploy to Cloud Run, monitor | [pipeline 2985631519](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985631519) | 2026-10-24 23:19 | Status success; 19 jobs, all with status success |
| `GET /health` on the deployed service | https://afaw-handsoff-ljm5hefnsq-uc.a.run.app/health | 2026-10-24 23:50 | HTTP 200, body `{"status":"ok"}` |

## GitLab Duo

| What ran | Link | Date (GMT-3) | Result |
|---|---|---|---|
| Fix CI/CD Pipeline Flow session, launched manually by the human from the GitLab UI | [pipeline 2985662569](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985662569) | 2026-10-24 23:46 | Ran as the service account `duo-fix-ci-cd-pipeline-gitlab-ai-hackathon` (user id 33073387). Pipeline source `duo_workflow`, one job `workload`, status success, 79 s (API). The flow's decision was `add_comment`, as read by the human in the session; it made no commits. The API showed no merge request, branch or commit from it |

## Deterministic checks run locally against the public API (read-only)

| What ran | Date (GMT-3) | Result |
|---|---|---|
| `scripts.merge_guard` decision for the open merge request !13, with `AFAW_AUTO_MERGE` unset, once with `AFAW_BOT_USER_IDS` empty and once with `33073387` | 2026-10-24 23:50 | Both runs: `merge: yes`, 0 automatic fix attempts (cap 3), nothing merged. !13 is authored by a human; this shows the rule runs against real data, not a Duo merge request |
| `GET /users?username=duo-fix-ci-cd-pipeline-gitlab-ai-hackathon&humans=true` (the lookup used by `scripts.human_only_files`) | 2026-10-24 23:50 | Empty list, so the service account counts as non-human even without `AFAW_BOT_USER_IDS`. The same lookup for `agustindiazcano` returns id 43344247 |

## Merge requests merged on 2026-10-25

Read from the public GitLab API on 2026-10-25. All six were merged by a person
(`agustindiazcano`); the pipeline of each branch had status success when the last check ran.

| Merge request | Merged (UTC) | What it brought |
|---|---|---|
| [!20](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/20) | 16:58 | Verified tool set of the Duo agents (task_038) |
| [!21](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/21) | 16:58 | Identity rule by commit author and pipeline user (task_044) |
| [!23](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/23) | 16:59 | Mutmut adapter and engine (task_046) |
| [!25](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/25) | 16:59 | `src/afaw_web` as a critical path, minimum 60 (task_048). Merged before !24, which the planned order did not allow |
| [!24](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/24) | 17:30 | The `mutation_gate` job runs mutmut (task_047) |
| [!22](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/22) | 17:30 | Triage flow, its tool lists and the autohealing design (task_045) |

None of these ran a Duo flow: they were written and merged by a person and an agent in a local
session. They add no link to the hands-off table below. The `mutation_gate` job has not yet been
observed on a change to `src/afaw_web`.

## Not yet observed

| Item | State |
|---|---|
| A merge request or commits authored by a Duo flow service account | None seen yet |
| Developer Flow session, Code Review Flow session | None seen yet |
| Automatic merge by `merge_guard` | Off (`AFAW_AUTO_MERGE` is not set); no merge request has been merged by it |
| GitLab Credits used | To be filled by the human from the GitLab UI |

## Hands-off loop, link by link

Nothing is marked Hands-off. Each link says whether it ran, with the link, the date (GMT-3) and the
result, read from the public GitLab API on 2026-10-25. A link that did not run says so. The
decision between Hands-off and Supervised is made from this table.

| Link | Ran | Evidence | Date | Result |
|---|---|---|---|---|
| A person creates the issue | Ran | Issues #2, #3, #4, #5 | 2026-10-25 | By design a person's step |
| The Developer Flow starts | Ran, started by a person | Pipelines [2985781520](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985781520), [2985787398](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985787398), [2985790337](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985790337), [2985792243](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985792243) | 2026-10-25 00:37 to 00:39 | Four sessions as `duo-developer-gitlab-ai-hackathon` (id 33073386), success, 106 to 151 s. How each was started (assign or mention) is not recorded. Issue #4 has no merge request |
| It opens a merge request | Ran | [!16](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/16), [!17](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/17), [!18](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/18) | 2026-10-25 00:39 to 00:41 | Draft. Author of each is a person (composite identity); commits are authored by the service account. !19, a duplicate of !16, was closed by a person |
| The Draft state is cleared | Not run | | | No merge request of the flow has left Draft |
| The pipeline gates judge the merge request | Ran | Pipelines [2985793535](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985793535) (!16), [2985796808](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985796808) (!17), [2985796985](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985796985) (!18) | 2026-10-25 | 20 jobs each, all success. On !16, `red_check`: 5 added tests failed on the old code; `human_only_files`: no human-only file changed |
| The gates stop broken code | Ran | Branches `demo/task-028-lint-failure` ([2985688766](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985688766)) and `demo/task-029-red-check-rejection` ([2985689849](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985689849)) | 2026-10-25 | The first failed only `lint`; the second failed only `red_check` |
| `merge_guard` gives a verdict | Ran, read only | Job `merge_guard` of 2985793535 | 2026-10-25 | `merge: no`, one reason: the merge request is a draft; 0 of 3 fix attempts |
| Automatic review | Not run | | | The merge requests are drafts and no trigger exists |
| A failed pipeline opens an issue | Not run | | | The triage flow and the triggers do not exist yet ([`docs/autohealing.md`](../autohealing.md)) |
| Fix CI/CD Pipeline Flow | Ran once, by hand | Pipeline [2985662569](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985662569) | 2026-10-24 23:46 | Launched by a person; decision `add_comment`, no commits. Not started by a trigger |
| Merge when the gates are green | Not run | | | `AFAW_AUTO_MERGE` is not set; every merge so far was a person's. `merge_guard` (task 012) merges through the API in continuous deployment mode and has never run it on a real merge request. Duo has no merge tool, but the merge does not depend on Duo |
| Release, deploy, monitor | Ran after a person's merge | Pipeline [2985700049](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985700049) on `main` | 2026-10-25 00:10 | 18 jobs success, including `deploy_cloud_run`, `monitor` and `monitor_live` |
| Summary comment on the issue | Not run | | | No documented event after a merge can start it. A deterministic CI job with a project access token could post it ([`docs/duo.md`](../duo.md)); not built |

