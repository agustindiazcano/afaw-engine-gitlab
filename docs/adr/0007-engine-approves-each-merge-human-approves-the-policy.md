---
status: proposed
date: 2026-10-24
supersedes: []
tags: [merge-policy, gitlab, guardrails]
---
# The human approves the policy; the deterministic engine approves each merge

## Context
`AGENTS.md` (sections 18.9, 18.10 and 21.3) says a human reviews and merges every pull
request. That rule fits the original AFAW, where the human is the bottleneck by design. It
does not fit the GitLab Transcend Hackathon variant ("AFAW Hands-off", tracks Best Hands-off
Agent and Most Stages Covered), where the loop issue → merge request → pipeline → fix →
review → merge → release → deploy → monitor must close without a person at each merge.

The risk the old rule controlled is real: a self-healing loop can weaken its own gates
(edit `.gitlab-ci.yml`, accept a mutant as equivalent, rewrite a test until it passes). The
principle "the AI decides, the engine measures" does not change: every number still comes
from a deterministic tool, never from an agent. This record supersedes the quoted
`AGENTS.md` rule; it does not supersede an earlier ADR (ADR 0004 stays in force).

## Decision
The human approves the policy, once, in a merge request that the human merges. After that,
the engine approves each merge: a merge request into `main` is merged automatically only
when every gate is green, including the full pipeline with `red_check` and `mutation_gate`.
The loop runs in GitLab under the group service account, never under a personal token. No
one pushes directly to `main`; every change goes through a merge request.

The policy is enforced by these compensating controls, defined and implemented in task 012:

1. **Human-only files:** `.gitlab-ci.yml`, `AGENTS.md`, `state/equivalent_mutants.json`, the
   mutation and gate settings in `state/config.json`, and `deploy/`. The strongest mechanism
   the GitLab tier offers is used (CODEOWNERS, push rules, protected paths). A `govern` job
   that fails any merge request touching these files unless its author is human is the
   fallback that always works. Gaps in the tier are reported, not assumed away.
2. **Retry cap:** at most 3 automatic fix attempts per merge request; then the flow comments
   and stops. Flow runs are also capped, because the account has 500 GitLab Credits a month.
3. **Full green pipeline:** merge requires every job green, including `red_check` and
   `mutation_gate`.
4. **No test edited to pass:** a test may change only if `red_check` confirms it still fails
   on the old code.
5. **Secrets** exist only as masked, protected CI/CD variables.

## Alternatives considered
- Keep "a human approves every merge request": safest, but the loop cannot close and the
  hackathon track is out of reach.
- Let the agent approve its own merge requests: the author of a change would also be its
  judge, and nothing measured would back the approval.
- Auto-merge with no guardrails on the gate files: fastest, and the loop could lower its own
  thresholds until it passes.

## Consequences
The human no longer reads each diff, so the quality of the gates is the quality of the
result: a weak gate now merges bad code unattended. Changes to the gates become the only
changes the human must review, and they are blocked from automation. Until task 012 is
merged and the human sets this record to `accepted`, the old rule applies and no merge is
automatic. Revisit this decision if a merged change is later found to have passed the gates
while violating them, or if the GitLab tier cannot enforce the human-only files.
