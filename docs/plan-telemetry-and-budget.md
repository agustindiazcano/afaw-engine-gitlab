# Plan: telemetry report, budget guardrails and state reconciliation

Status: planned, not built. Written 2026-10-25 from a list of four gaps that the human brought. Each
gap is checked against what the repository already does, so nothing is built twice and nothing is
claimed that does not run. Build it after the end to end loop and the Duo experiments
([`PENDING.md`](../PENDING.md), Phase 5).

## The four gaps against the current code

| # | Gap as written | What exists today | What is missing | Verdict |
|---|---|---|---|---|
| 1 | Three-way merge of the agents' knowledge, typed conflict detection | One branch per task, one task file and one delta per task, `check_task_files` and `check_task_delta` reject overlaps, `human_only_files` | Detection of two open branches that touch the same file or the same task id before they merge | Build a small pre-merge conflict report from the GitLab API; do not build a knowledge graph |
| 2 | Stop after 3 failed repairs, dump telemetry, fall back | Cap of 3 automatic fix attempts per merge request or branch, 6 open autoheal issues at most (`merge_guard`, `request_fix`) | A frozen state with a written log when the cap is hit, and a credit budget | Extend: write the log and a freeze marker when a cap is hit; read credits by hand |
| 3 | Pinned system prompt and `/clear` between tasks for prompt caching | The agent rules live in `AGENTS.md`, imported by `CLAUDE.md`; Duo reads the files from the repository | GitLab Duo flows build their own prompts and expose no token counts, so cache hits cannot be seen or controlled | Not measurable for Duo. Apply it only to local sessions through the context handoff rule |
| 4 | An audit trail for every self-healing event, with a fixed schema | `docs/experiments.md`, `docs/data/experiments.json`, `evidence.md`, issues and merge requests of `request_fix` | One generated file that lists each event with the same fields | Build `scripts/telemetry_report.py`, read-only, from the API |

## Telemetry report

`scripts/telemetry_report.py` reads the public GitLab API and writes `build/AFAW_TELEMETRY.md`
(generated, never committed; also published on the `/experiments/` page). One block per
self-healing event, from the issue opened by `request_fix` to the merge of the repair:

| Field | Source |
|---|---|
| Timestamp, branch or component | Issue creation time; merge request source branch |
| Trigger | The failed jobs and the end of their logs that `request_fix` copied into the issue |
| Root cause | The text of the repair merge request description, quoted, never summarised by the script |
| Remediation | Files changed in the merge request (API diff stats) |
| Validation | Status of the pipeline of the merge commit and of the next `e2e_live`; time from issue to merge |

A block with a missing source says `not available`, never an estimate. The schema is checked by
tests with a recorded API fixture.

## Budget guardrails

| Guard | How |
|---|---|
| Three attempts per failure | Already enforced; add a line in the issue and a `state/freeze/` marker read by `request_fix` when the cap is hit |
| Credits | GitLab exposes no token counts and no credits endpoint ([`cost-log.md`](submission/cost-log.md)); the human reads the balance, and `request_fix` stops when `AFAW_AUTO_MERGE` is off |
| Concurrency | At most 6 open autoheal issues (already enforced) |

## State reconciliation

A job `branch_overlap` in merge request pipelines lists the other open merge requests that touch
the same files or the same task id (API `changes`), and fails with the list. It does not merge
anything. This is the part of the "three-way merge" that a pipeline can decide deterministically.

## Auditing what an agent says

What is checked by code today, so an agent is never believed on its word:

| Claim | Check | Where |
|---|---|---|
| "I wrote a test that fails first" | The test is run on the old code | `red_check` |
| "My tests are good" | Changed files are mutated and the tests must notice | `mutation_gate` (AST-level mutants via mutmut) |
| "These are the files I touched" | `files_touched` must equal the diff | `check_task_delta` |
| "This took N minutes, CI is green" | Rejected in task files; measured values come from the API | `check_task_files`, `collect_facts` |
| "I did not change the rules" | Human-only files and the identity of author and pusher | `human_only_files`, `merge_guard` |
| "No secret, no vulnerability" | Scanner reports turned into a decision | `security_gate` |
| "It works when deployed" | The live service must report the commit; Playwright uses it | `monitor_live`, `deploy_demo_app`, `e2e_live` |

Not checked today, and the plan for each:

| Gap | Plan |
|---|---|
| A repair merge request claims to fix a failure: nobody checks that the job that failed now passes | A job `repair_check` in merge request pipelines: when the description or the issue names a failed job, require that job to be green in this pipeline. Deterministic, reads the API |
| Numbers written in documents | `check_docs` extension: a figure listed in `docs/data/experiments.json` must match where it is quoted |
| The AFAW auditor agent (source in `duo/custom-agent.md`, read-only) was never created in the UI and never ran | Create it and run it on one merge request as an experiment; its verdict is advice, the gates decide |
| Prose claims in merge request descriptions | Not checkable by code; they are not used as evidence anywhere |

## Order

| # | Step | Depends on |
|---|---|---|
| 1 | `telemetry_report.py` with tests, then the page section | Repair events exist (they do) |
| 2 | Freeze marker and log in `request_fix` | 1 |
| 3 | `branch_overlap` job (human-only file: merge request by the human) | — |
| 4 | Context handoff for local sessions | ADR |

## What is not claimed

No saving from prompt caching, no 10x figure and no zero human intervention is claimed anywhere:
none was measured. The telemetry file reports only what the API shows.
