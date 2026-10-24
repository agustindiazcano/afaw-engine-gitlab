#!/bin/sh
# Exchange the GitLab job's OIDC token for a short-lived Google access token of the deployer
# service account, with Workload Identity Federation. No key exists: the only credential is the
# id_token GitLab issues to this job, and it is accepted only for this project's protected main.
#
# Flow (docs.gitlab.com/ci/cloud_services/google_cloud): 1) the Security Token Service swaps the
# GitLab token for a federated token; 2) that token impersonates the deployer service account.
# Prints only the final access token on stdout. It never echoes a token or a response body.
#
# Needs: GITLAB_OIDC_TOKEN, GCP_WORKLOAD_IDENTITY_PROVIDER (projects/N/locations/global/
# workloadIdentityPools/P/providers/G) and GCP_DEPLOYER_SERVICE_ACCOUNT (the email).
set -eu

for name in GITLAB_OIDC_TOKEN GCP_WORKLOAD_IDENTITY_PROVIDER GCP_DEPLOYER_SERVICE_ACCOUNT; do
  eval "value=\${$name:-}"
  if [ -z "$value" ]; then
    echo "ERROR: $name is not set" >&2
    exit 1
  fi
done

extract() {
  sed -n "s/.*\"$1\": *\"\([^\"]*\)\".*/\1/p"
}

federated=$(curl -sS -X POST "https://sts.googleapis.com/v1/token" \
  -H "Content-Type: application/json" \
  -d "{\"audience\":\"//iam.googleapis.com/${GCP_WORKLOAD_IDENTITY_PROVIDER}\",\"grantType\":\"urn:ietf:params:oauth:grant-type:token-exchange\",\"requestedTokenType\":\"urn:ietf:params:oauth:token-type:access_token\",\"scope\":\"https://www.googleapis.com/auth/cloud-platform\",\"subjectTokenType\":\"urn:ietf:params:oauth:token-type:jwt\",\"subjectToken\":\"${GITLAB_OIDC_TOKEN}\"}" \
  | extract access_token)
if [ -z "$federated" ]; then
  echo "ERROR: the Security Token Service did not return a token (check the provider condition)" >&2
  exit 1
fi

final=$(curl -sS -X POST \
  "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${GCP_DEPLOYER_SERVICE_ACCOUNT}:generateAccessToken" \
  -H "Authorization: Bearer ${federated}" \
  -H "Content-Type: application/json" \
  -d '{"scope":["https://www.googleapis.com/auth/cloud-platform"]}' \
  | extract accessToken)
if [ -z "$final" ]; then
  echo "ERROR: the deployer service account could not be impersonated (check its bindings)" >&2
  exit 1
fi

printf '%s\n' "$final"
