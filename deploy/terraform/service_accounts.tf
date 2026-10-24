resource "google_service_account" "deployer" {
  account_id   = "afaw-deployer-sa"
  display_name = "AFAW deployer (GitLab CI, via Workload Identity Federation)"
}

resource "google_service_account" "runtime" {
  account_id   = "afaw-runtime-sa"
  display_name = "AFAW web service runtime (no roles: it serves files baked into the image)"
}

# GitLab CI may impersonate the deployer; the provider condition already limits who gets here.
resource "google_service_account_iam_member" "deployer_wif" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.gitlab.name}/attribute.project_id/${var.gitlab_project_id}"
}

# The deployer may start revisions that run as the runtime account, and no other account.
resource "google_service_account_iam_member" "deployer_acts_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}
