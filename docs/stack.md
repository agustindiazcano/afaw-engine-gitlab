# Technology stack, infrastructure as code and CI/CD

How the project is built and deployed. Read with [`google-cloud.md`](google-cloud.md) (setup steps
and who may do what), [`autohealing.md`](autohealing.md) (the repair loop) and
[`demo-app.md`](demo-app.md) (the app the agents change).

## Stack

| Layer | Choice | Where |
|---|---|---|
| Language and checks | Python 3.12, pytest, mypy `--strict`, ruff, mutmut (mutation testing) | `scripts/`, `tests/`, `.gitlab-ci.yml` |
| Web services | FastAPI on uvicorn: the dashboard (`src/afaw_web`) and the demo notes app (`src/notes_app`) | `src/` |
| Packaging | Docker images tagged with the commit (never `latest`); Buildah as the fallback builder | `Dockerfile`, `src/notes_app/Dockerfile` |
| Registry | GitLab Container Registry (build), Google Artifact Registry (what Cloud Run pulls) | `package_*`, `publish_*` jobs |
| Runtime | Google Cloud Run, us-central1, minimum 0 and maximum 2 instances per service | `deploy/terraform/cloud_run.tf` |
| Infrastructure as code | Terraform 1.x with the `hashicorp/google` provider `~> 8.0`, state in a Cloud Storage bucket | `deploy/terraform/` |
| Identity | Workload Identity Federation from the GitLab OIDC token; no service account key exists | `deploy/terraform/wif.tf`, `deploy/gcp_access_token.sh` |
| Agents | GitLab Duo Agent Platform: Developer Flow, Fix CI/CD Pipeline Flow, custom agent "AFAW merge agent" | `duo/`, `.gitlab/duo/`, [`duo.md`](duo.md) |
| Security scanning | GitLab SAST (Semgrep) and secret detection, turned into a blocking decision by `security_gate` | `.gitlab-ci.yml` |
| End to end tests | Playwright (planned, see `PENDING.md`) | |

## Infrastructure as code (Terraform)

| Resource | Purpose |
|---|---|
| Workload Identity pool `afaw-gitlab` and provider `gitlab` | Accepts only tokens of this GitLab project, namespace and protected `main` |
| Service accounts `afaw-deployer-sa` and `afaw-runtime-sa` | The deployer is impersonated by CI; the runtime account has no roles |
| Artifact Registry repository `afaw-images` | Images that Cloud Run pulls |
| Cloud Run service `afaw-handsoff` | The public dashboard |
| Cloud Run service `afaw-demo-app` | The public demo notes app |
| IAM members | The deployer is `run.developer` on each service; `allUsers` has `run.invoker` on the two services and nothing else |

A person applies the Terraform (`terraform init "-backend-config=backend.hcl"`, `plan`, `apply`); CI
only validates and formats it (`terraform_validate`). Both services ignore changes to the image and
the environment, because CI sets those on every deploy. The tests in
`tests/tooling/test_terraform_guardrails.py` fail if a key, a wildcard role or a third public
resource appears.

## CI/CD (`.gitlab-ci.yml`)

36 jobs in nine stages, plus the SAST and secret detection template jobs. Merge request pipelines
run the gates; the pipeline of `main` also releases and deploys.

| Stage | Jobs |
|---|---|
| plan | `task_files`, `docs_check`, `duo_config` |
| create | `task_delta`, `derived_views`, `web_data` |
| verify | `lint`, `typecheck`, `tests`, `red_check`, `mutation_gate`, `e2e_local` |
| secure | `semgrep-sast`, `secret_detection`, `security_gate` |
| govern | `paper_pdf`, `paper_build`, `human_only_files`, `equivalent_mutants_report`, `repair_check` |
| package | `package_docker`, `package_buildah` (fallback), `package_demo_app` |
| configure | `check_configuration`, `terraform_validate` |
| release | `release`, `publish_image`, `deploy_cloud_run`, `publish_demo_image`, `deploy_demo_app`, `e2e_live` |
| monitor | `monitor`, `monitor_live`, `merge_guard`, `telemetry_report`, `request_fix` |

Release path on `main`: build in the GitLab registry, copy to Artifact Registry with a short-lived
Google token, `gcloud run deploy` with the commit in the environment, then a check that the live
service reports that commit (`monitor_live` for the dashboard, inside `deploy_demo_app` for the
demo app).

CI/CD variables (names only; values are never written in the repository):

| Variable | Use |
|---|---|
| `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOYER_SERVICE_ACCOUNT`, `GCP_ARTIFACT_REPOSITORY`, `GCP_SERVICE_NAME`, `GCP_SERVICE_URL` | Deploy; protected, so only `main` reads them |
| `AFAW_AUTO_MERGE` | `true` turns on the automatic merge; anything else only prints the verdict |
| `AFAW_BOT_USER_IDS` | Service account ids that count as non-human |
| `AFAW_MERGE_TOKEN` | Token of a person that `merge_guard` and `request_fix` use; to be replaced (see `PENDING.md`) |

Human-only files (`.gitlab-ci.yml`, `deploy/`, `AGENTS.md`, `state/config.json`,
`state/equivalent_mutants.json`) change only in a merge request that a person opens.
