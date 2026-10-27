# Devpost text

Facts read on 2026-10-26 from the GitLab API and [`evidence.md`](evidence.md); every figure has its
source in [`experiments.md`](../experiments.md). Text in angle brackets is filled when it exists.
Remove a sentence rather than keep it if its condition is not true when you submit.

## Title

AFAW Engine: hands-off CI/CD for AI coding agents

## Tagline

An agent fixes a failing check, a program decides and performs the merge, Cloud Run redeploys and a browser test verifies the live app.

## What it does

AFAW Engine is a GitLab project that closes the loop after the code is written. When a check fails,
`request_fix` opens an issue and a GitLab Duo agent repairs it. When every gate is green,
`merge_guard` takes the merge request of a Duo service account out of Draft and merges it. The
pipeline of `main` releases and deploys to Google Cloud Run, and Playwright tests the live app
(`e2e_live`). An orchestrator script picks the next task from the project board and files its issue
with a fixed template, so no model chooses the work.

Around that loop, the checks are code that the agents cannot edit away: a new test must fail on the
old code (`red_check`), changed files are mutated and the tests must notice (`mutation_gate`), SAST
and secret detection become a blocking decision (`security_gate`), and the files that define the
rules cannot be changed by a service account (`human_only_files`). Every number comes from a tool
or the GitLab API, never from an agent.

## The problem

Several agents on one repository collide on branches and shared files, report results they never
measured, and write tests that pass whatever the code does. When generating code is cheap, the open
problem is what comes after it: review, security, tests, release and monitoring. A prompt that says
"do not weaken the gates" is advice. The gates have to be code.

## How GitLab and Duo are used

| Stage | What runs | A Duo-authored merge request through the pipeline |
|---|---|---|
| plan | `task_files`, `docs_check`, `duo_config` | [!79](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/79) |
| create | `task_delta`, `derived_views`, `web_data` | [!26](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/26) |
| verify | `lint`, `typecheck`, `tests`, `red_check`, `mutation_gate`, `e2e_local` | [!47](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/47) |
| secure | `semgrep-sast`, `secret_detection`, `security_gate` | [!77](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/77) |
| govern | `paper_pdf`, `human_only_files`, `repair_check` | [!78](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/78) |
| package | `package_docker`, `package_demo_app` | [!75](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/75) |
| configure | `check_configuration`, `terraform_validate` | [!76](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/76) |
| release | `release`, `deploy_cloud_run`, `deploy_demo_app`, `e2e_live` | [!80](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/80) |
| monitor | `monitor_live`, `merge_guard`, `request_fix`, `telemetry_report` | [!81](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/81) |

GitLab Duo Agent Platform pieces in the project (the list with service accounts is in the README):

| Piece | What ran |
|---|---|
| Developer Flow | Dozens of sessions from issues; three tools written in parallel reached a merge request in 2 to 4 minutes |
| Fix CI/CD Pipeline Flow | Once by hand, then by a trigger on failed pipelines: it opened a repair 1 min 43 s after a planted failure, in parallel with the Developer Flow, so the trigger is kept off outside a demonstration |
| Code Review Flow | Three rounds on one merge request, ending in an approval |
| Custom flow "AFAW loop reporter" | Once: a summary note on a merge request and its issue in 1 min 23 s |
| Custom agents "AFAW auditor" and "AFAW planner" | Created; not run |

## What ran, link by link

| Link | Result |
|---|---|
| Orchestrator files an issue and assigns it to Duo | Issue #61, in the rehearsal below |
| Duo opens a merge request | 3 min 15 s after the issue in the rehearsal |
| Gates judge it | `red_check`, `mutation_gate`, `security_gate`, `e2e_local` and the rest |
| Draft cleared and merge requested by `merge_guard` | 30 merge requests made only by agents, with the token of a person (`AFAW_MERGE_TOKEN`), so GitLab shows that person's name on the notes |
| Release, deploy to Cloud Run, live check | Ran after the automatic merge; `e2e_live` passed |
| A failed live check becomes an issue and Duo repairs it | Three planted bugs found by a browser test and fixed by one Duo session: 23 min 44 s from issue to verified app |

The whole loop, once, from the orchestrator command: 25 min 19 s from the issue to the verified live
app, 6.86 GitLab Credits and 0.55 to 5.57 gCO2eq (SCI without embodied emissions and without the
energy of the model behind Duo).

We do not claim that no person is involved: the token of a person takes the merge request out of
Draft and requests the merge, a person starts the first command, the Code Review Flow and the summary
note, and a person writes the rules.

## Google Cloud

Terraform in `deploy/terraform` creates two Cloud Run services (the dashboard and the demo app that
the agents change), an Artifact Registry repository and a Workload Identity Federation pool for
GitLab, with no service account keys. The pipeline of `main` deploys both and the live checks prove
the commit that is running. Dashboard: https://afaw-handsoff-ljm5hefnsq-uc.a.run.app · Demo app:
https://afaw-demo-app-ljm5hefnsq-uc.a.run.app.

## What we measured

| Measure | Result |
|---|---|
| Merge requests / made only by agents / merged / with a recorded automatic merge | 132 / 47 / 36 / 30 (2026-10-26); median 10.5 minutes from open to merge |
| Hidden acceptance tests on three tools Duo built | 39 of 39 passed |
| Planted defects repaired with no test touched | 6 of 6, plus 1 real defect Duo found |
| Chaos | C1, C2, C3, C5, C6, C7 and a security case held |
| Long chain | Three dependent tasks filed one after another by the orchestrator: each reached a verified live app in 24 to 28 minutes, 1 h 18 min 23 s in total, no repair request |
| Mutation score, `app.py` / `search.py` | 62.2 to 95.6 / 78.0 to 84.7 percent |
| Carbon of one development flow | 0.45 to 4.53 gCO2eq over 30 merge requests, stated assumptions |
| GitLab Credits used | 412.91 of 500 (read by hand); GitLab exposes no token counts |

Nothing here is a claim of savings in speed or money.

## Challenges

- Fail loudly: a job that cannot get what it needs must be red, not green.
- Parallel agents picked the same task id several times; the pipeline caught it every time and does
  not prevent it.
- Seven merges within a minute made parallel deploys overwrite each other; a deploy lock fixed it.
- A repair of a planted branch inherits the planted task file and fails a check of its own, which
  starts a chain of issues; the cap of six open issues stops it.
- `human_only_files` lives in `.gitlab-ci.yml`, so the same merge request can edit it away. It is
  labelled weak.

## What is not done

- The merge and the end of Draft use the token of a person. A service account token needs an Owner.
- A repair that needs more than one attempt has not happened.
- Chaos faults C4 (covered by unit tests, not run live), C8 and C9; the comparison against reading
  the code is not measured, so the sustainability result is a measured cost, not a saving.
- The custom agents AFAW auditor and AFAW planner were created and not run.

## Built with

Python, FastAPI, pytest, mypy, ruff, mutmut, Playwright, Docker, Terraform, GitLab CI/CD, GitLab Duo
Agent Platform, GitLab Container Registry, Google Cloud Run, Artifact Registry, Workload Identity
Federation, Semgrep.

## Links

Project: https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase ·
GitHub mirror: https://github.com/agustindiazcano/afaw-engine-gitlab ·
Original MIT project: https://github.com/agustindiazcano/afaw-anti-fragile-agentic-workflow ·
Demo video: https://youtu.be/42C2ZQdyujw · Dashboard: https://afaw-handsoff-ljm5hefnsq-uc.a.run.app ·
Author: Agustin Diaz-Cano, https://www.agustindiazcano.com/
