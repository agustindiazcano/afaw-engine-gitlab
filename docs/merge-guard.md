# Merge guard: fix-attempt cap and automatic merge rule

`scripts/merge_guard.py` and the `merge_guard` job implement the deterministic parts of
[ADR 0007](adr/0007-engine-approves-each-merge-human-approves-the-policy.md) (task 012). The ADR is
still `proposed`: until the human accepts it, `AGENTS.md` section 18.9 applies and no merge is
automatic. The job merges nothing unless a person turns it on.

## What the job does

It runs last (stage `monitor`) in merge request pipelines only, reads the merge request, its latest
pipeline and that pipeline's jobs from the GitLab REST API v4, prints a verdict and, only if told
to, asks GitLab to merge.

| Rule | Definition | Result when broken |
|---|---|---|
| Cap of fix attempts | A fix attempt is a commit pushed by a Duo flow service account (ids in the group variable `AFAW_BOT_USER_IDS`) after the first failed pipeline of the merge request. Two pipelines of one commit count once. More than 3 attempts break the cap | The job fails (exit 1), so the pipeline is red and the merge request cannot pass |
| Merge rule | The merge request is open, not a draft, targets the default branch, has no conflicts and no unresolved blocking discussion; the latest pipeline is for the head commit; every other job of that pipeline has the status `success`; `red_check`, `mutation_gate` and `security_gate` are present | `merge: no` with every reason listed; nothing is merged |
| Who made the change | The head pipeline was started by a user whose id is in `AFAW_BOT_USER_IDS`, and every commit of the merge request is authored by a service account address (`service_account_...@noreply.gitlab.com`). The merge request author is not looked at: with a Duo flow it is the person who triggered the flow (composite identity), and the committer is that person too. With no id configured nothing is merged automatically | `merge: no` with the reason; a person's merge request is never merged by the guard |
| Cannot decide | An API error, an unreadable response, a missing variable | Exit 2; nothing is merged (fails closed) |

A failed job that is allowed to fail, a skipped job and a manual job do not count as green.

### Who made the change

Read on 2026-10-25 from merge requests !16, !17 and !18 (Developer Flow): MR author id 43344247 (a
person), commit author `Duo Developer <service_account_group_..._...@noreply.gitlab.com>`, committer
the same person, pipeline user `duo-developer-gitlab-ai-hackathon` (id 33073386). The Fix CI/CD
Pipeline Flow account is id 33073387. Both ids belong in `AFAW_BOT_USER_IDS`.

The pipeline user is the authoritative signal. The author address is forgeable, so it only adds
conditions: `human_only_files` fails when a commit authored by a service account changes a human-only
file (whoever started the pipeline, so a person re-running a flow's pipeline does not clear it), and
`merge_guard` requires the address on every commit in addition to the pipeline user. A person who
forges the address still fails the pipeline-user condition.

Run against the real merge requests with `AFAW_AUTO_MERGE` unset: !16 was held only for being a
draft; the same run with no ids was also held for the missing ids; !14, a person's merge request, was
held because its pipeline and its commits were not a service account's.

### What the cap does not do

The job cannot stop a flow from running. GitLab documents no attempt cap for the Fix CI/CD Pipeline
Flow ([`docs/duo.md`](duo.md)). The guard makes the merge request fail once the cap is passed and says
so; a person must remove the trigger or the flow from the merge request to stop the spending of
credits. The count sees only commits that start a pipeline, and only those pushed by an id in
`AFAW_BOT_USER_IDS`: if that variable is empty the count is always 0.

## Leaving Draft

The Developer Flow opens its merge requests as Draft, and no Duo tool clears the state (the tools
page has none, and `/ready` does not work through a note). With `AFAW_AUTO_MERGE=true` the guard
does it: when the **only** reason for `merge: no` is the draft state, which means the pipeline is
green, the required jobs are present, no conflict, the cap holds and the pipeline user and every
commit author are service accounts, it writes the title without its `Draft:` marker with
`PUT /projects/:id/merge_requests/:iid` and then asks for the merge as usual. A draft with any
other reason, a draft of a person and a draft with the switch off are never touched. The call needs
`AFAW_MERGE_TOKEN`; without it, or if GitLab refuses, the job exits 2 and nothing changes.

Never run on a real merge request until the first Duo merge request after this change.

## Turning the merge on

| Variable | Value | Where |
|---|---|---|
| `AFAW_AUTO_MERGE` | exactly `true` (anything else, including `True`, keeps the merge off) | Settings > CI/CD > Variables |
| `AFAW_MERGE_TOKEN` | a project access token with the `api` scope whose user may merge into `main` | Settings > CI/CD > Variables, masked |

The guard calls `PUT /projects/:id/merge_requests/:iid/merge` with the head commit `sha` and
`auto_merge: true` (parameters read on docs.gitlab.com on 2026-10-24). Because the guard runs inside
the pipeline, `auto_merge` makes GitLab merge once the pipeline has passed, instead of refusing now;
`sha` makes GitLab refuse if the branch moved.

This path has not run against a real merge request: it needs the two variables, a token and an
accepted ADR. Until then the job only prints its verdict.

A protected variable is not passed to pipelines of unprotected branches, which is where merge
request pipelines of feature branches run. So `AFAW_MERGE_TOKEN` would have to be unprotected, and
then any pipeline of the project can read it. That is the cost of merging from inside the pipeline.
The alternative that needs no token in the pipeline is GitLab's own merge-when-pipeline-succeeds on a
merge request, set by a person.

## Gaps: what needs a Maintainer setting

Nothing below is assumed. "Read" means read from the public API on 2026-10-24; the rest answered
`401` without a login, so a person must look.

| # | Setting | What the API showed | What to check or do in the UI |
|---|---|---|---|
| 1 | Who may push to `main` | Read: `Developers + Maintainers` may push and merge, force push is off | **Settings > Repository > Branch rules > `main` > Protect branch**: set **Allowed to push and merge** to **No one**, and **Allowed to merge** to the roles that should merge. The ADR says nobody pushes to `main` |
| 2 | Code owner approval | Read: not required on `main` | Needs a tier that supports it; **Protect branch > Require approval from code owners** |
| 3 | `CODEOWNERS` | Read: the file is `* @owner`, a placeholder from the template. `@owner` is the username of an unrelated GitLab account | Replace it with the real owners before turning on code owner approval; otherwise approvals are asked from a stranger |
| 4 | Pipelines must succeed | Not readable (401) | **Settings > Merge requests > Merge checks**: check whether **Pipelines must succeed** is on. Without it a merge is not blocked by a red pipeline |
| 5 | Skipped pipelines count as success | Not readable (401) | Same page: **Skipped pipelines are considered successful** should be off |
| 6 | All threads resolved | Not readable (401) | Same page: **All threads must be resolved** |
| 7 | Approvals and approval rules | Not readable (401) | **Settings > Merge requests > Merge request approvals** |
| 8 | Push rules | Not readable (401) | **Settings > Repository > Push rules**; needs Premium or Ultimate |
| 9 | Merge when pipeline succeeds | Not readable (401) | The button on each merge request; the guard uses the API equivalent only when switched on |
| 10 | `AFAW_BOT_USER_IDS` | Not readable (variables are private) | Group-level variable with the ids of the flows' service accounts, from [`docs/duo.md`](duo.md) step 6. Empty means the cap counts nothing |
| 11 | The strong control of human-only files | `human_only_files` is a weak backup control (it lives in `.gitlab-ci.yml`) | Pipeline execution policy in a separate project, or code owner approval with a real `CODEOWNERS` (see `PENDING.md`) |

## What was verified

Tested on recorded payloads of this project (pipeline jobs from `tests/tooling/fixtures/gitlab`) and
on constructed ones for the cases the history does not contain: no flow has ever pushed to a merge
request here, so the attempt count has never been seen on a real flow. The rule, the exit codes and
the request the guard sends are covered by `tests/tooling/test_merge_guard.py`.
