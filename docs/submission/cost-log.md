# Cost log

One row after every Duo run. The credit columns are read by hand from the GitLab Credits
dashboard (User Settings > GitLab Credits): GitLab documents no REST or GraphQL endpoint that
returns credit usage, and the only export is the usage export in the Customers Portal, which needs
a billing account manager
([GitLab Credits dashboard](https://docs.gitlab.com/subscriptions/gitlab_credits_dashboard/)).
The other columns are measured from the public GitLab API.

Print the measured part of a row with:

```
python -m scripts.cost_log --mr <iid> --what "<flow>" --session <session url>
python -m scripts.cost_log --pipeline <id> --what "<flow>" --session <session url>
```

How to read the columns:

| Column | Source |
|---|---|
| Date and time (GMT-3) | Creation time of the earliest pipeline listed |
| Credits before, Credits after, Delta | The human, from the dashboard. `human` until filled |
| Pipelines | Every pipeline of the merge request, or the ids given |
| Job minutes | Each job's duration rounded up to a whole minute, summed. Not a billing figure |
| Job seconds | The durations GitLab reports, summed |
| Retries | Jobs that ran again with the same name in a pipeline, plus pipelines beyond the first for the same commit and source |

A value that could not be measured is `null`, never zero.

| Date and time (GMT-3) | What ran | Session URL | Merge request | Credits before | Credits after | Delta | Pipelines | Job minutes | Job seconds | Retries | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-24 23:46 | Fix CI/CD Pipeline Flow | | | human | human | human | [2985662569](https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43344247/showcase/-/pipelines/2985662569) | 2 | 79.822 | 0 | Launched manually; decision `add_comment`, no commits. The human read 0.30 credits used for the whole of October on the dashboard after this session |
