---
status: active
date: 2026-10-25
tags: [agents, process, merge-policy]
---
# An agent says a capability does not exist without reading the plan and the code

## Symptom
In the session of 2026-10-25 an agent reported that the loop had "no documented way to merge" and
that the merge should stay "a human click, or outside Hands-off". The human corrected it: the
merge was planned as automatic from the start (continuous deployment, with delivery as the other
option). The agent was wrong, and it had read none of the files that answer the question.

What was wrong, and where the right answer already was:

| What was said | What was true | Where it was already written |
|---|---|---|
| No path exists for a flow to merge, so "Supervised" with a human click is the recommendation | Duo has no merge tool, but the merge never depended on Duo: `merge_guard` merges through the API when its verdict is yes. Task 012 (!10) merged it | ADR 0007; `scripts/merge_guard.py` docstring; `docs/duo.md` row 5, "The deterministic policy (task 012), not Duo" |
| The merge is a human's choice only | It is a setting: `AFAW_AUTO_MERGE=true` with `AFAW_MERGE_TOKEN` is continuous deployment; unset is continuous delivery. Both are supported | `docs/autohealing.md`, section "Delivery or deployment" |
| Nobody can post the final comment on the issue | A deterministic CI job with a project access token can; `CI_JOB_TOKEN` cannot. This was the plan, not built yet | `docs/duo.md`, "No automatic summary after the merge" |
| The README lists the automatic merge and the cap of 3 as Planned | They are merged (task 012, !10), tested, and never run on a real merge request. The README was stale and nobody checked | `README.md`, now corrected |

Two smaller slips in the same session:

* The first lookup was in the stale GitHub copy of the repository (`origin`), not in `gitlab`.
  `AGENTS.md` and `CLAUDE.md` both say to use `gitlab/main`.
* Merge times were written into `docs/submission/evidence.md` as "before 17:00" without reading
  them. They were read from the API before the commit and corrected to the exact minutes. The
  rule "never claim a result that was not measured" (`AGENTS.md` section 2.2) covers this.

## Cause
The agent answered from the report pasted into the conversation and from the conversation so far.
That report was about what Duo flows can do. The agent applied it to the whole loop, and the whole
loop includes the repository's own engine.

## What to do
Before saying that something does not exist, cannot be done, or has "no way":

1. Search the project for it: `docs/adr/`, `docs/duo.md`, the docstring of the script that would
   do it, `state/tasks/`, and the README status tables. `grep` for the words, not only the name.
2. Say which thing lacks the capability. "Duo has no merge tool" and "the project cannot merge"
   are different statements.
3. A README or status table that says Planned for something already merged is a defect to fix, not
   a fact to repeat. Compare it with `git log` and the merge requests.
4. A number or a time in a document is read from the API or the log in the same session, or it is
   not written.
5. A choice the plan already made (here: automatic merge) is not reopened as a question for the
   human. Report the gap between the plan and what runs, and build what is missing.
