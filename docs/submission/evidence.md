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

## Not yet observed

| Item | State |
|---|---|
| A merge request or commits authored by a Duo flow service account | None seen yet |
| Developer Flow session, Code Review Flow session | None seen yet |
| Automatic merge by `merge_guard` | Off (`AFAW_AUTO_MERGE` is not set); no merge request has been merged by it |
| GitLab Credits used | To be filled by the human from the GitLab UI |
