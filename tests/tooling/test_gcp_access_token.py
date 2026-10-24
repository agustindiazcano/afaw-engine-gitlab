"""Tests for deploy/gcp_access_token.sh: GitLab OIDC token in, short-lived access token out."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from tests.tooling.conftest import REPO_ROOT

SCRIPT = REPO_ROOT / "deploy" / "gcp_access_token.sh"
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="bash is not available")

STUB = """#!/bin/sh
# Fake curl: records the call and answers by URL.
echo "$@" >> "$CALLS"
case "$*" in
  *sts.googleapis.com*) echo '{{"access_token": "FEDERATED", "token_type": "Bearer"}}' ;;
  *generateAccessToken*) echo '{{"accessToken": "{final}", "expireTime": "x"}}' ;;
esac
"""

ENV = {
    "GITLAB_OIDC_TOKEN": "id-token-value",
    "GCP_WORKLOAD_IDENTITY_PROVIDER": (
        "projects/1/locations/global/workloadIdentityPools/p/providers/g"
    ),
    "GCP_DEPLOYER_SERVICE_ACCOUNT": "deployer@example.iam.gserviceaccount.com",
}


def _run(
    tmp_path: Path, env: dict[str, str], final: str = "FINAL"
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    curl = bin_dir / "curl"
    curl.write_text(STUB.format(final=final), encoding="utf-8")
    curl.chmod(curl.stat().st_mode | stat.S_IEXEC)
    full = {**os.environ, **env, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    full["CALLS"] = str(tmp_path / "calls.txt")
    assert BASH is not None
    return subprocess.run(
        [BASH, str(SCRIPT)], env=full, capture_output=True, text=True, timeout=30, check=False
    )


def test_prints_only_the_final_access_token(tmp_path: Path) -> None:
    result = _run(tmp_path, ENV)
    assert result.returncode == 0 and result.stdout.strip() == "FINAL"


def test_exchanges_the_token_for_this_provider_and_impersonates_the_deployer(
    tmp_path: Path,
) -> None:
    _run(tmp_path, ENV)
    calls = (tmp_path / "calls.txt").read_text(encoding="utf-8")
    assert "//iam.googleapis.com/projects/1/locations/global/workloadIdentityPools/p" in calls
    assert "serviceAccounts/deployer@example.iam.gserviceaccount.com:generateAccessToken" in calls


@pytest.mark.parametrize("name", sorted(ENV))
def test_a_missing_variable_fails_loudly(tmp_path: Path, name: str) -> None:
    env = {k: v for k, v in ENV.items() if k != name}
    env_cleared = {**env, name: ""}
    result = _run(tmp_path, env_cleared)
    assert result.returncode != 0 and name in result.stderr and result.stdout == ""


def test_a_rejected_exchange_fails_without_printing_a_token(tmp_path: Path) -> None:
    result = _run(tmp_path, ENV, final="")
    assert result.returncode != 0 and result.stdout == ""
    assert "FEDERATED" not in result.stderr and "id-token-value" not in result.stderr
