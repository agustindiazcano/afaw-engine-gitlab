---
status: active
date: 2026-10-25
tags: [ci, deploy, concurrency, request_fix]
---
# Parallel pipelines of `main` overwrite each other's deploy

## Symptom
After several merge requests merge in the same minute, some pipelines of `main` fail in
`deploy_demo_app` or `monitor_live` with "the live service reports another commit", although the
code is fine. With the hands-off switch on, `request_fix` then opens issues for the Developer Flow,
which would spend credits on a failure that is not a defect of the code.

## What to do
The deploy jobs (`publish_image`, `deploy_cloud_run`, `publish_demo_image`, `deploy_demo_app`) share
a `resource_group: deploy`, so only one runs at a time. A residual race remains between the deploy
and the later `monitor_live`; a failure that names a commit that is not the pipeline's own is this
race, and the issue is closed with a note. In the settings of the resource group, the process mode
`oldest_first` keeps the order of the pipelines.

Found by the burst of seven merges of EXP-05 ([`experiments.md`](../experiments.md)); fixed in task 106.
