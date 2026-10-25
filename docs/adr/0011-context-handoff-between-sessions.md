---
status: proposed
date: 2026-10-25
supersedes: []
tags: [handoff, context, hooks]
---
# A session writes a handoff file near its context limit; the next session reads it first

## Context
Long sessions lose their context. Today the next prompt is written by hand from the conversation, and
what was done, what is pending and what was measured depends on the author's memory. AGENTS.md section 1
already makes every session read `LASTCONTEXT.md` and `PENDING.md` first.

## Decision
`scripts/handoff.py` writes `state/handoff/HANDOFF.md` from facts it reads itself: the current branch, the
open merge requests and issues, the last pipelines of `main`, and the list of pending items of `PENDING.md`.
The agent adds free text for "what is done" and "what to read first". The session-start hook prints the file
when it exists. The file never holds a secret: the script refuses text that matches a token pattern.

## Alternatives considered
- Rely on the model's own context summary: it is not under version control and cannot be audited.
- Put the handoff in `LASTCONTEXT.md`: that file is generated and never edited (AGENTS.md section 1.7).

## Consequences
A new session starts from one file. The file can go stale, so it carries the commit it was written at and
the hook says when `main` has moved. Worth revisiting if the hook cannot detect the context threshold:
until then the agent or the human triggers the script.
