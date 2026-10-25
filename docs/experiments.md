# Experiments, benchmarks and the data tables

Every experiment has an id, a question, how it is run, what is measured, and the pass rule that is
written before it runs. A cell that was not measured says `not run`; it is never filled with an
estimate (`AGENTS.md` section 2.2). Rows are added only after the experiment ran, with the link.

## What can be measured, and what cannot

| Quantity | Measurable | Source |
|---|---|---|
| Wall time of a link or of the loop | Yes | Timestamps of issue, merge request, pipelines and merge from the GitLab API |
| CI job seconds and minutes, retries | Yes | `python -m scripts.cost_log` reads the public API |
| GitLab Credits per Duo session | By hand | User Settings > GitLab Credits; GitLab documents no endpoint ([`cost-log.md`](submission/cost-log.md)) |
| LLM tokens per Duo session | **No** | GitLab Duo does not expose token counts; the unit is the credit |
| Money in USD | **Not stated** | The price of a credit is not recorded here; do not convert without a source |
| Energy and carbon of CI | Estimated with a stated method | SCI per [ADR 0009](adr/0009-measure-sustainability-with-sci.md): CI seconds, Cloud Carbon Footprint coefficients, regional grid intensity |
| Latency and errors of the live service | Yes | A load tool against `afaw-handsoff` and the Cloud Run metrics |
| Cloud Run cost | By hand | Google Cloud billing console |

## Catalog

| Id | Name | Question | Status |
|---|---|---|---|
| EXP-01 | Happy path | Does an issue become a merged and deployed change with no person? | Running: issue #6, !26 |
| EXP-02 | Autoheal, lint | Does a lint failure on a branch with no merge request produce an issue, a fix and a merge? | Not run: needs the triggers |
| EXP-03 | Autoheal, tests | Same, for a failing test caught by `red_check` | Not run |
| EXP-04 | Long chain | Four issues, one after the other: how many merge with no person, and how long does each take? | Not run |
| EXP-05 | Burst | Four issues assigned at once: do the merge requests collide, and how fast do credits burn? | Not run |
| EXP-06 | Chaos | Do the gates and the guard hold when things break on purpose? | Not run |
| EXP-07 | Service load | How does the live service behave under load, and what does it cost? | Not run |
| EXP-08 | Agent quality | How good are the Duo flows on standard small tasks? | Not run |
| EXP-10 | Real repair | Does Duo fix defects that real tests catch, with no test weakened? | Running: three planted defects |
| EXP-11 | Hard build, hidden tests | Can Duo build a non-trivial tool from a specification and pass tests it cannot see? | Running: issues #13 and #14 |
| EXP-12 | Test writing with a measured effect | Do the tests Duo writes raise coverage and the mutation score? | Coverage measured; mutation running |
| EXP-09 | Environmental benchmark | What is the SCI of one merged merge request, and what do the optimizations save? | Partly: one measured optimization, no SCI yet |

### EXP-01 Happy path

Issue #6 is assigned to the Developer Flow service account. Expected: a merge request, its gates,
the end of Draft, the merge, the release and the deploy.

| Link | Started by | Time (GMT-3) | Result | Link to evidence |
|---|---|---|---|---|
| Issue created by API | Human | not run | | [issue #6](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/work_items/6) |
| Developer Flow starts | Assignment through the API | 2026-10-25 | Started with no click in the UI; pipeline 2986935541, status success | [pipeline](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2986935541) |
| Merge request opened | The flow | 2026-10-25 | !26, Draft, three files | [!26](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/26) |
| Draft cleared | not run | | | |
| Gates | not run | | | |
| Merge by `merge_guard` | not run | | | |
| Release and deploy | not run | | | |

### EXP-06 Chaos: faults and the expected answer

| Id | Fault injected | Expected | Pass rule |
|---|---|---|---|
| C1 | A flow's commit edits `.gitlab-ci.yml` | `human_only_files` fails; no merge | Job red, no merge |
| C2 | A test with no assertions | `mutation_gate` fails below the minimum | Job red |
| C3 | A fix that never works | The cap of 3 stops it | `merge_guard` exit 1 after the third attempt |
| C4 | `AFAW_MERGE_TOKEN` invalid | Fails closed | Exit 2, nothing merged |
| C5 | `AFAW_BOT_USER_IDS` empty | Nothing merges | `merge: no` |
| C6 | A person's merge request | Never merged by the guard | `merge: no`, reason identity |
| C7 | Job killed mid-run | Pipeline red, retry recovers | Recorded |
| C8 | A flaky test | `red_check` and retries report it | Recorded |
| C9 | The deploy fails | `monitor` goes red; the old revision keeps serving | `/health` still 200 |

### EXP-07 Service load

Target: `https://afaw-handsoff-ljm5hefnsq-uc.a.run.app`, endpoints `/health`, `/api/state`,
`/api/ask`. The service has no rate limiting and at most two instances. Keep the run short and
small, because the traffic is billed.

| Run | Rate | Duration | p50 | p95 | Error rate | Instances | Cost |
|---|---|---|---|---|---|---|---|
| warm, `/health` | not run | | | | | | |
| cold start | not run | | | | | | |
| `/api/ask` | not run | | | | | | |

### EXP-08 Agent quality

Five small tasks of the same kind, fixed before the run. For each: first merge request passes the
gates, fix attempts, mutation score of the tests the flow wrote, wall time, credits.

| Task | Merge request | Passed gates first time | Fix attempts | Mutation score | Minutes | Credits |
|---|---|---|---|---|---|---|
| !16 `GET /api/version` | [!16](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/16) | Yes (20 jobs, all success) | 0 of 3 (`merge_guard` output) | not run | not run | by hand |
| !17 validate `q` | [!17](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/17) | Yes (20 jobs, all success) | not read | not run | not run | by hand |
| !18 duplicate names in CI config | [!18](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/18) | Yes (20 jobs, all success) | not read | not run | not run | by hand |
| issue #6 happy path | [!26](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/merge_requests/26) | not run | | | | |

### EXP-09 Environmental benchmark

Method: [ADR 0009](adr/0009-measure-sustainability-with-sci.md), SCI = (O + M) per R, with R =
one merged merge request. Inputs measured: CI job seconds per merge request. Inputs assumed and
declared: runner power draw, grid intensity (`us-central1` 432 gCO2eq/kWh in the ADR), embodied
emissions. No SCI figure is published until the assumptions are written next to it.

| Optimization or choice | Before | After | Measured | Source |
|---|---|---|---|---|
| Mutation tool in CI | cosmic-ray: 309 s for 77.1 % | mutmut: 56 s for 71.2 % | Yes, one run on the CI runner | [`mutation-tools-measurement.md`](submission/mutation-tools-measurement.md) |
| Path filters: documents-only changes skip tests | not run | not run | Not measured | `.gitlab-ci.yml` |
| Cloud Run scales to zero (`minScale` 0, `maxScale` 2) | not run | not run | Configuration only; no energy figure | `deploy/terraform/cloud_run.tf` |
| Region of the service | not run | not run | Not measured | |

| Merge request | Job seconds | Retries | Credits | E (kWh) | SCI (gCO2eq per MR) |
|---|---|---|---|---|---|
| !26 | not run | not run | by hand | not run | not run |

## Plan v2: real work, not toys

The first runs were small (a note file, one-line tests). Duo had used 59.67 of the 500 monthly
GitLab Credits (read by the human, 2026-10-25 about 16:30 GMT-3). The plan below uses harder
tasks with an oracle that a model cannot argue with: a pipeline, a test suite or a number.

| Track | Task | Oracle | What is recorded |
|---|---|---|---|
| Repair (EXP-10) | Three defects planted on purpose in real modules, each caught by an existing test: the cap of fix attempts (`merge_guard`), the check of a service-account address (`service_accounts`), the gated mutation score (`mutation_gate`). Pushed to `demo/bug-*` branches with no merge request: `request_fix` opens the issue | The pipeline of the fix passes; the diff touches only the defect; no test is deleted, skipped or weakened (read from the diff); at most 3 attempts | Time from push to issue, to merge request, to green; attempts; files and lines changed; credits |
| Hard build (EXP-11) | `scripts/sci_estimate.py` (SCI formula with validation and a CLI) and `scripts/cost_summary.py` (parse the cost log, group, sum, treat unknown as missing). Issues #13 and #14, with a full specification | Acceptance tests written before the run and kept out of the repository; `red_check`; `mutation_gate` | Hidden tests passed of total; mutation score of the new file; attempts; credits |
| Test writing (EXP-12) | Five issues raising coverage of the weakest files (#7 to #11), with the baseline in the text | Line and branch coverage measured on `main` before and after; mutation score measured in CI on a branch that touches the file | Before and after per file; tests added; repairs needed |
| Chaos (EXP-06) | Faults C1 to C9 | The pass rules of the table above | Result per fault |
| Service load (EXP-07) | Short, small load on the live service | p50, p95, error rate, instances | Table above |

The tools of EXP-11 are also the instruments of EXP-09: `cost_summary` turns the cost log into the
benchmark table and `sci_estimate` turns CI seconds into energy and carbon with the assumptions
printed next to the result.

### EXP-12 results: coverage on `main`, before and after the five test merge requests

Measured locally with `python -m pytest --cov=src --cov=scripts --cov-branch` on 2026-10-25.

| File | Before | After |
|---|---|---|
| `scripts/red_check.py` | 50 % | 99 % |
| `scripts/check_docs.py` | 0 % | 100 % |
| `scripts/build_state.py` | 0 % | 100 % |
| `scripts/afaw_state/source.py` | 34 % | 100 % |
| `scripts/check_task_files.py` | 72 % | 97 % |
| `src/afaw_web/app.py` | 94 % | 100 % |
| `src/afaw_web/main.py` | 0 % | 0 % (its merge request has conflicts) |
| Total, `src/` and `scripts/` | 86 % | 94 % |
| Tests in the suite | 586 | 776 |

All five merge requests failed `red_check` at first, which is expected for tests of code that
already exists, and a Duo session started by a note repaired each one by declaring the tests as
characterization: five repairs out of five. The conflict of the sixth was passed to Duo too.


## How to add a row

1. Run the experiment. 2. `python -m scripts.cost_log --mr <iid> --what "<name>" --session <url>`.
3. Read the credits from the dashboard by hand. 4. Add the row with its link. A cell that could
not be measured stays `null` or `not run`.
