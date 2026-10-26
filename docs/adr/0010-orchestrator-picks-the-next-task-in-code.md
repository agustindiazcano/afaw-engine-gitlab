---
status: proposed
date: 2026-10-25
supersedes: []
tags: [orchestrator, hands-off, tokens]
---
# The orchestrator picks the next task in code; the agent only writes the issue text

## Context
The loop starts from an issue. Today a person decides which issue comes next. A scrum-style agent
that reads the whole repository to decide would spend tokens and credits on every pick, and its choice
could not be reproduced. The dashboard already derives `build/state/pending.json`, `LASTCONTEXT.md`
and the metrics from the task files and the GitLab API (AGENTS.md section 3).

## Decision
`scripts/orchestrator.py` selects the next task as a pure function of `pending.json`: tasks with
status `pending` or `backlog`, owner `agent`, and no blocker that is still open, ordered by ascending
priority, then ascending difficulty, then task id (a task already `in_progress` has a branch and an owner). It prints the selection and the reason as JSON. A Duo agent (or a person)
only writes the issue text for the selected task; it does not choose. The issue is created through
the API and assigned to the Developer Flow account, as in the stage experiments.

## Alternatives considered
- Let an LLM read the repository and choose: not reproducible, and it spends credits on every pick.
- A person chooses every time: it is the step this project is meant to remove.
- A queue in a new database: the derived views already hold the same facts, and AGENTS.md section 20
  says state is recorded once.

## Consequences
The pick is the same for the same input and costs no credits. The quality of the pick depends on the
priorities declared in the task files. Saving tokens against reading the code is expected, not measured,
until the comparison in EXP-09 runs (the unit is GitLab Credits and CI seconds, not tokens). Worth
revisiting if the declared priorities prove unreliable.
