# Roadmap

High-level roadmap and pending tasks of AFAW Hands-off, a derived variant of AFAW for the GitLab Transcend Hackathon "Life After Code" (deadline Monday Oct 27, 2026, 10:00 GMT-3). Agents read this file to understand their next objectives.

**Do not delete this file.** Protect it with a workspace rule so agents never empty it. Update the roadmap as the project evolves.

## Phase 0: Done
- [x] Task 007: test suite passes on Windows
- [x] Import the repository into the GitLab showcase project

## Phase 1: Valid submission
- [x] Task 008: document the merge policy (ADR 0007, `AGENTS.md`, README, this roadmap)
- [x] Task 009: `.gitlab-ci.yml` with the nine stages (plan, create, verify, secure, govern, package, configure, release, monitor), GitLab SAST and secret detection in `secure`
- [x] Task 010: `collect_facts.py` with the GitLab REST API v4, GitHub kept working (see [`docs/facts.md`](docs/facts.md))

A valid submission exists after tasks 009 and 010.

## Phase 2: The loop becomes real
- [ ] Task 011: Duo agents and custom flows (read the current docs.gitlab.com pages first; record what was verified)
  - [x] Configuration in `.gitlab/duo/`, the workspace subagent, the custom flow and agent sources in `duo/`, and the `duo_config` check (see [`docs/duo.md`](docs/duo.md))
  - [ ] Human: enable the foundational flows for the top-level group, create the custom agent and flow in the UI, add the triggers, set `AFAW_BOT_USER_IDS` (steps and required roles in `docs/duo.md`)
  - [ ] First real sessions: Developer on an issue, a failed pipeline fixed by the Fix CI/CD Pipeline Flow, a review by the Code Review Flow; keep the failed pipelines in the history for the video
- [ ] Task 012: guardrails and merge policy (human-only files, 3-attempt cap, auto-merge rule); report gaps in the GitLab tier
  - [x] Deterministic parts: `scripts/merge_guard.py` and the `merge_guard` job (cap of 3 fix attempts, merge rule, merge off by default); see [`docs/merge-guard.md`](docs/merge-guard.md)
  - [ ] Human: check the Maintainer settings listed as gaps in `docs/merge-guard.md` (who may push to `main`, a real `CODEOWNERS`, Pipelines must succeed, `AFAW_BOT_USER_IDS`), then accept ADR 0007
  - [x] Add to the first line of `AGENTS.md` that this repository is `afaw-engine-gitlab` and lives on GitLab (`CLAUDE.md` already says it).
  - [x] Add to `AGENTS.md` that an agent always reads `LASTCONTEXT.md` and `PENDING.md` before anything else (section 1.2 says it only for the session-start hook).
  - [x] Fix the overclaim in `AGENTS.md` section 17.3 and reword 6.1 for Duo flows (task 018) ("guarded by CI (the govern job)"): `human_only_files` is a weak backup control. Regenerate `docs/paper/afaw.pdf` in the same merge request; `paper_pdf` keeps requiring it.
  - [x] A TeX Live job, `paper_build`, compiles the paper PDF in CI; download its artifact and commit it (see `docs/paper/README.md`).

## Phase 3: Live service and submission
- [ ] Task 013: read-only FastAPI service (dashboard, `/health`, `/api/state`, `/api/ask`), Dockerfile, `deploy/`, release and deploy job on Cloud Run
  - [x] Service in `src/afaw_web`, its image and the Terraform in `deploy/terraform` (plan: 11 to add, 0 to change, 0 to destroy)
  - [x] Human: run `terraform apply` and set the protected `GCP_*` CI/CD variables, as in [`docs/google-cloud.md`](docs/google-cloud.md) (done Oct 24, 2026)
  - [x] First run of the deploy on `main`: the issuer string and the `ref_protected` type were confirmed with a real token; the live URL is in the README
  - [x] Human: create the budget alert in the Google Cloud console (reported by the human; this repository cannot see it)
- [ ] Task 014: demo script (under 3 minutes), Devpost description, Path B explanation of what was added since Oct 5

## Phase 4: prove the hands-off loop (deadline 2026-10-27 10:00 GMT-3)
- [ ] Happy path (EXP-01): issue #6 to merge request !26 ran; the Draft state, the gates, the merge by `merge_guard` and the deploy have not been shown yet
- [ ] Autoheal (EXP-02, EXP-03): create the label, the "AFAW triage" flow and the two Pipeline Failed triggers, then push the broken branch `demo/task-028-lint-failure`
- [ ] Chaos, load, agent quality and the environmental benchmark (EXP-04 to EXP-09, see [`docs/experiments.md`](docs/experiments.md)); record each row with its link
- [ ] Demo ON and demo OFF scripts that run the whole flow and put the project back
- [ ] Update `docs/submission/devpost.md` and `path-b.md` to the final state; record the video (under 3 minutes, YouTube)
- [ ] 2026-10-26 14:00: decide Hands-off or Supervised from `docs/submission/evidence.md`
- [ ] Rebuild `docs/paper/afaw.pdf` at the end, after the last change to `AGENTS.md`

## Phase 5: the demo app, the orchestrator and the end to end loop (added 2026-10-25)
- [x] Task 091: the notes demo app `src/notes_app` with its image and tests (see [`docs/demo-app.md`](docs/demo-app.md))
- [x] Task 092 (merged, Terraform applied 2026-10-25): Terraform service `afaw-demo-app`, and the `package_demo_app`, `publish_demo_image` and `deploy_demo_app` jobs. Human: `terraform apply` (steps in `docs/google-cloud.md`), then merge the human-only MR
- [x] Task 094 (in review): Playwright end to end on both apps, see [`docs/e2e.md`](docs/e2e.md); `e2e_live` has not run on `main` yet
- [ ] One Duo experiment per stage that has none (plan, secure, package, release, configure, monitor, govern): an issue per stage, Duo changes it, evidence linked in the README table "Stages and Duo"
- [ ] Bug benchmarks on the demo app: plant a button that does nothing, a wrong result and a wrong colour; Playwright detects each, `request_fix` opens the issue, Duo repairs it, the deploy runs, Playwright passes and the issue closes. Record time per link and credits
- [ ] Telemetry report, budget guardrails and branch overlap check: plan in [`docs/plan-telemetry-and-budget.md`](docs/plan-telemetry-and-budget.md) (build after the Duo experiments)
- [ ] Orchestrator (scrum) agent: reads the same derived views as the dashboard (`build/state/pending.json`, `LASTCONTEXT.md`, metrics), picks the next task by priority and light, and files the issue. Design first as an ADR: deterministic selection in code, the agent only writes the issue text
- [ ] Context handoff rule: when an agent session reaches a context threshold it writes the prompt for the next session (what is done, what is pending, what to read first) to a file, clears, and the new session reads that file first. Design first as an ADR; the mechanism is a hook plus a `state/handoff/` file, never a secret in it

## FINAL, last of all: new white paper
- [ ] Write a new white paper for AFAW Engine (hands-off automation end to end: CI/CD, testing, security, deployment, self-repair and observability) and cite the original AFAW paper (DOI 10.5281/zenodo.23050310) instead of editing it. Write it only after the experiments, the telemetry report and the evidence table are final, so every figure in it is measured. `docs/paper/afaw.pdf` stays as the original; the new one goes in its own folder, and `paper_pdf` must keep passing

## Low priority: security hardening
Recorded on 2026-10-25. None of these blocks the loop; do them after it works.
- [ ] Revoke the personal token `automerge` (scope `api`, expires 2027-01-31): it was pasted in a conversation
- [ ] Replace it by a project access token or a group service account token made by an Owner, so a leak does not reach the human's other projects
- [ ] `AFAW_MERGE_TOKEN` is protected today and cannot be read by merge request pipelines of unprotected branches; unprotecting it exposes it to the ~50 inherited Developers of the group (the decision to unprotect is the human's)
- [ ] Set "Allowed to push" of `main` to No one (today Developers + Maintainers)
- [ ] Turn on "Pipelines must succeed" and "All threads must be resolved" in the merge request settings (both are off today)
- [ ] `AFAW_BOT_USER_IDS` is masked today; unmask it so the guard log shows the ids (the guard works either way)
- [ ] Accept ADR 0007 (`proposed` today)
- [ ] The strong control for human-only files (pipeline execution policy or CODEOWNERS with required approval)

## FINAL: strong human-only-files control
Do this last, only after the pipeline, the Duo flows and Cloud Run work. Until then `human_only_files` is a weak backup control.
- [ ] Preferred: a pipeline execution policy in a separate private project (for example `afaw-policies`) linked from Secure > Policies. Our role may not allow creating policies, so first ask in #transcend-hackathon.
- [ ] Fallback: CODEOWNERS with "Require approval from code owners" enabled on protected `main`. List `CODEOWNERS` itself, and keep the auto-merge account out of "Allowed to push and merge".
