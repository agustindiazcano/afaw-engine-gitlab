# Instructions for Claude Code

This repository is `afaw-engine-gitlab` (AFAW Hands-off) and it lives on GitLab: base all work on the `gitlab` remote (`gitlab/main`); `origin` is the old GitHub copy and is stale.

The rules live in AGENTS.md, the single source for every coding agent. This file imports it.

@AGENTS.md

## Read the plan before saying something is missing
An agent in this repository does not say "there is no way to X", "X is not possible" or "X stays a
human step" before it has searched `docs/adr/`, `docs/duo.md`, `docs/autohealing.md`, the docstring
of the script that would do it, `state/tasks/` and the README status tables.

* Say which part lacks the capability. "Duo has no merge tool" is not "the project cannot merge":
  `merge_guard` merges through the API (continuous deployment with `AFAW_AUTO_MERGE=true`,
  continuous delivery otherwise).
* Do not reopen a choice the plan already made. Report the gap between the plan and what runs, and
  build what is missing.
* A status table that says Planned for something already merged is stale: fix it.
* A number, a time or a status written in a document is read from the API or the log in the same
  session, or it is not written.
* Use the `gitlab` remote. `origin` is the stale GitHub copy.

The mistakes that led to this section, and where each right answer was already written, are in
[`docs/gotchas/0004-read-the-plan-before-saying-a-capability-is-missing.md`](docs/gotchas/0004-read-the-plan-before-saying-a-capability-is-missing.md).
