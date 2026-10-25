# Competition rules and how much of them the project covers

Source: the Official Rules and the overview page of the GitLab Transcend "Life After Code"
hackathon on Devpost, read on 2026-10-25. The percentages below are counts of items, not a
judgement of quality. A row counts as covered only when there is evidence for it in
[`evidence.md`](evidence.md) or in the public repository.

## The rules that bind the submission

| Rule | Value |
|---|---|
| Submission period | 2026-10-05 10:00 UTC to **2026-10-27 13:00 UTC** (10:00 GMT-3) |
| Judging | 2026-10-28 to 2026-11-14; winners around 2026-11-16 |
| Path | **B, Bring Your Own**: existing MIT project, imported to GitLab; the automation and the deployment must be new work done on or after 2026-10-05 |
| Level of autonomy | One of Assisted, Supervised, Hands-off. Hands-off is "a full loop from code to production with no human in the middle" |
| Must use | GitLab Duo Agent Platform (agents, flows, MCP clients) |
| Repository | Public GitLab URL, MIT licence visible in the About section, all source and instructions |
| Pipeline history | Visible and showing the automation running |
| Path B extras | URL of the original MIT project; URL of the deployed project, live until about 2026-11-16; explain what was added during the submission period |
| Google Cloud bonus | Up to 0.2 points (final score up to 5.2): deployment code in the public repository and a public live link |
| Video | Under 3 minutes, public on YouTube, shows the automation running, no third-party trademarks or copyrighted music |
| Language | English |
| Judging criteria (equal weight) | Technological Implementation, Design, Potential Impact, Innovation/Idea, Presentation |
| Prize for stages | Most Stages Covered: nine stages: plan, create, verify, package, secure, release, configure, monitor, govern |
| Prize for sustainability | Most Environmentally Impactful: opt-in; must quantify the gain with public methods and SCI |

## Submission requirements: 8 of 12 covered (67 %)

| # | Requirement | Covered | Evidence or gap |
|---|---|---|---|
| 1 | Uses Duo Agent Platform | Yes | Developer Flow ran in five sessions, four of them opened a merge request (!16, !17, !18, !26; the session for issue #4 opened none); Fix CI/CD ran once; the agent "AFAW merge agent" exists in the AI Catalog |
| 2 | Public GitLab repository | Yes | Visibility public |
| 3 | MIT licence detected by GitLab | Yes | The API reports licence `mit` for the project |
| 4 | Pipeline history shows the automation | Yes | Pipelines of `main` and of !16 to !26 |
| 5 | URL of the original MIT project | Yes | In the README |
| 6 | Deployed project, public | Yes | Cloud Run service `afaw-handsoff`, `/health` answers 200 |
| 7 | Google Cloud deployment code in the repository | Yes | `deploy/terraform/` and the deploy jobs of `.gitlab-ci.yml` |
| 8 | Written in English | Yes | `AGENTS.md` section 0 |
| 9 | Text description | Partly | `docs/submission/devpost.md` exists; it must be updated to the final state |
| 10 | Explanation of what was added since 2026-10-05 | Partly | `docs/submission/path-b.md` and the README timeline; they stop at 2026-10-24 |
| 11 | Demo video under 3 minutes | **No** | Script in `demo-script.md`; not recorded |
| 12 | Live until about 2026-11-16 | Not yet decidable | The service is up today; the cost bound is a maximum of two instances |

## Judging criteria: where the project stands

Self-assessment from the evidence. It is not a score.

| Criterion | What supports it | What is missing |
|---|---|---|
| Technological Implementation | Nine-stage pipeline, deterministic gates (`red_check`, `mutation_gate`, `security_gate`, `merge_guard`, `human_only_files`), 586 tests, 86 % line and branch coverage | The mutation gate has not run on a real change to `src/afaw_web` |
| Design | The loop issue to production exists as a design and each link is tracked | No complete loop has run without a person |
| Potential Impact | Governance of agents that edit code: they cannot weaken their own gates | No user or audience evidence |
| Innovation/Idea | "The AI decides, the engine measures"; identity by commit author and pipeline user; red-first | |
| Presentation | Script written | No video |

## Level of autonomy: 12 of 14 links ran at least once (86 %); the feature path ran seven times with no click after the issue, the repair path once

The 13 links are the rows of the table in [`evidence.md`](evidence.md#hands-off-loop-link-by-link).

| Level | Fits today | Why |
|---|---|---|
| Assisted | Yes | A person starts every flow and merges |
| Supervised | Yes, with the issue-to-merge-request and deploy parts | A person starts the flow, marks the draft ready and approves; the gates, the deploy and the monitor ran on their own |
| Hands-off | **Mostly, with three gaps**: the feature path (issue, Duo merge request, gates, undraft, merge, release, deploy, monitor) ran seven times with no click; the repair path (failure, issue opened by `request_fix`, Duo merge request, merge by the guard) ran once end to end (issue #19 to !47). Not run: the automatic review, the summary comment on the issue, and a repair that needed more than one attempt. The identity of the undraft and the merge is a person's token | A level is claimed only with evidence per link |

The decision between Hands-off and Supervised is made on 2026-10-26 14:00 from the evidence table.

## Prizes: what the project can claim

| Prize | Amount | Coverage | Basis |
|---|---|---|---|
| Path B Best Hands-off Agent | $5,000 | Demonstrated for the feature and repair paths | Seven merges by the guard; one repair end to end; see the gaps above |
| Path B Best Supervised Agent | $4,000 | Claimable | See the level table |
| Path B Best Assisted Agent | $4,000 | Claimable | Fits, but only one level is submitted |
| Most Stages Covered (Path B) | $5,000 | **9 of 9 stages have a running job** (100 %); 2 of 9 with a Duo flow that ran (create: Developer Flow; verify: Fix CI/CD, once) | Pipeline of `main`; Duo evidence is in `evidence.md` |
| Most Environmentally Impactful | $5,000 | **Not claimable**: 0 measured figures | Method and tool exist ([ADR 0009](../adr/0009-measure-sustainability-with-sci.md), `scripts/cost_log.py`), see [`experiments.md`](../experiments.md) |
| Most Creative | $4,000 | Decided by the Innovation score | Nothing to submit separately |
| Google Cloud bonus | up to 0.2 points | Requirements met (code and a public live link) | Final score is 1 to 5.2 |

A project wins at most one path prize and one special prize.

## What else the rules ask that is still open

| Item | Owner |
|---|---|
| Record and upload the video | Human |
| Update the Devpost text and the Path B text to the final state | Agent, after the experiments |
| Opt in to the sustainability prize on the form, only with measured figures | Human, on 2026-10-26 |
| Keep the Cloud Run service up until about 2026-11-16 | Human (budget alert exists) |
