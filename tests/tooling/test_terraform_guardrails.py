"""Guardrails on deploy/terraform: no hardcoded identity, no keys, least privilege."""

from __future__ import annotations

import re

import pytest

from tests.tooling.conftest import REPO_ROOT

TF_DIR = REPO_ROOT / "deploy" / "terraform"
NO_DEFAULT = ("gcp_project_id", "region", "gitlab_project_id", "gitlab_namespace_id")


def _tf() -> dict[str, str]:
    files = {p.name: p.read_text(encoding="utf-8") for p in sorted(TF_DIR.glob("*.tf"))}
    assert files, "deploy/terraform has no .tf files"
    return files


def _all() -> str:
    return "\n".join(_tf().values())


def _variable_block(name: str) -> str:
    match = re.search(rf'variable "{name}" \{{(.*?)\n\}}', _all(), re.S)
    assert match, f"variable {name} is not declared"
    return match.group(1)


@pytest.mark.parametrize("name", NO_DEFAULT)
def test_identity_variables_have_no_default(name: str) -> None:
    assert "default" not in _variable_block(name)


def test_the_backend_is_partial() -> None:
    backend = re.search(r'backend "gcs" \{(.*?)\}', _all(), re.S)
    assert backend and "bucket" not in backend.group(1)


def test_no_service_account_keys_exist() -> None:
    assert "google_service_account_key" not in _all()
    assert not list(TF_DIR.glob("*.json"))


def test_no_project_wide_iam() -> None:
    assert not re.search(r'resource "google_project_iam_\w+"', _all())


def test_no_broad_role_is_granted() -> None:
    roles = re.findall(r'role\s*=\s*"([^"]+)"', _all())
    assert roles, "no IAM role found"
    assert not [r for r in roles if re.search(r"admin|owner|editor", r, re.I)]


def test_the_deployer_gets_exactly_the_required_roles() -> None:
    roles = set(re.findall(r'role\s*=\s*"([^"]+)"', _all()))
    assert roles == {
        "roles/iam.workloadIdentityUser",
        "roles/run.developer",
        "roles/artifactregistry.writer",
        "roles/iam.serviceAccountUser",
        "roles/run.invoker",
    }


def test_all_users_may_only_invoke_the_service() -> None:
    blocks = re.findall(r'resource "[^"]+" "[^"]+" \{.*?\n\}', _all(), re.S)
    with_all_users = [b for b in blocks if "allUsers" in b]
    # Two public services: the dashboard and the demo notes app. Nothing else is public.
    assert len(with_all_users) == 2
    assert all('role     = "roles/run.invoker"' in b for b in with_all_users)
    assert all("google_cloud_run_v2_service." in b for b in with_all_users)


def test_the_provider_trusts_only_this_gitlab_project() -> None:
    text = _all()
    assert 'issuer_uri        = "https://gitlab.com"' in text
    for claim in ("project_id", "namespace_id", "ref_protected", "ref_type"):
        assert f"assertion.{claim}" in text
    assert "var.gitlab_project_id" in text and "var.gitlab_namespace_id" in text


def test_cloud_run_scales_to_zero_with_a_small_cap_and_a_dedicated_account() -> None:
    text = _all()
    assert "min_instance_count = 0" in text and "max_instance_count = 2" in text
    assert "google_service_account.runtime.email" in text
    assert "compute@developer" not in text
    assert 'cpu    = "1"' in text and 'memory = "512Mi"' in text and "timeout" in text


def test_the_image_is_left_to_ci_after_the_first_apply() -> None:
    assert re.search(r"ignore_changes\s*=\s*\[.*?containers\[0\]\.image", _all(), re.S)


def test_no_gcp_identifier_is_written_in_the_repo() -> None:
    text = _all() + "\n".join(
        p.read_text(encoding="utf-8") for p in TF_DIR.glob("*.example")
    )
    assert not re.search(r"\b\d{12}\b", text), "a 12-digit project number is written"
    assert not re.search(r"project-[0-9a-f]{8}-", text)
    assert not re.search(r"\b[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}\b", text)
