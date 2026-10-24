# Bootstrap for the AFAW Hands-off service on Google Cloud. It creates new resources only and
# never imports or changes anything that already exists in the project.
terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }

  # Partial configuration: the bucket and prefix are passed with
  #   terraform init -backend-config=backend.hcl
  # so no bucket name is written in the repository.
  backend "gcs" {}
}

provider "google" {
  project = var.gcp_project_id
  region  = var.region
}
