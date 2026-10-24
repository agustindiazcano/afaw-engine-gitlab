resource "google_artifact_registry_repository" "images" {
  repository_id = var.artifact_repository_id
  location      = var.region
  format        = "DOCKER"
  description   = "AFAW web service images, pushed by GitLab CI"
}

resource "google_artifact_registry_repository_iam_member" "deployer_writer" {
  repository = google_artifact_registry_repository.images.name
  location   = google_artifact_registry_repository.images.location
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
}
