# Public, read-only service: it serves files baked into the image and makes no paid call, so a
# public endpoint costs nothing per request beyond Cloud Run itself. It scales to zero.
resource "google_cloud_run_v2_service" "web" {
  name                = var.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = true

  template {
    service_account = google_service_account.runtime.email
    timeout         = "30s"

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.placeholder_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }

  # CI deploys the real image with gcloud run deploy; Terraform must not revert it.
  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
      template[0].containers[0].env,
      client,
      client_version,
    ]
  }
}

resource "google_cloud_run_v2_service_iam_member" "deployer_developer" {
  name     = google_cloud_run_v2_service.web.name
  location = google_cloud_run_v2_service.web.location
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.web.name
  location = google_cloud_run_v2_service.web.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# The demo notes app (src/notes_app): the target that the Duo flows change through issues. It is a
# separate service so a reader can open it and see the change an agent made. Same limits as above.
resource "google_cloud_run_v2_service" "demo" {
  name                = var.demo_service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = true

  template {
    service_account = google_service_account.runtime.email
    timeout         = "30s"

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.placeholder_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
      }
    }
  }

  # CI deploys the real image with gcloud run deploy; Terraform must not revert it.
  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
      template[0].containers[0].env,
      client,
      client_version,
    ]
  }
}

resource "google_cloud_run_v2_service_iam_member" "demo_deployer_developer" {
  name     = google_cloud_run_v2_service.demo.name
  location = google_cloud_run_v2_service.demo.location
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_cloud_run_v2_service_iam_member" "demo_public" {
  name     = google_cloud_run_v2_service.demo.name
  location = google_cloud_run_v2_service.demo.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
