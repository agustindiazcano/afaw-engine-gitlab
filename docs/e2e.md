# End to end tests (Playwright)

A real browser opens the apps the way a visitor does. A failure here is a defect a user would see,
so it feeds the repair loop: the failed job opens an issue for Duo through `request_fix`.

| Item | Value |
|---|---|
| Tests | `e2e/test_notes_app.py` (demo app), `e2e/test_dashboard.py` (dashboard) |
| Tool | Python Playwright 1.64.1, Chromium; image `mcr.microsoft.com/playwright/python:v1.64.1-noble` (the tag was read from `mcr.microsoft.com`; the pin in `e2e/requirements.txt` must equal it, and a test checks that) |
| Variables | `NOTES_URL`, `DASHBOARD_URL`; a test skips when its variable is unset |
| Artifacts | `e2e-results/` with screenshots, kept one week |

## Jobs

| Job | Stage | When | Against |
|---|---|---|---|
| `e2e_local` | verify | Merge request that changes `src/notes_app/` or `e2e/`, and `main` | The demo app started inside the job (uvicorn on port 8000) |
| `e2e_live` | release | `main`, after `deploy_cloud_run` and `deploy_demo_app` | The live demo app and the live dashboard |

`e2e_live` is in the release stage on purpose: `request_fix` reacts to failures of earlier stages,
so a live test placed in monitor would never reach it.

## What is checked

| Kind | Test |
|---|---|
| Behaviour, demo app | A note typed in the page appears in the list; a blank note is not added; the page shows the release and the commit |
| Appearance, demo app | The Add button has the brand background (`rgb(11, 95, 255)`) and white text, read from the computed style |
| Behaviour, dashboard | Experiments opens from the navigation and draws at least three charts; the demo page says its data is invented; the live panel fills in within ten seconds |

The appearance check compares computed colours, not pixels: a screenshot baseline made in another
container differs by fonts and anti-aliasing, so it would fail with no defect. Screenshots are saved
for a person to read.

## The repair loop on a visible defect

1. A change breaks a button, a result or a colour; the pipeline of `main` deploys it.
2. `e2e_live` fails; `request_fix` opens an issue labelled `afaw-autoheal` for the Developer Flow.
3. Duo opens a merge request; the gates run; `merge_guard` merges it.
4. The next pipeline deploys the fix and `e2e_live` runs again; it passes.

Measured runs of this loop are recorded in [`experiments.md`](experiments.md) with their links.

## Run it locally

```
pip install -r e2e/requirements.txt -r src/notes_app/requirements.txt
playwright install chromium
PYTHONPATH=src python -m uvicorn notes_app.main:app --port 8000 &
NOTES_URL=http://127.0.0.1:8000 python -m pytest e2e/test_notes_app.py
```
