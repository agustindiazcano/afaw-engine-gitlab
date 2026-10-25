# Path B: what was added or changed since Oct 5, 2026

Original project (MIT): https://github.com/agustindiazcano/afaw-anti-fragile-agentic-workflow.
Its base method (task files, derived state, red-first check, mutation gate, rules in `AGENTS.md`)
was committed on Sep 29 and 30, 2026. This project is a variant of it for the GitLab Transcend
Hackathon. Everything below is in the history of the GitLab project; the numbers are merge
request numbers and release tags of that project, read on 2026-10-24 (GMT-3).

| Date | Change | Evidence | State |
|---|---|---|---|
| Oct 23 | English-only rule and the first GitLab Duo rules in `AGENTS.md` | Commit `8f29bb3` | Merged |
| Oct 23 | Test suite passes on Windows (task 007) | Commit `2f696fe`, MR !1 | Merged |
| Oct 24 | Repository imported into the GitLab project | MR !2 | Merged |
| Oct 24 | Merge policy: the human approves the policy, the engine approves each merge (ADR 0007, task 008) | MR !3 | Merged; the ADR is `proposed` until the human accepts it |
| Oct 24 | Nine-stage `.gitlab-ci.yml`, security gate, `human_only_files` weak control (task 009) | MR !4, release v0.9 | Merged |
| Oct 24 | Read-only FastAPI service, Dockerfile, Terraform for Cloud Run and Workload Identity Federation, deploy jobs (task 013) | MR !5, release v0.15 | Done: a person applied the Terraform and set the variables, and the pipeline of `main` deployed it (pipeline 2985631519) |
| Oct 24 | Duo configuration, custom agent and custom flow sources, `duo_config` check (task 011) | MR !6, release v0.20 | Merged; the flows must be enabled in the GitLab UI by a person |
| Oct 24 | Facts from the GitLab REST API v4: merge requests, pipelines, jobs, retries, job minutes; GitHub kept working (task 010) | MR !7, release v0.23 | Merged |
| Oct 24 | Fix-attempt cap and automatic merge rule, off by default (task 012) | MR !10 | Merged; merges nothing unless a person sets `AFAW_AUTO_MERGE=true` |
| Oct 24 | README validated against the repository (task 016); demo script, Devpost text, this page (task 014) | MR !8 and later | Merged |
| Oct 25 | Developer Flow started by assigning an issue through the API: !16, !17, !18 | [evidence](evidence.md) | Ran; its merge requests are Draft |
| Oct 25 | `merge_guard` clears Draft and asks for the merge; `request_fix` turns a failed pipeline into a note or an issue | From !35 | Nine merges by the guard with a person's token; `request_fix` opened issues #15 and #19 to #23 |
| Oct 25 | Experiments: coverage, mutation score, hidden acceptance tests, planted defects, chaos, load | [`experiments.md`](../experiments.md) | Measured; some faults and experiments not run |
| Oct 25 | Dashboard with live GitLab panel, `/experiments/`, `/environment/`; mutmut as mutation engine | Listed in `evidence.md` | Merged and deployed |

## What is deliberately not claimed

- No automatic review by the Code Review Flow and no summary comment on the issue: neither ran.
- No repair that needed more than one attempt.
- No Hands-off for the whole loop: the token that clears Draft and enables the merge is a person's.
- No saving in time or money. The carbon figure is an estimate with its assumptions listed.
