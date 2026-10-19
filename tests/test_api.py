"""Comprehensive Automated REST API Test Suite (Task 5).

Validates all FastAPI serving layer routes, CORS middleware, static asset
mounting, error handling, input validation, and database view integration:
1. Root & Discovery Endpoints (/ and /api/health)
2. Interactive Documentation Endpoints (/docs and /redoc)
3. Data Quality & Audit Report Endpoint (/api/quality)
4. Clubs Dimension Endpoints (/api/clubs and /api/clubs/{club_id})
5. Players Dimension Endpoints (/api/players and /api/players/{player_id})
6. Matches Fact Endpoints (/api/matches with gameweek and club filters)
7. Analytical SQL View Endpoints (/api/standings, /api/analytics/top-scorers, /api/analytics/club-summary)
8. Pipeline Execution Trigger Endpoint (POST /api/pipeline/trigger with success & 500 error cases)
9. CORS Preflight & Frontend Static Mounting
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.config import PROCESSED_DATA_DIR
from src.database.connection import get_db_engine
from src.database.models import create_all_tables
from src.database.views import create_analytical_views
from src.pipeline_runner import run_full_pipeline


@pytest.fixture(scope="session", autouse=True)
def ensure_pipeline_data_and_schema():
    """Ensures database tables, analytical views, and pipeline datasets exist for testing."""
    engine = get_db_engine()
    create_all_tables(engine)
    create_analytical_views(engine)
    # Run the pipeline once to populate warehouse and processed files
    run_full_pipeline()


@pytest.fixture
def client():
    """Provides a TestClient managing the application lifespan."""
    with TestClient(app) as test_client:
        yield test_client


# =========================================================================
# 1. ROOT & PLATFORM HEALTH ENDPOINTS
# =========================================================================

def test_root_endpoint(client):
    """Verifies that GET / returns the platform welcome payload and discovery map."""
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "Welcome to the EPL Club Data Platform API" in data["message"]
    assert data["docs"] == "/docs"
    assert data["frontend"] == "/app/index.html"

    endpoints = data["endpoints"]
    assert "health" in endpoints
    assert "quality" in endpoints
    assert "clubs" in endpoints
    assert "players" in endpoints
    assert "matches" in endpoints
    assert "standings" in endpoints
    assert "top_scorers" in endpoints
    assert "club_summary" in endpoints
    assert "pipeline_trigger" in endpoints


def test_health_endpoint(client):
    """Verifies that GET /api/health returns operational metrics and DB connectivity."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ONLINE", "DEGRADED")
    assert isinstance(data["database_connected"], bool)
    assert data["database_connected"] is True
    assert data["platform"] == "EPL Data Engineering Platform"
    assert "version" in data


def test_docs_endpoints(client):
    """Verifies that FastAPI OpenAPI documentation (/docs, /redoc) serves successfully."""
    resp_docs = client.get("/docs")
    assert resp_docs.status_code == 200
    assert "swagger" in resp_docs.text.lower() or "openapi" in resp_docs.text.lower()

    resp_redoc = client.get("/redoc")
    assert resp_redoc.status_code == 200
    assert "redoc" in resp_redoc.text.lower()


# =========================================================================
# 2. DATA QUALITY AUDIT ENDPOINT
# =========================================================================

def test_quality_report_endpoint_success(client):
    """Verifies that GET /api/quality returns the latest data quality audit report."""
    resp = client.get("/api/quality")
    assert resp.status_code == 200
    data = resp.json()
    assert "timestamp" in data
    assert "source_records" in data
    assert "processed_records" in data
    assert "status" in data
    assert data["status"] == "PASS"
    assert data["source_records"] == 55
    assert data["processed_records"] == 55
    assert data["rejected_records"] == 0
    assert data["missing_fields"] == 0
    assert data["duplicates"] == 0
    assert "dataset_details" in data
    assert "clubs" in data["dataset_details"]
    assert "players" in data["dataset_details"]
    assert "matches" in data["dataset_details"]
    assert "standings" in data["dataset_details"]


def test_quality_report_endpoint_missing(client, monkeypatch, tmp_path):
    """Verifies that GET /api/quality returns 404 when quality_report.json does not exist."""
    non_existent = tmp_path / "non_existent_report.json"
    with patch("src.config.PROCESSED_DATA_DIR", tmp_path):
        resp = client.get("/api/quality")
        assert resp.status_code == 404
        assert "Quality report has not been generated yet" in resp.json()["detail"]


# =========================================================================
# 3. CLUBS ENDPOINTS
# =========================================================================

def test_get_clubs_all(client):
    """Verifies that GET /api/clubs returns all Premier League clubs sorted by name."""
    resp = client.get("/api/clubs")
    assert resp.status_code == 200
    clubs = resp.json()
    assert isinstance(clubs, list)
    assert len(clubs) == 10

    # Verify club schema fields
    first = clubs[0]
    assert "club_id" in first
    assert "name" in first
    assert "short_name" in first
    assert "stadium" in first
    assert "capacity" in first
    assert "city" in first
    assert "founded_year" in first

    # Verify alphabetical sorting by club name
    names = [c["name"] for c in clubs]
    assert names == sorted(names)


def test_get_clubs_filter_city(client):
    """Verifies that GET /api/clubs?city=London filters clubs by city name."""
    resp = client.get("/api/clubs?city=London")
    assert resp.status_code == 200
    clubs = resp.json()
    assert len(clubs) > 0
    for club in clubs:
        assert club["city"] == "London"

    club_names = [c["name"] for c in clubs]
    assert "Arsenal FC" in club_names
    assert "Chelsea FC" in club_names


def test_get_clubs_filter_city_no_match(client):
    """Verifies that GET /api/clubs with a non-matching city returns an empty list."""
    resp = client.get("/api/clubs?city=Atlantis")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_club_detail_valid(client):
    """Verifies that GET /api/clubs/{club_id} returns club details, squad, standing, and matches."""
    resp = client.get("/api/clubs/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["club_id"] == 1
    assert data["name"] == "Arsenal FC"
    assert "squad" in data
    assert "squad_count" in data
    assert isinstance(data["squad"], list)
    assert data["squad_count"] == len(data["squad"])
    assert data["standing"] is not None
    assert "points" in data["standing"]
    assert "matches" in data
    assert isinstance(data["matches"], list)


def test_get_club_detail_not_found(client):
    """Verifies that GET /api/clubs/{club_id} returns 404 for non-existent club ID."""
    resp = client.get("/api/clubs/99999")
    assert resp.status_code == 404
    assert "Club ID 99999 not found" in resp.json()["detail"]


# =========================================================================
# 4. PLAYERS ENDPOINTS
# =========================================================================

def test_get_players_all(client):
    """Verifies that GET /api/players returns players ordered by goals and assists."""
    resp = client.get("/api/players")
    assert resp.status_code == 200
    players = resp.json()
    assert isinstance(players, list)
    assert len(players) == 20

    first = players[0]
    assert "player_id" in first
    assert "name" in first
    assert "position" in first
    assert "goals" in first
    assert "assists" in first
    assert "appearances" in first

    # Verify descending ordering by goals
    assert players[0]["goals"] >= players[1]["goals"]


def test_get_players_filter_club(client):
    """Verifies that GET /api/players?club_id=2 filters players belonging to Man City."""
    resp = client.get("/api/players?club_id=2")
    assert resp.status_code == 200
    players = resp.json()
    assert len(players) > 0
    assert all(p["club_id"] == 2 for p in players)


def test_get_players_filter_position(client):
    """Verifies that GET /api/players?position=Forward filters forwards."""
    resp = client.get("/api/players?position=Forward")
    assert resp.status_code == 200
    players = resp.json()
    assert len(players) > 0
    assert all("Forward" in p["position"] for p in players)


def test_get_players_search_name(client):
    """Verifies that GET /api/players?search=Haaland performs case-insensitive name matching."""
    resp = client.get("/api/players?search=haaland")
    assert resp.status_code == 200
    players = resp.json()
    assert len(players) == 1
    assert players[0]["name"] == "Erling Haaland"


def test_get_players_limit_pagination(client):
    """Verifies that GET /api/players?limit=5 limits result size."""
    resp = client.get("/api/players?limit=5")
    assert resp.status_code == 200
    players = resp.json()
    assert len(players) == 5


def test_get_players_invalid_limit(client):
    """Verifies that GET /api/players with limit outside [1, 100] returns 422."""
    resp_zero = client.get("/api/players?limit=0")
    assert resp_zero.status_code == 422

    resp_too_high = client.get("/api/players?limit=101")
    assert resp_too_high.status_code == 422


def test_get_player_detail_valid(client):
    """Verifies that GET /api/players/{player_id} returns single player statistics."""
    resp = client.get("/api/players/111")
    assert resp.status_code == 200
    player = resp.json()
    assert player["player_id"] == 111
    assert player["name"] == "Erling Haaland"
    assert player["position"] == "Forward"
    assert player["goals"] == 27
    assert player["appearances"] == 31


def test_get_player_detail_not_found(client):
    """Verifies that GET /api/players/{player_id} returns 404 for unknown player."""
    resp = client.get("/api/players/99999")
    assert resp.status_code == 404
    assert "Player ID 99999 not found" in resp.json()["detail"]


# =========================================================================
# 5. MATCHES ENDPOINTS
# =========================================================================

def test_get_matches_all(client):
    """Verifies that GET /api/matches returns all fixtures with home/away team details."""
    resp = client.get("/api/matches")
    assert resp.status_code == 200
    matches = resp.json()
    assert isinstance(matches, list)
    assert len(matches) == 15

    first = matches[0]
    assert "match_id" in first
    assert "gameweek" in first
    assert "home_club_id" in first
    assert "away_club_id" in first
    assert "home_score" in first
    assert "away_score" in first
    assert "home_club_name" in first
    assert "away_club_name" in first


def test_get_matches_filter_gameweek(client):
    """Verifies that GET /api/matches?gameweek=1 returns only Gameweek 1 fixtures."""
    resp = client.get("/api/matches?gameweek=1")
    assert resp.status_code == 200
    matches = resp.json()
    assert len(matches) > 0
    assert all(m["gameweek"] == 1 for m in matches)


def test_get_matches_filter_club(client):
    """Verifies that GET /api/matches?club_id=1 returns matches where club played home or away."""
    resp = client.get("/api/matches?club_id=1")
    assert resp.status_code == 200
    matches = resp.json()
    assert len(matches) > 0
    for m in matches:
        assert m["home_club_id"] == 1 or m["away_club_id"] == 1


def test_get_matches_filter_gameweek_no_matches(client):
    """Verifies that GET /api/matches?gameweek=99 returns empty list."""
    resp = client.get("/api/matches?gameweek=99")
    assert resp.status_code == 200
    assert resp.json() == []


# =========================================================================
# 6. ANALYTICAL SQL VIEW ENDPOINTS
# =========================================================================

def test_standings_endpoint(client):
    """Verifies that GET /api/standings returns data from vw_league_table."""
    resp = client.get("/api/standings")
    assert resp.status_code == 200
    table = resp.json()
    assert isinstance(table, list)
    assert len(table) == 10

    leader = table[0]
    assert leader["dynamic_rank"] == 1
    assert "club_name" in leader
    assert "points" in leader
    assert "goal_difference" in leader
    assert "form" in leader

    # Ranks should be 1 to 10
    ranks = [row["dynamic_rank"] for row in table]
    assert ranks == list(range(1, 11))


def test_top_scorers_endpoint(client):
    """Verifies that GET /api/analytics/top-scorers returns data from vw_top_scorers."""
    resp = client.get("/api/analytics/top-scorers?limit=5")
    assert resp.status_code == 200
    scorers = resp.json()
    assert isinstance(scorers, list)
    assert len(scorers) == 5

    first = scorers[0]
    assert first["scorer_rank"] == 1
    assert first["player_name"] == "Erling Haaland"
    assert first["goals"] == 27
    assert all(s["goals"] > 0 for s in scorers)


def test_top_scorers_invalid_limit(client):
    """Verifies that GET /api/analytics/top-scorers with invalid limit returns 422."""
    resp = client.get("/api/analytics/top-scorers?limit=0")
    assert resp.status_code == 422


def test_club_summary_endpoint(client):
    """Verifies that GET /api/analytics/club-summary returns data from vw_club_analytics."""
    resp = client.get("/api/analytics/club-summary")
    assert resp.status_code == 200
    summary = resp.json()
    assert isinstance(summary, list)
    assert len(summary) == 10

    first = summary[0]
    assert "club_name" in first
    assert "squad_size" in first
    assert "squad_goals" in first
    assert "squad_assists" in first
    assert "avg_player_appearances" in first
    assert "capacity" in first


# =========================================================================
# 7. PIPELINE TRIGGER ENDPOINT
# =========================================================================

def test_pipeline_trigger_success(client):
    """Verifies that POST /api/pipeline/trigger executes the full ELT pipeline."""
    resp = client.post("/api/pipeline/trigger")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    report = data["report"]
    assert "execution_timestamp" in report
    assert "elapsed_seconds" in report
    assert "ingestion" in report
    assert "transformation" in report
    assert "loader" in report
    assert report["ingestion"]["total_records"] == 55
    assert report["loader"]["total_loaded"] == 55


def test_pipeline_trigger_failure_handles_exception(client):
    """Verifies that POST /api/pipeline/trigger handles exceptions and returns 500 error."""
    with patch("src.api.routes.run_full_pipeline", side_effect=RuntimeError("Simulated pipeline failure")):
        resp = client.post("/api/pipeline/trigger")
        assert resp.status_code == 500
        data = resp.json()
        assert "Pipeline execution failed: Simulated pipeline failure" in data["detail"]


# =========================================================================
# 8. CORS PREFLIGHT & STATIC FRONTEND SERVING
# =========================================================================

def test_cors_headers(client):
    """Verifies CORS middleware sets Allow-Origin header for browser cross-origin requests."""
    resp = client.options(
        "/api/clubs",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Under Starlette/FastAPI with allow_credentials=True, server reflects allowed origin
    assert resp.headers.get("access-control-allow-origin") in ("*", "http://localhost:3000")


def test_frontend_static_serving(client):
    """Verifies that the mounted frontend static directory serves index.html and styles.css."""
    resp_index = client.get("/app/index.html")
    assert resp_index.status_code == 200
    assert "<title>EPL Club Data Platform" in resp_index.text

    resp_css = client.get("/app/styles.css")
    assert resp_css.status_code == 200
    assert "css" in resp_css.headers.get("content-type", "").lower()
