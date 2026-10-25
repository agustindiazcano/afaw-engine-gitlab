"""Structure of .gitlab-ci.yml: nine stages, each with a real job, and the guardrails."""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from tests.tooling.conftest import REPO_ROOT

STAGES = [
    "plan", "create", "verify", "secure", "govern", "package", "configure", "release", "monitor",
]
# Jobs whose script comes from an included GitLab template, not from this file.
NATIVE = {"semgrep-sast", "secret_detection"}
CI_FILE = REPO_ROOT / ".gitlab-ci.yml"


class _GitLabLoader(yaml.SafeLoader):
    """SafeLoader that accepts GitLab's !reference tag (kept as a plain list)."""


_GitLabLoader.add_constructor(
    "!reference", lambda loader, node: loader.construct_sequence(node)
)


@pytest.fixture(scope="module")
def ci() -> dict[str, Any]:
    assert CI_FILE.is_file(), ".gitlab-ci.yml does not exist"
    return yaml.load(CI_FILE.read_text(encoding="utf-8"), Loader=_GitLabLoader)  # noqa: S506


def _jobs(ci: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {k: v for k, v in ci.items() if isinstance(v, dict) and "stage" in v}


def _is_real(name: str, job: dict[str, Any]) -> bool:
    return name in NATIVE or "script" in job or "release" in job


def _script(job: dict[str, Any]) -> str:
    return "\n".join(str(line) for line in job.get("script", []))


def test_declares_the_nine_stages_in_order(ci: dict[str, Any]) -> None:
    # "test" is required by the GitLab SAST templates; no job of ours uses it.
    assert [s for s in ci["stages"] if s != "test"] == STAGES
    assert "test" in ci["stages"] and "test" not in {j["stage"] for j in _jobs(ci).values()}


def test_every_stage_has_a_real_job(ci: dict[str, Any]) -> None:
    jobs = _jobs(ci)
    for stage in STAGES:
        staged = {n: j for n, j in jobs.items() if j["stage"] == stage}
        assert staged, f"stage {stage} has no job"
        assert any(_is_real(n, j) for n, j in staged.items()), f"stage {stage} has no real job"
        assert not any(_script(j).strip() in {"", "echo"} for j in staged.values() if "script" in j)


def test_every_job_stage_is_declared(ci: dict[str, Any]) -> None:
    assert {j["stage"] for j in _jobs(ci).values()} <= set(STAGES)


def test_native_security_templates_are_included(ci: dict[str, Any]) -> None:
    templates = {i.get("template") for i in ci["include"] if isinstance(i, dict)}
    assert {"Jobs/SAST.gitlab-ci.yml", "Jobs/Secret-Detection.gitlab-ci.yml"} <= templates


def test_native_security_jobs_run_in_the_secure_stage_and_do_not_tolerate_failure(
    ci: dict[str, Any],
) -> None:
    for name in ("semgrep-sast", "secret_detection"):
        assert ci[name]["stage"] == "secure"
        assert ci[name]["allow_failure"] is False


def test_security_gate_reads_both_scanner_reports(ci: dict[str, Any]) -> None:
    job = ci["security_gate"]
    assert job["stage"] == "secure" and set(job["needs"]) == {"semgrep-sast", "secret_detection"}
    script = _script(job)
    assert "gl-sast-report.json" in script and "gl-secret-detection-report.json" in script


def test_configure_has_a_real_job_that_checks_configuration(ci: dict[str, Any]) -> None:
    assert "scripts.check_ci_config" in _script(ci["check_configuration"])
    assert ci["check_configuration"]["stage"] == "configure"


def test_no_placeholder_job_that_fails_on_purpose(ci: dict[str, Any]) -> None:
    for name, job in _jobs(ci).items():
        assert "not implemented" not in _script(job), f"{name} is a placeholder"
    assert "paper_build" not in ci


def test_merge_request_pipelines_do_not_duplicate_branch_pipelines(ci: dict[str, Any]) -> None:
    rules = ci["workflow"]["rules"]
    assert any("merge_request_event" in r.get("if", "") for r in rules)
    assert any(r.get("when") == "never" and "CI_OPEN_MERGE_REQUESTS" in r["if"] for r in rules)


def test_release_tags_do_not_start_pipelines(ci: dict[str, Any]) -> None:
    assert not any("CI_COMMIT_TAG" in r.get("if", "") for r in ci["workflow"]["rules"])


def test_verify_jobs_run_the_afaw_gates(ci: dict[str, Any]) -> None:
    scripts = "\n".join(_script(j) for j in _jobs(ci).values() if j["stage"] == "verify")
    for expected in ("scripts.red_check", "scripts.mutation_ci", "pytest tests/tooling",
                     "ruff check", "mypy --strict scripts"):
        assert expected in scripts


def test_the_pipeline_clones_full_history(ci: dict[str, Any]) -> None:
    assert str(ci["variables"]["GIT_DEPTH"]) == "0"


def test_package_builds_with_docker_and_falls_back_to_buildah(ci: dict[str, Any]) -> None:
    docker, buildah = ci["package_docker"], ci["package_buildah"]
    assert docker["stage"] == buildah["stage"] == "package"
    assert any("docker:" in str(s) for s in docker["services"])
    assert "quay.io/buildah" in buildah["image"]
    assert "$CI_REGISTRY_IMAGE" in _script(docker) and "$CI_COMMIT_SHA" in _script(docker)
    assert "latest" not in _script(docker) + _script(buildah)
    assert any("PACKAGE_BUILDER" in str(r) for r in docker["rules"] + buildah["rules"])


def test_duo_configuration_is_validated_in_plan(ci: dict[str, Any]) -> None:
    assert ci["duo_config"]["stage"] == "plan"
    assert "scripts.check_duo_config" in _script(ci["duo_config"])


def test_package_builds_the_web_service_from_the_assembled_data(ci: dict[str, Any]) -> None:
    for name in ("package_docker", "package_buildah"):
        assert "web_data" in ci[name]["needs"]
        assert "afaw-web:" in _script(ci[name])
    assert "build/web-data/" in ci["web_data"]["artifacts"]["paths"]


def test_quality_jobs_cover_the_service_sources(ci: dict[str, Any]) -> None:
    assert "src" in _script(ci["typecheck"]) and "tests/web" in _script(ci["tests"])


def test_every_image_is_pinned(ci: dict[str, Any]) -> None:
    def name(image: Any) -> str:
        return str(image["name"] if isinstance(image, dict) else image)

    images = [name(ci["default"]["image"])]
    images += [name(j["image"]) for j in _jobs(ci).values() if "image" in j]
    assert not [i for i in images if i.endswith(":latest") or ":" not in i.split("/")[-1]]


def test_terraform_is_formatted_and_validated_in_configure(ci: dict[str, Any]) -> None:
    job = ci["terraform_validate"]
    assert job["stage"] == "configure" and "hashicorp/terraform:" in str(job["image"])
    script = _script(job)
    assert "fmt -check" in script and "validate" in script and "-backend=false" in script


MAIN_ONLY = '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'


@pytest.mark.parametrize("name", ["publish_image", "deploy_cloud_run", "monitor_live"])
def test_the_google_cloud_jobs_run_on_main_only(ci: dict[str, Any], name: str) -> None:
    assert [r["if"] for r in ci[name]["rules"]] == [MAIN_ONLY]


def test_the_deploy_uses_workload_identity_and_no_key(ci: dict[str, Any]) -> None:
    for name in ("publish_image", "deploy_cloud_run"):
        tokens = ci[name]["id_tokens"]
        assert tokens["GITLAB_OIDC_TOKEN"]["aud"] == "https://gitlab.com"
        assert "deploy/gcp_access_token.sh" in _script(ci[name])
    text = CI_FILE.read_text(encoding="utf-8")
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in text and "service_account_key" not in text


def test_the_audience_matches_the_terraform_provider() -> None:
    terraform = (REPO_ROOT / "deploy" / "terraform" / "variables.tf").read_text(encoding="utf-8")
    assert 'default     = "https://gitlab.com"' in terraform


def test_the_image_reaches_cloud_run_through_artifact_registry(ci: dict[str, Any]) -> None:
    publish, deploy = ci["publish_image"], ci["deploy_cloud_run"]
    assert "$GCP_ARTIFACT_REPOSITORY/afaw-web:$CI_COMMIT_SHA" in _script(publish)
    assert "afaw-web:$CI_COMMIT_SHA" in _script(deploy) and "gcloud run deploy" in _script(deploy)
    assert "publish_image" in deploy["needs"]
    assert "latest" not in _script(publish) + _script(deploy)


def test_monitor_live_fails_when_the_service_does_not_answer(ci: dict[str, Any]) -> None:
    job = ci["monitor_live"]
    assert "scripts.check_live" in _script(job) and "$GCP_SERVICE_URL" in _script(job)
    assert "deploy_cloud_run" in job["needs"]


@pytest.mark.characterization(
    reason="guards a property the pipeline already had: it holds no Google Cloud identifier"
)
def test_no_google_cloud_identifier_is_written_in_the_pipeline() -> None:
    import re

    text = CI_FILE.read_text(encoding="utf-8")
    assert not re.search(r"project-[0-9a-f]{8}-|\d{12}|us-central1", text)


def test_release_creates_a_gitlab_release_with_glab(ci: dict[str, Any]) -> None:
    release = ci["release"]
    assert "gitlab-org/cli" in release["image"]
    assert release["release"]["tag_name"] and release["needs"]


def test_monitor_collects_facts_and_rebuilds_the_dashboard(ci: dict[str, Any]) -> None:
    script = _script(ci["monitor"])
    assert "scripts.collect_facts" in script and "scripts.build_state" in script
    assert "build/" in str(ci["monitor"]["artifacts"]["paths"])


def test_monitor_always_collects_facts_on_gitlab(ci: dict[str, Any]) -> None:
    script = _script(ci["monitor"])
    assert "NOTICE" not in script and "GITHUB_REPOSITORY" not in script
    assert "python -m scripts.collect_facts" in script
    assert "--facts build/facts.json" in script


def test_human_only_files_job_is_a_labelled_weak_control(ci: dict[str, Any]) -> None:
    job = ci["human_only_files"]
    assert job["stage"] == "govern" and "scripts.human_only_files" in _script(job)
    assert "WEAK" in CI_FILE.read_text(encoding="utf-8")


def test_no_secret_is_written_in_the_file() -> None:
    text = CI_FILE.read_text(encoding="utf-8")
    assert "glpat-" not in text and "password:" not in text.lower()
