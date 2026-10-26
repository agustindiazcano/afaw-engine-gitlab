# Demo script (under 3 minutes)

Rule for the recording: show only what ran. Each segment names the page or command and the text
that must appear on screen. If a segment's condition is not met when you record, cut the segment;
do not narrate around it. Target: 2 minutes 50 seconds.

The loop takes about 10 to 24 minutes in real time (measured: [`../experiments.md`](../experiments.md)).
Record the whole run in one take with the GitLab clock visible, then cut the waits and speed up the
rest. Put "sped up, 24 min real" on screen over any cut or sped-up part. Say the real time out loud.

## Prepare (before recording)

| Step | Command or page | Check |
|---|---|---|
| 1 | Open in separate tabs: the project pipelines, the issues list, the merge requests list, the live demo app https://afaw-demo-app-ljm5hefnsq-uc.a.run.app, the dashboard https://afaw-handsoff-ljm5hefnsq-uc.a.run.app/live/ and `/experiments/` | Signed out of GitLab is fine: the project is public |
| 2 | `GITLAB_TOKEN=... python -m scripts.demo on --issues 0` turns the switch on (`AFAW_AUTO_MERGE=true`) without opening the sample issues | The command prints that the variables exist |
| 3 | `python -m scripts.build_state --ref gitlab/main` then `python -m scripts.orchestrator` | It prints the task it would pick and why |
| 4 | After recording: `GITLAB_TOKEN=... python -m scripts.demo off` | The switch is off and open demo issues are closed |

## Script

| Time | Show | Say (one sentence) |
|---|---|---|
| 0:00 to 0:15 | README top: stack line, what it does, what is measured | "AI agents write and repair code; ordinary programs decide whether it is acceptable and merge it." |
| 0:15 to 0:25 | Dashboard `/live/`, the carbon line at the top | "Every flow is measured: 0.45 to 4.53 grams of CO2 per merged change, with the assumptions stated." |
| 0:25 to 0:45 | Terminal: `GITLAB_TOKEN=... python -m scripts.orchestrator --create --project 88052530`. On screen: the selected task, `"issue": "created"` | "A program picks the next task from the project board and files the issue for a GitLab Duo agent. No model chooses." |
| 0:45 to 1:05 | The new issue, assigned to the Duo account; then the merge request list: the Draft merge request Duo opens (about 2 minutes later) | "Duo opens a merge request by itself." |
| 1:05 to 1:30 | The merge request pipeline: stages, `red_check` log line `OK: N added tests failed on the old code`, `mutation_gate` | "A new test must fail on the old code; the tests are mutated to prove they check something." |
| 1:30 to 1:50 | The merge request after the guard acts: "marked as ready", "enabled an automatic merge", merged. Then the pipeline of `main`: release, `deploy_demo_app`, `e2e_live` | "When every gate is green a program merges it, Cloud Run redeploys, and a browser test checks the live site." |
| 1:50 to 2:10 | The live demo app showing the change; `/api/version` with the new commit | "The running app reports the commit that was just merged." |
| 2:10 to 2:30 | Issue #58 and its pipeline: the weak-test branch, `mutation_gate` red, the issue opened 6 min 43 s after the push | "Tests that assert nothing are caught, and the agent is asked to write real ones." |
| 2:30 to 2:50 | `/experiments/`, section "Hands-off loop": nine stages with their Duo merge requests, the repair chain times, and "What this does not prove" | "Nine of nine stages have a merge request written by Duo. The merge uses a person's token, and the code review flow has not run." |

## Segments that depend on something that has not run

| Segment | Condition to include it | If the condition is false |
|---|---|---|
| Orchestrator creates the issue | `scripts.orchestrator --create` merged and a task is eligible | Use the issue created by `scripts.demo on --issues 1` and say so |
| Repair of a failing live check | Use the recorded chain instead of a new run: issue #54, merge request !101, times in `experiments.md` | Cut the segment; do not stage a fault that did not happen |
| C2 weak-test segment | Issue #58 and its pipeline exist | Cut it |
| Live app and `/experiments/` pages | `/health` answers 200 right before recording | Use the local run in the README |

## Check before you publish

- Every number you say is on screen or on a linked page and was read from GitLab.
- Do not say 100 percent autonomous or no human involvement. Say what the limits section says.
- No third-party trademark or copyrighted music (hackathon rule).
- The video is on YouTube, public, and under 3 minutes.
