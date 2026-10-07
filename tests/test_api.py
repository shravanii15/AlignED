"""Tests for the REST API (api/). Uses a small seeded database so results are deterministic."""

import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.main import create_app
from api.security import RateLimiter, key_is_valid

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = {"X-API-Key": "test-key"}
JOB = "Data Engineer. You will write Python and SQL, and use Docker and Git every day on our platform."


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "api.db")
    c = sqlite3.connect(path)
    c.executescript(open(os.path.join(BASE, "database", "schema.sql"), encoding="utf-8").read())
    c.execute("INSERT INTO programs VALUES (1, 'Test University', 'MS Data Science', 'top-ranked', NULL)")
    c.execute("INSERT INTO programs VALUES (2, 'Other College', 'MS Analytics', 'online', NULL)")
    c.execute("INSERT INTO courses (program_id, course_name) VALUES (1, 'Intro'), (1, 'Stats'), (2, 'Basics')")
    c.executemany("INSERT INTO skills VALUES (?, ?, 'ONET', NULL)", [(1, "Python"), (2, "Docker"), (3, "Git")])
    for i in range(10):
        c.execute("INSERT INTO postings (posting_id, source, title) VALUES (?, 'kaggle_sample', 't')", (f"p{i}",))
    c.executemany("INSERT INTO extractions (source_type, source_id, skill_id, method) VALUES ('posting', ?, ?, 'baseline_keyword')",
                  [(f"p{i}", 1) for i in range(8)] + [(f"p{i}", 2) for i in range(3)] + [("p0", 3)])
    c.execute("INSERT INTO role_clusters VALUES (1, 'Data Engineering', 'kmeans', 0.4)")
    c.executemany("INSERT INTO gap_scores (program_id, skill_id, cluster_id, program_coverage_rate, market_demand_rate, gap_value, q_value, test_method) VALUES (1, ?, NULL, 0, ?, ?, 0.001, 'z_test')",
                  [(1, 0.8, 0.8), (2, 0.3, 0.3)])
    c.executemany("INSERT INTO recommendations (program_id, skill_id, cluster_id, gap_value, trend_label, priority_score, priority_tier, rationale) VALUES (1, ?, NULL, ?, 'no clear trend', ?, ?, 'because')",
                  [(1, 0.8, 0.8, "high"), (2, 0.3, 0.3, "medium")])
    c.commit()
    c.close()
    return path


def make_client(db_path, keys=("test-key",), limit=1000):
    settings = Settings(db_path=db_path, api_keys=tuple(keys), rate_limit_per_minute=limit)
    return TestClient(create_app(settings))


@pytest.fixture
def client(db_path):
    return make_client(db_path)


# ---------- ops and security ----------

def test_health_needs_no_key_and_reports_database(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["database"] == "ok"


def test_health_reports_degraded_when_database_missing(tmp_path):
    c = make_client(str(tmp_path / "missing.db"))
    assert c.get("/health").json()["status"] == "degraded"


def test_protected_routes_reject_missing_and_wrong_keys(client):
    assert client.get("/v1/programs").status_code == 401
    assert client.get("/v1/programs", headers={"X-API-Key": "nope"}).status_code == 401


def test_no_configured_keys_fails_closed(db_path):
    c = make_client(db_path, keys=())
    assert c.get("/v1/programs", headers=KEY).status_code == 503


def test_key_comparison_helper():
    assert key_is_valid("abc", ("x", "abc")) and not key_is_valid("ab", ("abc",)) and not key_is_valid(None, ("abc",))


def test_rate_limit_returns_429_with_retry_after(db_path):
    c = make_client(db_path, limit=3)
    assert [c.get("/v1/programs", headers=KEY).status_code for _ in range(3)] == [200, 200, 200]
    blocked = c.get("/v1/programs", headers=KEY)
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) >= 1


def test_rate_limiter_window_expires():
    now = [0.0]
    limiter = RateLimiter(2, window_seconds=60, clock=lambda: now[0])
    assert limiter.check("k")[0] and limiter.check("k")[0] and not limiter.check("k")[0]
    now[0] = 61
    assert limiter.check("k")[0]


def test_every_response_has_a_request_id(client):
    assert client.get("/health").headers["X-Request-ID"]
    assert client.get("/health", headers={"X-Request-ID": "abc123"}).headers["X-Request-ID"] == "abc123"


# ---------- programs ----------

def test_programs_pagination_and_filter(client):
    page = client.get("/v1/programs?limit=1", headers=KEY).json()
    assert page["total"] == 2 and len(page["items"]) == 1
    only = client.get("/v1/programs?university=test", headers=KEY).json()
    assert only["total"] == 1 and only["items"][0]["course_count"] == 2


def test_programs_rejects_bad_paging(client):
    assert client.get("/v1/programs?limit=0", headers=KEY).status_code == 422
    assert client.get("/v1/programs?limit=101", headers=KEY).status_code == 422
    assert client.get("/v1/programs?offset=-1", headers=KEY).status_code == 422


def test_sql_injection_text_is_treated_as_data(client):
    r = client.get("/v1/programs", params={"university": "x' OR '1'='1"}, headers=KEY)
    assert r.status_code == 200 and r.json()["total"] == 0


# ---------- gaps ----------

def test_gaps_are_ordered_by_priority_and_include_evidence(client):
    body = client.get("/v1/programs/1/gaps", headers=KEY).json()
    assert body["scope"] == "overall market" and body["total"] == 2
    assert [g["skill"] for g in body["items"]] == ["Python", "Docker"]
    assert body["items"][0]["priority_tier"] == "high" and body["items"][0]["q_value"] < 0.05


def test_gaps_tier_filter_and_paging(client):
    only = client.get("/v1/programs/1/gaps?tier=medium", headers=KEY).json()
    assert [g["skill"] for g in only["items"]] == ["Docker"]
    second = client.get("/v1/programs/1/gaps?limit=1&offset=1", headers=KEY).json()
    assert second["total"] == 2 and second["items"][0]["skill"] == "Docker"


def test_gaps_unknown_program_cluster_and_tier(client):
    assert client.get("/v1/programs/999/gaps", headers=KEY).status_code == 404
    assert client.get("/v1/programs/1/gaps?cluster_id=99", headers=KEY).status_code == 404
    assert client.get("/v1/programs/1/gaps?tier=urgent", headers=KEY).status_code == 422


def test_gaps_for_known_cluster_with_no_rows_is_empty_not_error(client):
    body = client.get("/v1/programs/1/gaps?cluster_id=1", headers=KEY).json()
    assert body["scope"] == "Data Engineering" and body["total"] == 0


# ---------- match ----------

def test_match_splits_have_and_missing_most_demanded_first(client):
    r = client.post("/v1/match", headers=KEY, json={"job_text": JOB, "my_skills": "I know Python"}).json()
    assert [s["skill"] for s in r["have"]] == ["Python"]
    assert [s["skill"] for s in r["missing"]] == ["Docker", "Git"]  # Docker is asked for more often than Git
    assert r["match_fraction"] == pytest.approx(1 / 3, abs=1e-3)


def test_match_without_skills_has_null_fraction(client):
    r = client.post("/v1/match", headers=KEY, json={"job_text": JOB}).json()
    assert r["match_fraction"] is None and len(r["missing"]) == 3


def test_match_validates_input(client):
    assert client.post("/v1/match", headers=KEY, json={"job_text": "short"}).status_code == 422
    assert client.post("/v1/match", headers=KEY, json={"job_text": "x" * 20_001}).status_code == 422
    assert client.post("/v1/match", headers=KEY, json={}).status_code == 422
    assert client.post("/v1/match", headers=KEY, json={"job_text": "We want someone who enjoys long walks on the beach."}).status_code == 422


def test_database_is_opened_read_only(db_path):
    from api.repository import Repository
    with pytest.raises(sqlite3.OperationalError):
        Repository(db_path)._connect().execute("DELETE FROM programs")


def test_openapi_documents_all_v1_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/health", "/v1/programs", "/v1/programs/{program_id}/gaps", "/v1/clusters", "/v1/match"} <= set(paths)
