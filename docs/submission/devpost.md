# Devpost text

Facts checked on 2026-10-25 against the GitLab API and `docs/submission/evidence.md`. Text in angle
brackets is to fill when it exists. Remove a sentence rather than keep it if its condition is not
true when you submit.

## Title

AFAW Engine: deterministic governance for AI coding agents

## Tagline

Agents write and repair code; deterministic GitLab CI jobs decide whether a change is acceptable and merge it.

## What it does

AFAW Engine is a GitLab project that wraps AI coding agents in checks that cannot be argued with.
`.gitlab-ci.yml` defines 29 jobs in nine stages, plus the jobs of the GitLab SAST and secret
detection templates. A new test must fail on the old code (`red_check`), changed files are mutated
and the tests must notice (`mutation_gate`), SAST and secret detection reports become a blocking
decision (`security_gate`), and a backup job rejects changes to the files that define the rules when
a non-human made them (`human_only_files`, a weak control that is documented as weak). The measured
facts of every task come from the GitLab REST API v4 and are never declared by an agent. A
read-only FastAPI service on Cloud Run publishes the derived project state, the experiments and an
estimate of the carbon footprint of the pipeline.

The merge policy is the point of the project: the human approves the policy once, and the
deterministic engine approves each merge. `merge_guard` merges nothing unless a person turns it on
(`AFAW_AUTO_MERGE=true`). With it on, it takes a merge request of a service account out of Draft
when that is the only thing holding it, and asks GitLab to merge it when every gate is green.
A second job, `request_fix`, turns a failed pipeline into a note or an issue that the Duo Developer
Flow account picks up.

## The problem

Several agents on one repository collide on branches and shared files, report results they never
measured, and write tests that pass whatever the code does. When generating code is cheap, the
open problem is what comes after it: review, security, tests, release and monitoring. A prompt
that says "do not weaken the gates" is advice. The gates have to be code that the loop cannot edit
away.

## How GitLab is used, stage by stage

| Stage | What runs | GitLab feature |
|---|---|---|
| plan | `task_files`, `docs_check`, `duo_config` | Merge request pipelines (`workflow:rules`) |
| create | `task_delta`, `derived_views`, `web_data` | Merge requests opened by the Developer Flow |
| verify | `lint`, `typecheck`, `tests`, `red_check`, `mutation_gate` | `rules`, pipeline cache, parallel jobs |
| secure | `semgrep-sast`, `secret_detection`, `security_gate` | GitLab SAST and secret detection templates |
| govern | `paper_pdf`, `paper_build`, `human_only_files`, `equivalent_mutants_report` | Merge request author and pusher identity from the API |
| package | `package_docker`, `package_buildah` (fallback) | Container Registry |
| configure | `check_configuration`, `terraform_validate` | Protected CI/CD variables |
| release | `release`, `publish_image`, `deploy_cloud_run` | `release:` keyword with `glab`; `id_tokens` and Workload Identity Federation |
| monitor | `monitor`, `monitor_live`, `merge_guard`, `request_fix` | Job artifacts; REST API v4 |

GitLab Duo Agent Platform: the Developer Flow, started by assigning an issue to its service
account through the API, opened merge requests that the pipeline then judged. The Fix CI/CD
Pipeline Flow ran once, started by a person, and only commented. A custom agent, "AFAW merge agent",
exists in the AI Catalog. The Code Review Flow never ran. <Update the session counts from the
project before submitting.>

## What ran, link by link

All of it is listed with links in [`evidence.md`](evidence.md).

| Link | Result |
|---|---|
| Issue assigned to the Duo account through the API | Developer Flow started with no click in the UI |
| Duo opens a merge request | Yes, as Draft |
| Gates judge it | Yes |
| Draft cleared and merge requested by `merge_guard` | Nine merge requests, with the token of a person (`AFAW_MERGE_TOKEN`), so GitLab shows that person's name on those notes |
| Release, deploy to Cloud Run, live check | Ran after the automatic merge |
| A failed pipeline becomes an issue (`request_fix`) | Yes, issues #15 and #19 to #23 |
| Duo repairs it | One real defect Duo found in `scripts/mutation_engine.py`, merged by the guard; planted defects repaired with a one-line inverse each |
| Review by the Code Review Flow, summary comment on the issue | Not run |

We do not claim Hands-off for the whole loop: the identity that clears Draft and enables the merge
is a person's token. The decision on the level is taken on 2026-10-26 from that table.

## Google Cloud

Terraform in `deploy/terraform` creates a Cloud Run service (minimum 0, maximum 2 instances), an
Artifact Registry repository and a Workload Identity Federation pool for GitLab, with no service
account keys. The pipeline of `main` deploys it and `monitor_live` proves the commit that is
running. Live at https://afaw-handsoff-ljm5hefnsq-uc.a.run.app.

## What we measured

Every figure is in [`docs/experiments.md`](../experiments.md) with its source.

| Measure | Result |
|---|---|
| Line and branch coverage | 86 to 94 percent after tests written by Duo |
| Mutation score, `app.py` / `search.py` | 62.2 to 95.6 / 78.0 to 84.7 percent (mutmut in CI) |
| Hidden acceptance tests on three tools Duo built | 39 of 39 passed |
| Planted defects repaired with no test touched | 6 of 6, plus 1 real defect Duo found |
| Chaos: C1, C3 and a security case | Held |
| Load test of the live service | 992 requests, no errors |
| GitLab Credits used | 219.38 of 500, read by hand on 2026-10-25; GitLab exposes no token counts |

Nothing here is a claim of savings in speed or money. The carbon figure is an estimate with its
assumptions listed on the `/environment/` page.

## Challenges

- Fail loudly: a job that cannot get what it needs must be red, not green.
- Honest controls: `human_only_files` lives in `.gitlab-ci.yml`, so the same merge request can edit
  it away. It is labelled weak. The strong control depends on the role and tier.
- GitLab documents no cap on Fix CI/CD Pipeline attempts, so the cap of three is counted by our own job.
- Our own experiments found two defects of ours (task_070, gotcha 0005).

## What is not done

- The Code Review Flow and the summary comment on the issue never ran.
- The merge uses a person's token. A service account token needs an Owner.
- The strong control for human-only files and the Maintainer settings in `docs/merge-guard.md`.
- Chaos faults C2 and C4 to C9 and parts of EXP-04, EXP-05 and EXP-09.

## Built with

Python, pytest, mypy, ruff, mutmut, FastAPI, Docker, Terraform, GitLab CI/CD, GitLab Duo Agent Platform,
GitLab Container Registry, Google Cloud Run, Artifact Registry, Workload Identity Federation.

## Links

Project: https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase ·
Original MIT project: https://github.com/agustindiazcano/afaw-anti-fragile-agentic-workflow ·
Demo video: <DEMO_VIDEO_URL> · Live service: https://afaw-handsoff-ljm5hefnsq-uc.a.run.app ·
Author: Agustin Diaz-Cano, https://www.agustindiazcano.com/
