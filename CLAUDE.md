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

## Goal and priorities (changed 2026-10-25)
The goal is to show an agentic flow that does everything by itself: an issue or a broken push
becomes a fix, a merge request, a review, a merge, a release, a deploy and a comment, with no person
in the middle. The merge is automatic (continuous deployment, `AFAW_AUTO_MERGE=true`); continuous
delivery is the fallback, not the design.

* **Working first, security second.** A security recommendation never blocks the loop. Record it in
  `PENDING.md` under "Low priority: security hardening" and keep going. Do not remove a gate that
  already exists (the human-only files, `merge_guard`, the red-first check) to make something work.
* **A level of autonomy is claimed only with evidence per link** (`docs/submission/evidence.md`).
  Never write Hands-off in a document before a real failure went through the whole loop.
* **Secrets:** a token pasted in the conversation is used from an environment variable of one
  command, never written to a file, a commit, a memory or a document. Say once that it was exposed
  and should be revoked after the tests.
* **Where to look:** the competition rules and the coverage of each prize are in
  `docs/submission/rules-and-coverage.md`; the experiments, benchmarks and the data tables are in
  `docs/experiments.md`; the delivery or deployment modes of the merge are in `docs/autohealing.md`.
* **Data:** every figure in those tables is read from the API or a log in the same session. LLM
  tokens are not exposed by GitLab Duo; the unit is the GitLab Credit, read by hand.
