---
status: proposed
date: 2026-10-24
supersedes: []
tags: [deploy, google-cloud, security]
---
# Deploy to Cloud Run from GitLab CI with Workload Identity Federation, applied by a human

## Context
The hackathon requires a live URL, and the Google Cloud bonus requires the deployment code in the
public repository. The Google Cloud project already hosts other public services, other
Terraform stacks and a shared state bucket, none of which this work may change. GitLab CI needs
to deploy without a long-lived credential: a leaked service-account key is the failure this
project's guardrails exist to prevent ([ADR 0007](0007-engine-approves-each-merge-human-approves-the-policy.md)).

## Decision
1. The Terraform in `deploy/terraform` creates new resources only: a Workload Identity pool and
   provider for GitLab, a deployer and a runtime service account, an Artifact Registry
   repository and one public Cloud Run service. A human runs `terraform apply`; CI never does.
2. GitLab CI authenticates with Workload Identity Federation and the job's OIDC token. No
   service-account key exists. The provider accepts a token only when `project_id` and
   `namespace_id` are this project's, and the ref is the protected default branch.
3. The deployer has `run.developer` on the one service, `artifactregistry.writer` on the one
   repository and `serviceAccountUser` on the runtime account only. The runtime account has no
   roles and is never the default Compute account.
4. The state is in an existing GCS bucket under a new prefix, with the bucket passed as a partial
   backend configuration. No identifier of the Google Cloud project is written in the repository.
5. CI copies the image built in `package` to Artifact Registry (Cloud Run cannot pull from the
   GitLab registry) and runs `gcloud run deploy`. Terraform ignores the image after the first apply.
6. The service is read-only and makes no paid call per request; it scales to zero with a maximum
   of two instances.

## Alternatives considered
- A JSON service-account key in a masked variable: simple, but a long-lived secret that a
  compromised job or log can leak. Rejected.
- Reuse the existing GitHub workload identity pools: they trust another forge and other
  repositories, and changing them could break services that work. Rejected.
- GitLab-managed Terraform state: needs no bucket, but writing it needs the Maintainer role and
  keeps the state away from the project that owns the resources. The existing bucket under a new
  prefix was preferred.
- Let CI run `terraform apply`: this would give the pipeline permission to change IAM, which
  the least-privilege deployer must not have. Rejected; the human applies once.
- Build the image with Cloud Build: needs more APIs and a broader role. Rejected.

## Consequences
Nothing in the pipeline can widen its own access: the deploy account can only update one
service. The cost is a manual first step (apply, then set protected variables) and a deploy path
that cannot be tested until that is done, so the first run on `main` is the real verification.
The public endpoint has no rate limiting, a gap bounded by the instance cap. Revisit this
decision if the issuer or claim format check on the first real token fails, or if the service
ever needs a secret or a paid call.
