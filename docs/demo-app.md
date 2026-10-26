# The demo notes app

`src/notes_app` is a small FastAPI app, deployed on its own Cloud Run service (`afaw-demo-app`).
It is the target of the hands-off loop: the dashboard (`afaw-handsoff`) shows the project, and this
app is the product the agents work on. A reader can open it, see a change an agent made, and check
the commit it runs.

| Item | Value |
|---|---|
| Source | `src/notes_app/` (`app.py`, `main.py`, `Dockerfile`, `requirements.txt`) |
| Tests | `tests/notes/` (run in the `tests` job; mutation is not mandatory for it) |
| Endpoints | `GET /` (page), `GET /health`, `GET /api/version`, `GET /api/notes`, `POST /api/notes`, `DELETE /api/notes` (clear all), `DELETE /api/notes/{note_id}` (one note) |
| Limits | Text of 1 to 200 characters after trimming; at most 100 notes; extra fields rejected with 422 |
| Storage | In memory, per instance. The service scales to zero, so notes are lost; the page says so |
| Infrastructure | `deploy/terraform/cloud_run.tf` (`google_cloud_run_v2_service.demo`), same limits as the dashboard service |
| Pipeline | `package_demo_app`, `publish_demo_image`, `deploy_demo_app` (the last two on `main` only) |
| Proof of the commit | `deploy_demo_app` fails unless `/api/version` of the live service reports `$CI_COMMIT_SHA` |
| URL for other jobs | `deploy_demo_app` exports `DEMO_APP_URL` in a dotenv report |

## What it is for

* Demo issues ask the Developer Flow for features and fixes here (a delete button, a search box, a
  wrong colour). The merge request goes through the same gates as any other, `merge_guard` merges
  it, and the pipeline of `main` deploys it.
* The end to end tests (Playwright, planned in [`PENDING.md`](../PENDING.md)) open the live app. A
  visible defect (a button that does nothing, a wrong result, a wrong colour) fails the test, the
  failure becomes an issue, Duo repairs it, the fix is deployed, and the same test passes again.
* Nothing in it is secret and it makes no paid call.

## First deploy (human step)

The Terraform that creates the service is applied by a person; see
[`google-cloud.md`](google-cloud.md). The first image is a placeholder; the next pipeline of `main`
replaces it with the app.
