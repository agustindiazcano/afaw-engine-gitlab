# Path B: what was added or changed since Oct 5, 2026

Original project (MIT): https://github.com/agustindiazcano/afaw-anti-fragile-agentic-workflow.
Its base method (task files, derived state, red-first check, mutation gate, rules in `AGENTS.md`)
was committed on Sep 29 and 30, 2026. This project is a variant of it for the GitLab Transcend
Hackathon. Everything below is in the history of the GitLab project; the numbers are merge
request numbers and release tags of that project, read on 2026-10-25.

| Date | Change | Evidence | State |
|---|---|---|---|
| Oct 23 | English-only rule and the first GitLab Duo rules in `AGENTS.md` | Commit `8f29bb3` | Merged |
| Oct 23 | Test suite passes on Windows (task 007) | Commit `2f696fe`, MR !1 | Merged |
| Oct 24 | Repository imported into the GitLab project | MR !2 | Merged |
| Oct 24 | Merge policy: the human approves the policy, the engine approves each merge (ADR 0007, task 008) | MR !3 | Merged; the ADR is `proposed` until the human accepts it |
| Oct 24 | Nine-stage `.gitlab-ci.yml`, security gate, `human_only_files` weak control (task 009) | MR !4, release v0.9 | Merged |
| Oct 24 | Read-only FastAPI service, Dockerfile, Terraform for Cloud Run and Workload Identity Federation, deploy jobs (task 013) | MR !5, release v0.15 | Merged; not deployed until a person applies the Terraform and sets the variables |
| Oct 24 | Duo configuration, custom agent and custom flow sources, `duo_config` check (task 011) | MR !6, release v0.20 | Merged; the flows must be enabled in the GitLab UI by a person |
| Oct 25 | Facts from the GitLab REST API v4: merge requests, pipelines, jobs, retries, job minutes; GitHub kept working (task 010) | MR !7, release v0.23 | Merged |
| Oct 25 | Fix-attempt cap and automatic merge rule, off by default (task 012) | Branch `feat/task-012-merge-guardrails` | In review: <MR number and tag when merged> |
| Oct 25 | README validated against the repository (task 016) | Branch `docs/readme-validated` | In review: <MR number when merged> |
| Oct 25 | Demo script, Devpost text, this page (task 014) | Branch `docs/task-014-submission` | In review |

## What is deliberately not claimed

- No Duo flow session is claimed until one exists in the project history.
- No savings in time, cost or carbon is claimed; the SCI experiment (task 015) is not done.
- The Cloud Run service is not described as live until `deploy_cloud_run` and `monitor_live` are
  green on `main`.
