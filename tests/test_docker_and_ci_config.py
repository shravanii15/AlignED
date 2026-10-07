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
    assert set(compose["services"]) == {"dashboard", "ingest", "rebuild"}
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
