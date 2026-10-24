# Roadmap

High-level roadmap and pending tasks of AFAW Hands-off, a derived variant of AFAW for the GitLab Transcend Hackathon "Life After Code" (deadline Monday Oct 27, 2026, 10:00 GMT-3). Agents read this file to understand their next objectives.

**Do not delete this file.** Protect it with a workspace rule so agents never empty it. Update the roadmap as the project evolves.

## Phase 0: Done
- [x] Task 007: test suite passes on Windows
- [x] Import the repository into the GitLab showcase project

## Phase 1: Valid submission
- [x] Task 008: document the merge policy (ADR 0007, `AGENTS.md`, README, this roadmap)
- [x] Task 009: `.gitlab-ci.yml` with the nine stages (plan, create, verify, secure, govern, package, configure, release, monitor), GitLab SAST and secret detection in `secure`
- [ ] Task 010: `collect_facts.py` with the GitLab REST API v4, GitHub kept working

A valid submission exists after tasks 009 and 010.

## Phase 2: The loop becomes real
- [ ] Task 011: Duo agents and custom flows (read the current docs.gitlab.com pages first; record what was verified)
- [ ] Task 012: guardrails and merge policy (human-only files, 3-attempt cap, auto-merge rule); report gaps in the GitLab tier
  - [ ] Add to `AGENTS.md` that an agent always reads `LASTCONTEXT.md` and `PENDING.md` before anything else (section 1.2 says it only for the session-start hook).
  - [ ] Fix the overclaim in `AGENTS.md` section 17.3 ("guarded by CI (the govern job)"): `human_only_files` is a weak backup control. Regenerate `docs/paper/afaw.pdf` in the same merge request; `paper_pdf` keeps requiring it.
  - [ ] Add a TeX Live job to rebuild the paper PDF (there is no `paper_build` job until then).

## Phase 3: Live service and submission
- [ ] Task 013: read-only FastAPI service (dashboard, `/health`, `/api/state`, `/api/ask`), Dockerfile, `deploy/`, release and deploy job on Cloud Run
  - [x] Service in `src/afaw_web`, its image and the Terraform in `deploy/terraform` (plan: 11 to add, 0 to change, 0 to destroy)
  - [ ] Human: run `terraform apply` and set the protected `GCP_*` CI/CD variables, as in [`docs/google-cloud.md`](docs/google-cloud.md)
  - [ ] First run of the deploy on `main`: confirm the issuer string and the `ref_protected` type with a real token, then fill the live URL in the README
  - [ ] Human: create the budget alert in the Google Cloud console
- [ ] Task 014: demo script (under 3 minutes), Devpost description, Path B explanation of what was added since Oct 5

## FINAL: strong human-only-files control
Do this last, only after the pipeline, the Duo flows and Cloud Run work. Until then `human_only_files` is a weak backup control.
- [ ] Preferred: a pipeline execution policy in a separate private project (for example `afaw-policies`) linked from Secure > Policies. Our role may not allow creating policies, so first ask in #transcend-hackathon.
- [ ] Fallback: CODEOWNERS with "Require approval from code owners" enabled on protected `main`. List `CODEOWNERS` itself, and keep the auto-merge account out of "Allowed to push and merge".
