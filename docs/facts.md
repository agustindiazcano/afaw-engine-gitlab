# Measured facts

`python -m scripts.collect_facts` writes `build/facts.json`: the facts of each task, measured from git and from the forge API. Nothing in it is declared by an agent. `build_state --facts` reads it to derive the traffic light, the durations and the CI cost.

## Choosing the forge

The forge is chosen by environment and never guessed.

| Environment | Forge |
|---|---|
| `CI_API_V4_URL` and `CI_PROJECT_ID` (GitLab CI sets both) | GitLab REST API v4; optional `GITLAB_TOKEN` for a private project |
| `GITHUB_REPOSITORY` (and `GITHUB_TOKEN`) | GitHub REST API |
| Neither, only one of the GitLab pair, or both forges | Exit code 1 with the reason; no file is written |

## GitLab: what is read

| Endpoint | Used for |
|---|---|
| `GET /projects/:id/merge_requests?source_branch=…&state=all` | The merge request of the task (the latest one if the branch had several) |
| `GET /merge_requests/:iid/commits` | `started_at` and the last commit |
| `GET /merge_requests/:iid/pipelines` and `GET /pipelines?ref=<branch>` | The pipelines, joined by id (the second one also lists the pipelines run before the merge request was opened) |
| `GET /pipelines/:id/jobs?include_retried=true` | Durations, queue time and retried jobs |

Every request has a 30 s timeout. A 429, a 5xx or a network error is retried with exponential backoff (1 s, 2 s, 4 s, four attempts); any other error stops the collection. A list is read in pages of 100 up to 10 pages; a longer list is an error, never a silent truncation. Facts of a merged task are final and are reused from the previous `facts.json` when it exists.

### Authentication (verified on docs.gitlab.com, 2026-10-24)

The project is public, so these reads need no token, and CI sends none. The CI/CD job token page lists the endpoints a `CI_JOB_TOKEN` can call: the merge request list and the single merge request are on it; the merge request commits, the merge request pipelines, the pipeline list and the pipeline jobs are not. The Jobs API entry covers only `GET /job`. So the job token is not relied on. The pipeline jobs page does not say whether `JOB-TOKEN` is accepted. Job logs need a session and are not read. Unauthenticated requests are limited per IP (500 per minute was returned in the `RateLimit-Limit` header on 2026-10-24); the backoff covers a 429.

## Fields per task

The fields of `pr_facts` and `ci_facts` (GitHub) are kept: `pr_url`, `pr_opened_at`, `merged_at`, `started_at`, `first_green_at`, `ci_status`, `last_activity_at` and `ci` with `runs`, `failed_runs`, `jobs`, `queue_seconds`, `job_minutes`. On GitLab a pipeline is a run. `ci_status` is `failure` when a pipeline of the latest commit failed or was canceled, because nothing is running and it is not green.

GitLab adds, for the sustainability experiment (task 015):

| Key under `ci` | Definition |
|---|---|
| `job_seconds` | Sum of the `duration` GitLab reports for each job that started |
| `job_minutes` | The same durations with each job rounded up to a whole minute. It is not claimed to equal what GitLab bills |
| `missing_durations` | Jobs that started and report no duration |
| `pipelines` | Every pipeline listed for the merge request or the branch |
| `retried_jobs` | Jobs that ran again with the same name in the same pipeline (counts beyond the first) |
| `pipeline_retries` | Pipelines beyond the first for the same commit and the same source. A push of a new commit is new work, not a retry |
| `retries` | `retried_jobs` + `pipeline_retries` |

A value that is missing is `null` and is counted in `missing_durations`; it is never zero. If a started job has no duration, `job_seconds` and `job_minutes` are `null`, and `build_state` treats the CI cost of that task as not measured. A job that never started (skipped, manual, created) has no duration and is not missing.

## Not covered

- The data was checked only against merge requests with no retried job; the retry counts are tested on constructed payloads and must be confirmed on the first real retry in the history.
- `queue_seconds` is the `queued_duration` GitLab reports, so it excludes time before the job was created.
