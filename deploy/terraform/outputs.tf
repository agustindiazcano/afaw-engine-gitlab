# What the CI/CD variables GCP_WORKLOAD_IDENTITY_PROVIDER, GCP_DEPLOYER_SERVICE_ACCOUNT and
# GCP_ARTIFACT_REPOSITORY hold, plus the live URL.
output "workload_identity_provider" {
  value = google_iam_workload_identity_pool_provider.gitlab.name
}

output "deployer_service_account" {
  value = google_service_account.deployer.email
}

output "runtime_service_account" {
  value = google_service_account.runtime.email
}

output "artifact_repository" {
  value = "${var.region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "service_url" {
  value = google_cloud_run_v2_service.web.uri
}
