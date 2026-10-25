# Demo script (under 3 minutes)

Rule for the recording: show only what ran. Every segment below names the page or command and the
text that must appear on screen. If a segment's condition is not met when you record, cut the
segment; do not narrate around it. Total target: 2 minutes 50 seconds.

Prepare before recording: a terminal in the repository root, `build/facts.json` deleted, a browser
signed out of GitLab (the project is public, so everything below is visible without a login).

| Time | Show | Say (one sentence) |
|---|---|---|
| 0:00 to 0:15 | The README top: https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase | "Agents write code; deterministic tools decide if it is acceptable. Every number comes from a tool, never from an agent." |
| 0:15 to 0:50 | **Build > Pipelines**, open the green merge request pipeline https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985416324 and scroll the stage columns | "One pipeline, nine stages, a real job in each: plan, create, verify, secure, govern, package, configure, release, monitor." |
| 0:50 to 1:15 | In that pipeline open the `red_check` job log. The last lines read `OK: N added tests failed on the old code.` | "A new test must fail on the old code. A test that passes on both proves nothing, so the pipeline rejects it." |
| 1:15 to 1:40 | Open https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985441455 (pipeline on `main`). `check_configuration` and `publish_image` are red; `deploy_cloud_run`, `monitor` and `monitor_live` are skipped | "A job that cannot measure what it needs fails loudly. This one is red because the Google Cloud variables were not set yet." Cut this segment if `main` is already green; keep the pipeline link in the description instead |
| 1:40 to 2:10 | Terminal: `CI_API_V4_URL=https://gitlab.com/api/v4 CI_PROJECT_ID=88052530 python -m scripts.collect_facts --ref origin/main --out build/facts.json` then `python -c "import json; print(json.dumps(json.load(open('build/facts.json'))['task_011'], indent=1))"`. Fields on screen: `merged_at`, `ci_status`, `ci.pipelines`, `ci.jobs`, `ci.job_minutes`, `ci.retries` | "Timestamps, pipelines, job minutes and retries are read from the GitLab API for every merge request. Nothing is declared by an agent." |
| 2:10 to 2:30 | Terminal: `CI_API_V4_URL=https://gitlab.com/api/v4 CI_PROJECT_ID=88052530 CI_DEFAULT_BRANCH=main python -m scripts.merge_guard --mr 6`. On screen: `merge: no`, `- merge request is not open`, `automatic fix attempts: 0 (cap 3)`. Only after task 012 is merged | "The merge rule and the cap of three automatic fix attempts are code, not a prompt. It merges only when every gate is green, and only when a person turns it on." |
| 2:30 to 2:50 | If deployed: the Cloud Run URL, `/health` returns `{"status":"ok"}`, then `/api/state`. If not deployed: terminal `PYTHONPATH=src AFAW_WEB_DATA_DIR=build/web-data python -m uvicorn afaw_web.main:app --port 8080` (setup in the README) and `http://localhost:8080/health` | "A read-only service shows the derived project state. It runs on Cloud Run." Say "runs locally" if it is not deployed |

## Segments that depend on something that has not run

| Segment | Condition to include it | If the condition is false |
|---|---|---|
| A Duo flow producing a merge request or fixing a pipeline | A real session exists: a merge request or commits authored by a flow service account, visible in the project | Do not show or mention a flow as working. Say once: "Duo flows are configured in the repository; the first session is still to run." The hackathon requires using Duo, so run at least one session before submitting |
| The live Cloud Run URL | Met on Oct 24, 2026: `terraform apply` done, the `GCP_*` variables set, a green `deploy_cloud_run` and `monitor_live` on `main` (pipeline 2985631519). Check `/health` again right before recording | Use the local run above |
| The merge guard line | Task 012 merged to `main` | Cut it |

## Check before you publish

- Every number you say is on screen and was produced in the recording.
- No third-party trademark or copyrighted music (hackathon rule).
- The video is on YouTube and under 3 minutes.
