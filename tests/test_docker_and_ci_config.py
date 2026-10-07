"""Static checks for the Docker and CI configuration.

Docker itself is not available in the test environment, so these tests catch
the mistakes that would otherwise only appear on the first `docker build`:
files copied by the Dockerfile that do not exist, compose services pointing
at missing build targets, and workflows that no longer parse.
"""

import glob
import os
import re

import yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    return open(os.path.join(BASE, *parts), encoding="utf-8").read()


def test_dockerfile_defines_both_targets():
    targets = re.findall(r"^FROM .* AS (\w+)", _read("Dockerfile"), flags=re.M)
    assert {"dashboard", "pipeline"} <= set(targets)


def test_every_path_the_dockerfile_copies_exists():
    for line in _read("Dockerfile").splitlines():
        if line.startswith("COPY "):
            for source in line.split()[1:-1]:
                assert glob.glob(os.path.join(BASE, source)), f"Dockerfile copies a missing path: {source}"


def test_compose_services_use_real_targets_and_profiles():
    compose = yaml.safe_load(_read("docker-compose.yml"))
    targets = set(re.findall(r"^FROM .* AS (\w+)", _read("Dockerfile"), flags=re.M))
    assert set(compose["services"]) == {"dashboard", "api", "ingest", "rebuild"}
    for name, service in compose["services"].items():
        assert service["build"]["target"] in targets, name
    assert "profiles" not in compose["services"]["dashboard"]  # `docker compose up dashboard` just works
    assert compose["services"]["ingest"]["profiles"] == ["pipeline"]


def test_pipeline_requirements_cover_what_the_pipeline_scripts_import():
    reqs = _read("requirements-pipeline.txt").lower()
    for package in ("requests", "pandas", "scipy", "numpy"):
        assert package in reqs


def test_workflows_parse_and_ci_gates_docker_on_lint_and_tests():
    ci = yaml.safe_load(_read(".github", "workflows", "run_tests.yml"))
    assert set(ci["jobs"]) == {"lint", "test", "docker"}
    assert set(ci["jobs"]["docker"]["needs"]) == {"lint", "test"}
    ingest = yaml.safe_load(_read(".github", "workflows", "fetch_adzuna.yml"))
    assert "ingest" in ingest["jobs"]


def test_secrets_never_get_baked_into_images():
    ignore = _read(".dockerignore").splitlines()
    assert ".env" in ignore


def test_pipeline_image_user_can_write_where_the_pipeline_writes():
    """The rebuild writes under data/gap_analysis; the image runs as a non-root
    user, so the app folder must be owned by that user."""
    pipeline_stage = _read("Dockerfile").split("AS pipeline", 1)[1]
    assert "chown -R aligned" in pipeline_stage
    assert pipeline_stage.index("chown -R aligned") < pipeline_stage.index("USER aligned")


def test_ingestion_workflow_keeps_the_git_tree_clean_before_pulling():
    """`git pull --rebase` fails (exit 128) with uncommitted changes, and the
    ingestion run modifies database/aligned.db. The workflow must save the
    database as an artifact first, then discard the change, then pull."""
    text = _read(".github", "workflows", "fetch_adzuna.yml")
    assert text.index("upload-artifact") < text.index("git checkout -- database/aligned.db") < text.index("git pull --rebase origin main")


def test_api_service_has_its_own_target_healthcheck_and_no_hardcoded_key():
    compose = yaml.safe_load(_read("docker-compose.yml"))
    dockerfile = _read("Dockerfile")
    api_stage = dockerfile.split("AS api", 1)[1].split("\nFROM ", 1)[0]
    assert "HEALTHCHECK" in api_stage and "USER aligned" in api_stage and "api/" in api_stage
    key = str(compose["services"]["api"]["environment"]["ALIGNED_API_KEYS"])
    assert key.startswith("${ALIGNED_API_KEYS"), "the API key must come from the environment, never be written in the file"
