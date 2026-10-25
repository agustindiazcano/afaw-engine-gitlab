# Devpost text

Facts checked on 2026-10-25. Text in angle brackets is to fill when it exists. Remove a sentence
rather than keep it if its condition is not true when you submit.

## Title

AFAW Engine: deterministic governance for AI coding agents

## Tagline

Agents write and repair code; deterministic GitLab CI jobs decide whether a change is acceptable.

## What it does

AFAW Engine is a GitLab project that wraps AI coding agents in checks that cannot be argued with.
A merge request goes through a pipeline with nine stages and 26 jobs. A new test must fail on the
old code (`red_check`), changed files are mutated and the tests must notice (`mutation_gate`),
SAST and secret detection reports are turned into a blocking decision (`security_gate`), and a
backup job rejects changes to the files that define the rules when a non-human made them
(`human_only_files`, a weak control that is documented as weak). The measured facts of every task
(first green time, merge time, pipelines, job minutes, retries) are read from the GitLab REST API
v4 and never declared by an agent. A read-only FastAPI service publishes the derived project state.

The merge policy is the point of the project: the human approves the policy once, and the
deterministic engine approves each merge. Task 012 adds a job that counts automatic fix attempts
per merge request, with a cap of three, and a merge rule that holds the merge for any open
question. It merges nothing unless a person turns it on.

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
| create | `task_delta`, `derived_views`, `web_data` | Merge requests; Duo review rules in `.gitlab/duo/` |
| verify | `lint`, `typecheck`, `tests`, `red_check`, `mutation_gate` | `rules`, pipeline cache, parallel jobs |
| secure | `semgrep-sast`, `secret_detection`, `security_gate` | GitLab SAST and secret detection templates |
| govern | `paper_pdf`, `equivalent_mutants_report`, `human_only_files` | Merge request author and pusher identity from the API |
| package | `package_docker` (Buildah as fallback) | Container Registry |
| configure | `check_configuration`, `terraform_validate` | Protected CI/CD variables |
| release | `release`, `publish_image`, `deploy_cloud_run` | `release:` keyword with `glab`; `id_tokens` and Workload Identity Federation |
| monitor | `monitor`, `monitor_live` | Job artifacts; REST API v4 |

GitLab Duo Agent Platform: the repository contains the sandbox configuration
(`.gitlab/duo/agent-config.yml`), the review instructions for the Code Review Flow, a workspace
subagent, and the sources of one custom agent and one custom flow (`duo/`). Their keys, tools and
limits are checked in CI against what docs.gitlab.com documents. <State here, from the project, how
many Duo sessions ran and what they produced. If none ran, write: "The flows are configured; the
first session is pending.">

## Google Cloud

Terraform in `deploy/terraform` creates a Cloud Run service (minimum 0, maximum 2 instances), an
Artifact Registry repository and a Workload Identity Federation pool for GitLab, with no service
account keys. Deployed on Oct 24, 2026 and running at https://afaw-handsoff-ljm5hefnsq-uc.a.run.app; the pipeline of `main` deploys it with Workload Identity Federation.

## What we measured

The collector read the GitLab API for the merge requests of this project on 2026-10-24. For task
011 it reported 4 pipelines, 75 jobs, 76 job minutes (each job rounded up to a whole minute, from
the durations GitLab reports) and 0 retries. These are captured values, not a claim of savings.
We make no statement about speed, cost or carbon: the Software Carbon Intensity experiment is not
done, and nothing in the project says otherwise.

## Challenges

- Fail loudly: a job that cannot get what it needs must be red, not green. `main` stayed red
  until a person applied the Terraform and set the Google Cloud variables, on purpose; those red
  pipelines are in the history.
- Honest controls: the job that protects the human-only files lives in `.gitlab-ci.yml`, so the
  same merge request can edit it away. It is labelled weak. The strong control (a pipeline
  execution policy or code owner approval) depends on the role and tier.
- GitLab documents no cap on Fix CI/CD Pipeline attempts, so the cap is counted by our own job.
- Some GitLab APIs answer only to a signed-in user; the identity check uses the endpoint that
  works without one and fails closed when it cannot decide.

## What is not done

- Duo flow sessions: <fill>.
- Automatic merge: written and tested, off by default, never run against a real merge request.
- The strong control for human-only files and the Maintainer settings listed in `docs/merge-guard.md`.
- The sustainability experiment (SCI).

## Built with

Python, pytest, mypy, ruff, FastAPI, Docker, Terraform, GitLab CI/CD, GitLab Duo Agent Platform,
GitLab Container Registry, Google Cloud Run, Artifact Registry, Workload Identity Federation.

## Links

Project: https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase ·
Original MIT project: https://github.com/agustindiazcano/afaw-anti-fragile-agentic-workflow ·
Demo video: <DEMO_VIDEO_URL> · Live service: https://afaw-handsoff-ljm5hefnsq-uc.a.run.app
