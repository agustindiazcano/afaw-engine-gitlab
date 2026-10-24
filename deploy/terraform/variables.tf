variable "gcp_project_id" {
  type        = string
  description = "Google Cloud project that hosts the service. Given as TF_VAR_gcp_project_id."
}

variable "region" {
  type        = string
  description = "Region for Cloud Run and Artifact Registry. Given as TF_VAR_region."
}

variable "gitlab_project_id" {
  type        = string
  description = "Numeric id of the GitLab project (CI_PROJECT_ID). The provider trusts only it."
}

variable "gitlab_namespace_id" {
  type        = string
  description = "Numeric id of the GitLab namespace (CI_PROJECT_NAMESPACE_ID)."
}

variable "gitlab_default_branch" {
  type        = string
  default     = "main"
  description = "Only tokens of this protected branch can impersonate the deployer."
}

variable "gitlab_oidc_audience" {
  type        = string
  default     = "https://gitlab.com"
  description = "Must equal the aud of the id_tokens in .gitlab-ci.yml."
}

variable "service_name" {
  type    = string
  default = "afaw-handsoff"
}

variable "artifact_repository_id" {
  type    = string
  default = "afaw-images"
}

variable "wif_pool_id" {
  type    = string
  default = "afaw-gitlab"
}

variable "placeholder_image" {
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
  description = "Image of the first apply only; CI deploys the real one with gcloud run deploy."
}
