"""Structure of .gitlab-ci.yml: nine stages, each with a real job, and the guardrails."""

from __future__ import annotations

import os
import shutil
import subprocess
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


def test_paper_build_compiles_the_pdf_so_nobody_needs_latex_locally(ci: dict[str, Any]) -> None:
    job = ci["paper_build"]
    assert job["stage"] == "govern"
    image = job["image"]["name"] if isinstance(job["image"], dict) else job["image"]
    assert image.startswith("texlive/texlive:TL") and not image.endswith(":latest")
    script = _script(job)
    assert "scripts.rules_to_tex AGENTS.md docs/paper/appendix_rules.tex" in script
    assert script.count("xelatex") >= 2  # twice: the second run resolves the references
    assert "fonts-liberation" in script  # the paper is set in Liberation Sans
    assert "docs/paper/afaw.pdf" in job["artifacts"]["paths"]
    watched = [r["changes"] for r in job["rules"] if "changes" in r]
    paths = " ".join(str(p) for c in watched for p in c["paths"])
    assert "AGENTS.md" in paths and "docs/paper/afaw.tex" in paths and "docs/img" in paths
    # against main, not the previous push: a later push that does not touch the sources still builds
    assert all(c["compare_to"] == "refs/heads/main" for c in watched)


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


def test_merge_guard_runs_last_in_merge_request_pipelines_only(ci: dict[str, Any]) -> None:
    job = ci["merge_guard"]
    assert job["stage"] == "monitor"  # the last stage: it waits for every other job
    assert "python -m scripts.merge_guard" in _script(job)
    assert '--mr "$CI_MERGE_REQUEST_IID"' in _script(job)
    assert [r["if"] for r in job["rules"]] == ['$CI_PIPELINE_SOURCE == "merge_request_event"']
    assert not job.get("allow_failure")
    assert "AFAW_MERGE_TOKEN" not in str(job)  # the token comes from a CI/CD variable, not the file


def test_request_fix_runs_only_after_a_failure_and_with_the_switch_on(
    ci: dict[str, Any],
) -> None:
    job = ci["request_fix"]
    assert job["stage"] == "monitor"  # after every job it may have to read
    assert _script(job).strip() == "python -m scripts.request_fix"
    assert job["rules"] == [{"if": '$AFAW_AUTO_MERGE == "true"', "when": "on_failure"}]
    assert "AFAW_MERGE_TOKEN" not in str(job)  # the token comes from a CI/CD variable


def test_web_data_builds_the_live_views_from_measured_facts(ci: dict[str, Any]) -> None:
    script = _script(ci["web_data"])
    collect = script.index("python -m scripts.collect_facts")
    build = script.index("--out build/web-data/live")
    assert collect < build  # the facts exist before the views are built
    assert "--facts build/facts.json" in script[build:]
    assert "--out build/facts.json" in script[collect:build]


def test_the_deploy_tells_the_service_which_commit_and_release_it_runs(ci: dict[str, Any]) -> None:
    script = _script(ci["deploy_cloud_run"])
    assert "--update-env-vars" in script
    assert "AFAW_COMMIT_SHA=$CI_COMMIT_SHA" in script
    assert "AFAW_RELEASE_TAG=v0.$CI_PIPELINE_IID" in script


def test_the_live_monitor_checks_the_deployed_commit_and_the_pages(ci: dict[str, Any]) -> None:
    script = _script(ci["monitor_live"])
    assert '--expect-sha "$CI_COMMIT_SHA"' in script
    for page in ("/", "/experiments/", "/environment/"):
        assert f"--page {page}" in script


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


def test_the_demo_app_is_packaged_published_and_deployed(ci: dict[str, Any]) -> None:
    package, publish = ci["package_demo_app"], ci["publish_demo_image"]
    deploy = ci["deploy_demo_app"]
    assert package["stage"] == "package" and publish["stage"] == deploy["stage"] == "release"
    assert "src/notes_app/Dockerfile" in _script(package)
    assert "afaw-demo-app:$CI_COMMIT_SHA" in _script(package) + _script(publish)
    assert "publish_demo_image" in deploy["needs"]
    assert "gcloud run deploy" in _script(deploy)
    assert "AFAW_COMMIT_SHA=$CI_COMMIT_SHA" in _script(deploy)
    assert "latest" not in _script(package) + _script(publish) + _script(deploy)
    for name in ("publish_demo_image", "deploy_demo_app"):
        assert ci[name]["id_tokens"]["GITLAB_OIDC_TOKEN"]["aud"] == "https://gitlab.com"
        assert "deploy/gcp_access_token.sh" in _script(ci[name])


def test_the_demo_deploy_proves_the_commit_and_hands_the_url_on(ci: dict[str, Any]) -> None:
    deploy = ci["deploy_demo_app"]
    text = _script(deploy)
    assert "/api/version" in text and "$CI_COMMIT_SHA" in text
    assert "DEMO_APP_URL" in text
    assert "dotenv" in str(deploy["artifacts"]["reports"])


def test_the_demo_app_is_type_checked_and_tested(ci: dict[str, Any]) -> None:
    assert "tests/notes" in _script(ci["tests"])


def test_the_end_to_end_jobs_use_the_pinned_playwright_image(ci: dict[str, Any]) -> None:
    pinned = (REPO_ROOT / "e2e" / "requirements.txt").read_text(encoding="utf-8")
    lines = pinned.splitlines()
    version = next(x.split("==")[1].strip() for x in lines if x.startswith("playwright=="))
    for name in ("e2e_local", "e2e_live"):
        assert ci[name]["image"] == f"mcr.microsoft.com/playwright/python:v{version}-noble"
        assert "pytest e2e" in _script(ci[name])
        assert ci[name]["artifacts"]["when"] == "always"


def test_e2e_local_starts_the_app_and_runs_in_merge_requests(ci: dict[str, Any]) -> None:
    job = ci["e2e_local"]
    assert job["stage"] == "verify"
    assert "uvicorn notes_app.main:app" in _script(job)
    assert "NOTES_URL=http://127.0.0.1" in _script(job)
    assert any("merge_request_event" in str(r) or "changes" in r for r in job["rules"])


def test_e2e_live_runs_after_both_deploys_and_before_request_fix(ci: dict[str, Any]) -> None:
    job = ci["e2e_live"]
    # request_fix reacts to failures of earlier stages: a live test in monitor would not reach it.
    assert STAGES.index(job["stage"]) < STAGES.index(ci["request_fix"]["stage"])
    assert {"deploy_demo_app", "deploy_cloud_run"} <= set(job["needs"])
    text = _script(job)
    assert "NOTES_URL=\"$DEMO_APP_URL\"" in text and "DASHBOARD_URL=\"$GCP_SERVICE_URL\"" in text
    assert job["rules"] == [{"if": "$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH"}]


def test_deploy_jobs_share_one_lock(ci: dict[str, Any]) -> None:
    # A burst of merges starts several pipelines of main; without a lock one deploy overwrites
    # another and the version check of the earlier job sees the later commit (task_106).
    names = ("publish_image", "deploy_cloud_run", "publish_demo_image", "deploy_demo_app")
    groups = {ci[name].get("resource_group") for name in names}
    assert groups == {"deploy"}


def test_telemetry_report_runs_on_main_and_never_blocks(ci: dict[str, Any]) -> None:
    job = ci["telemetry_report"]
    assert job["stage"] == "monitor"
    assert job["rules"] == [{"if": "$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH"}]
    assert job["allow_failure"] is True  # observability never blocks the pipeline
    assert "python -m scripts.telemetry_report" in _script(job)
    assert "build/AFAW_TELEMETRY.md" in str(job["artifacts"]["paths"])
    assert "AFAW_MERGE_TOKEN" not in str(job)


def test_repair_check_reports_on_the_merge_requests_of_the_flow_only(ci: dict[str, Any]) -> None:
    job = ci["repair_check"]
    # Not in the monitor stage: merge_guard waits for that stage and must not see this job pending.
    assert job["stage"] == "govern"
    rule = job["rules"][0]["if"]
    assert "merge_request_event" in rule and r"/^duo\//" in rule
    script = _script(job)
    assert "python -m scripts.repair_check" in script
    assert '--mr "$CI_MERGE_REQUEST_IID"' in script
    # The issue number comes from the merge request description. A space before "#" would start a
    # YAML comment and cut the line, so the pattern must survive the parser whole.
    assert "grep -oE 'Closes[[:space:]]#[0-9]+'" in script
    assert "|| echo" in script  # it reports; a job that did not run here is not a failure
    assert not job.get("allow_failure")
    assert "AFAW_MERGE_TOKEN" not in str(job)


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
@pytest.mark.parametrize(
    ("description", "expected"),
    [("Fix the lint job\n\nCloses #62\n", "62"), ("No issue is named here", "")],
)
def test_repair_check_finds_the_issue_under_the_shell_gitlab_uses(
    ci: dict[str, Any], description: str, expected: str
) -> None:
    # GitLab runs job scripts with errexit and pipefail: grep exits 1 when nothing matches, and that
    # must not turn into a red job.
    line = ci["repair_check"]["script"][0] + '\necho "issue=[$ISSUE]"'
    result = subprocess.run(  # noqa: S603
        [str(shutil.which("bash")), "-e", "-o", "pipefail", "-c", line],
        env={"CI_MERGE_REQUEST_DESCRIPTION": description, "PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert f"issue=[{expected}]" in result.stdout
