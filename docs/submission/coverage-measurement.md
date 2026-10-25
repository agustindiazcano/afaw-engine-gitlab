# Coverage measurement

First measurement of line and branch coverage, taken locally on 2026-10-25 (GMT-3) on `main` at
`b479cbf`, with `python -m pytest --cov=src --cov=scripts --cov-branch`
(pytest-cov 7.1.0, coverage 7.16.1, Python 3.12.4, Windows). It is not a CI number: the runner was
not used, and no coverage job exists yet.

| Scope | Statements | Missed | Branches | Partial | Cover |
|---|---|---|---|---|---|
| `src/` and `scripts/`, total | 2460 | 316 | 826 | 74 | 86 % |
| `src/afaw_web/` (the mutation-critical path) | 86 | 4 | 8 | 2 | 95 % (`app.py` 94 %, `search.py` 100 %, `settings.py` 100 %, `main.py` 0 %) |

Files with the lowest coverage:

| File | Cover | Note |
|---|---|---|
| `scripts/build_state.py` | 0 % | Command-line entry point; `scripts.afaw_state` below it is covered |
| `scripts/check_docs.py` | 0 % | Command-line entry point |
| `src/afaw_web/main.py` | 0 % | Two statements that start the server |
| `scripts/afaw_state/source.py` | 34 % | Reads from git; not exercised by the tests |
| `scripts/red_check.py` | 50 % | Runs the test suite on the old code; the git paths are not exercised |
| `scripts/check_task_files.py` | 72 % | |

## What this says and does not say

- High coverage with a mutation score of 62.2 % on `app.py` (see
  [mutation-tools-measurement.md](mutation-tools-measurement.md)) means lines are run but not all
  behaviour is asserted. The two numbers are meant to be read together.
- The 0 % files are entry points. This measurement does not decide whether they need tests.

## Proposal, not built

A `coverage_gate` job that fails below a minimum would edit `.gitlab-ci.yml` and
`state/config.json`, both human-only. A minimum of 80 % on `src/afaw_web/` leaves 15 points of
margin on today's 95 %. The human decides whether to add it.
