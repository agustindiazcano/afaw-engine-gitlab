# Demo script (under 3 minutes)

Rule for the recording: show only what ran. Each segment names the page or command and the text
that must appear on screen. If a segment's condition is not met when you record, cut the segment;
do not narrate around it. Read every number from the screen at the moment of recording; do not say
a number from this file. Target: 2 minutes 50 seconds.

The real run takes 25 to 45 minutes (measured: [`../experiments.md`](../experiments.md)). Record the
whole run in one take with the GitLab clock visible, then cut the waits and speed up the rest. Put
"sped up, N min real" on screen over any cut or sped-up part, and say the real time out loud.

## Prepare (before recording)

| Step | Where | Command or page | Check |
|---|---|---|---|
| 1 | Terminal | `cd` to the repository folder, then `git fetch gitlab` and `git checkout --detach gitlab/main` | The tree is at the latest `gitlab/main` |
| 2 | Terminal | `$env:GITLAB_TOKEN = "..."` then `Clear-Host`, before the recording starts | The token is never on screen |
| 3 | Terminal | `python -m scripts.build_state --ref gitlab/main` | It writes the derived views |
| 4 | Terminal | `python -m scripts.orchestrator` (no `--create`) | It prints the task it would pick and why; no issue is filed and no credits are spent |
| 5 | Browser | `https://afaw-demo-app-ljm5hefnsq-uc.a.run.app/health` | It answers `{"status":"ok"}` |
| 6 | Both | Zoom the browser and the terminal to 150 percent; keep the clock of the taskbar visible | Text is readable in the video |
| 7 | Browser | Open the seven tabs below, in order, signed out of nothing the video should not show | All load |
| 8 | Notes | Write down the credit reading before launching | One number, read from the GitLab Credits dashboard |

The switch `AFAW_AUTO_MERGE` must already be `true` (check in the project CI/CD variables). Do not run
`python -m scripts.demo on`: it is not needed and it files the sample issues. Do not run
`python -m scripts.demo off` after recording until the filmed run is recorded in the repository.

Tabs, in order, with `P` = `https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase`:

| Tab | Page |
|---|---|
| 1 | `P` (the project page, which renders the README) |
| 2 | `https://afaw-handsoff-ljm5hefnsq-uc.a.run.app/live/` |
| 3 | `P/-/issues` |
| 4 | `P/-/merge_requests` |
| 5 | `P/-/pipelines` |
| 6 | `https://afaw-demo-app-ljm5hefnsq-uc.a.run.app` |
| 7 | `https://afaw-handsoff-ljm5hefnsq-uc.a.run.app/experiments/` |

## Launch command

```powershell
python -m scripts.orchestrator --create --project 88052530
```

It must print `"issue": "created"` and the selected task. Stay on that screen for three seconds.
The task that is queued for the filmed run is `task_155` (filter the notes by text, in the API and on
the page); `task_154` (mark a note as done) already ran as the test take.

## Script

| Time | Page | Show | Say |
|---|---|---|---|
| 0:00 to 0:15 | Tab 1 | README top: stack line, what it does, what is measured | "Hi, I'm Agustin. AI agents can already write code. The slow part is everything after it: checking, merging, deploying and verifying. AFAW Engine closes that loop on GitLab." |
| 0:15 to 0:25 | Tab 2 | The carbon line at the top of the dashboard | "Every flow is measured. The carbon figure on screen comes with its assumptions." |
| 0:25 to 0:45 | Terminal | The launch command; on screen: the selected task and `"issue": "created"` | "One command. A program picks the next task from the project board and files the issue for a GitLab Duo agent. No model chooses the work." |
| 0:45 to 1:05 | Tabs 3 and 4 | The new issue assigned to the Duo account; then the Draft merge request Duo opens (a few minutes later, reload until it appears) | "Duo opens a merge request by itself. In real time that took about N minutes." |
| 1:05 to 1:30 | Tab 5 | The merge request pipeline: stages, the `red_check` log line `OK: N added tests failed on the old code`, `mutation_gate` | "A new test must fail on the old code, and the tests are mutated to prove they check something." |
| 1:30 to 1:50 | Tabs 4 and 5 | The merge request after the guard acts: "marked as ready", "enabled an automatic merge", merged; then the pipeline of `main`: release, `deploy_demo_app`, `e2e_live` | "When every gate is green, a program merges it. Code decides, not a model. Cloud Run redeploys and a browser test checks the live app." |
| 1:50 to 2:15 | Tab 6 | The live demo app: add three notes (`buy milk`, `call mom`, `milk tea`), type `milk` in the filter field, two notes remain; then `/api/version` shows the new commit | "The running app has the feature Duo just wrote, and reports the commit that was just merged." |
| 2:15 to 2:30 | Tab 7 | `/experiments/`, section "Hands-off loop": the nine stages with their Duo merge requests and the times of each link | "Nine of nine DevSecOps stages have a merge request written by Duo." |
| 2:30 to 2:50 | Tab 7 | The part "What this does not prove" | "The merge uses a person's token, and the review and the summary note are started by a person. Everything is measured and linked. The repository and the live dashboard are in the description." |

If the video goes over 3:00, shorten 1:05 to 1:30 first.

## If something fails during the run

| Situation | What to do |
|---|---|
| A gate fails and a note "attempt N of 3" mentions the Duo account on the merge request | That is `request_fix`, the repair loop, working as designed. Show it and write down the time |
| A job fails on `main` | Write down the time and the job name. Closing the issue that `request_fix` opens does not stop a Duo session that already started |
| Duo opens no merge request within 15 minutes | Stop, do not launch another session, and record the failure instead of hiding it |
| Any other case | Do not launch another Duo session and do not merge by hand during the take |

## Segments that depend on something that has not run

| Segment | Condition to include it | If the condition is false |
|---|---|---|
| Orchestrator creates the issue | The command prints `"issue": "created"` | Cut the video and start again after finding the cause; do not file the issue by hand and call it the orchestrator |
| Repair of a failing live check | Use the recorded chain instead of a new run: issue #54, merge request !101, times in `experiments.md`, shown as a still image | Cut the segment; do not stage a fault that did not happen |
| Weak-test case (chaos C2) | Issue #58 and its pipeline exist; show them as a still image | Cut it |
| Live app and `/experiments/` pages | `/health` answers 200 right before recording | Use the local run in the README |

## After the recording

Tell the agent that keeps the repository: the credit reading before and after, the link of the
video, and the time and name of every failure seen. It records the filmed run in `experiments.md`,
`evidence.md`, the white paper and the Devpost text, replaces `<DEMO_VIDEO_URL>` in the README, and
synchronizes with GitHub.

## Check before you publish

- Every number you say is on screen or on a linked page and was read from GitLab.
- Do not say 100 percent autonomous or no human involvement. Say what the limits section says.
- No third-party trademark or copyrighted music (hackathon rule).
- The video is on YouTube, public, and under 3 minutes.
