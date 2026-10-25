# Mutation tools measured on the CI runner

Data for the mutation gate and for the sustainability record (the CI minutes are measured, no
energy figure is derived here). Measured on 2026-10-25 on the GitLab.com shared runner
`saas-linux-small-amd64`: Python 3.12.15, x86_64, 2 vCPUs, 7954 MB. Target: `src/afaw_web` with
`tests/web`. Each tool ran once or twice; there is no statistical claim.

| Measure | mutmut 3.8.0 | cosmic-ray 8.7.0 |
|---|---|---|
| Release date (PyPI) | 2026-09-12 | 2026-08-09 |
| Python | 3.10 or newer | 3.9 or newer |
| Install | 3 s | 8 s |
| Run | 11 s (job [17444296422](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/jobs/17444296422)); a second run printed 13.21 mutations per second (job [17444606498](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/jobs/17444606498)) | baseline 1 s, `exec` 261 s |
| Whole job | 56.08 s, then 54.18 s | 309.34 s (job [17444296423](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/jobs/17444296423)) |
| Mutants | 104 | 240 |
| Killed / survived | 74 / 30 | 185 / 55 |
| Score (killed over all) | 71.2 % | 77.1 % |
| Machine-readable result | `mutants/<path>.meta` per file, JSON `exit_code_by_key` (1 killed, 0 survived); `mutants/mutmut-cicd-stats.json` with the totals | `session.sqlite`; `cosmic-ray dump` prints one JSON line per mutant with `module_path`; `cr-rate` prints the percentage of survivors |
| Native Windows | No: it needs fork support; WSL only | No restriction stated |

The two scores are not comparable: mutmut mutates only functions that are called and uses its own
operators; cosmic-ray mutated 240 places with its own set. mutmut was chosen because it ran about 24
times faster here and writes a per-file result the gate can read.

## mutmut by file

From `mutmut results --all` in job 17444606498.

| File | Mutants | Killed | Survived | Score |
|---|---|---|---|---|
| `src/afaw_web/app.py` | 45 | 28 | 17 | 62.2 % |
| `src/afaw_web/search.py` | 59 | 46 | 13 | 78.0 % |
| `src/afaw_web/settings.py`, `main.py`, `__init__.py` | 0 | | | no function to mutate |

A file with no mutants has no result, and the gate says a required file has no results.

## Proposed minimum

`mutation_min_score` is one value for every required file. The weakest file today is `app.py` at
62.2 %, and the current value of 80 would fail it. Proposal: **60**, which is the weakest score
rounded down with a margin of 2.2 points, so the first merge requests pass and a clearly weak test
fails. It is a floor to raise: the 17 survivors of `app.py` are the work that lets it move up. The
merge requests that change `app.py` (!16 and !17) change that score, so re-measure after they merge.
`state/config.json` is a human-only file: the change is its own merge request.

## What reads this

* `scripts/mutmut_results.py` turns the `.meta` files into the results of `scripts/mutation_gate.py`
  and refuses any exit code other than 0 and 1.
* `scripts/mutation_engine.py` finds the required files, writes the mutmut configuration, runs
  `python -m mutmut run` with a timeout and calls the adapter. One source directory and one test
  selection are supported, which is what was run.
* The job in `.gitlab-ci.yml` that calls the engine before `scripts.mutation_ci` is a separate merge
  request, because that file is human-only.

Not verified: the exit codes other than 0 and 1 (a timeout, no tests selected), several test
selections in one run, and the time on a larger change.
