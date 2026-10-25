# Workload Identity Federation for GitLab CI: no service-account key exists anywhere. GitLab
# issues an OIDC token per job (id_tokens) and Google exchanges it for a short-lived credential.
# Claim names and the issuer come from docs.gitlab.com/ci/secrets/id_token_authentication.
resource "google_iam_workload_identity_pool" "gitlab" {
  workload_identity_pool_id = var.wif_pool_id
  display_name              = "AFAW GitLab"
  description               = "Trusts one GitLab project, on its protected default branch only."
}

resource "google_iam_workload_identity_pool_provider" "gitlab" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.gitlab.workload_identity_pool_id
  workload_identity_pool_provider_id = "gitlab"
  display_name                       = "GitLab OIDC"

  attribute_mapping = {
    "google.subject"          = "assertion.sub"
    "attribute.project_id"    = "assertion.project_id"
    "attribute.namespace_id"  = "assertion.namespace_id"
    "attribute.ref"           = "assertion.ref"
    "attribute.ref_protected" = "assertion.ref_protected"
  }

  # Fails closed: a token that is not from this project, this namespace and the protected default
  # branch is rejected before any service account is involved. string() makes the comparison hold
  # whether GitLab sends a claim as a string or as a boolean.
  attribute_condition = join(" && ", [
    "string(assertion.project_id) == \"${var.gitlab_project_id}\"",
    "string(assertion.namespace_id) == \"${var.gitlab_namespace_id}\"",
    "assertion.ref_type == \"branch\"",
    "assertion.ref == \"${var.gitlab_default_branch}\"",
    "string(assertion.ref_protected) == \"true\"",
  ])

  oidc {
    issuer_uri        = "https://gitlab.com"
    allowed_audiences = [var.gitlab_oidc_audience]
  }
}
