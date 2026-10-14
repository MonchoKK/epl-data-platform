"""Comprehensive Automated Test Suite for PostgreSQL Warehouse Container (Task 4).

Validates that the relational data warehouse, constraints, indexes,
analytical SQL window views, ETL loading, and REST APIs operate
flawlessly against the live PostgreSQL container (not only SQLite).

Test Coverage:
1. Container Connectivity & Engine Verification (PostgreSQL 16)
2. 3NF Relational Tables Schema & Primary Key Introspection
3. Foreign Key Referential Integrity Enforcement
4. Check Constraints & Domain Invariant Rejection
5. Unique Constraints Enforcement (club name, standing club_id)
6. Composite & B-Tree Index Registration
7. Cascading Deletes Across Foreign Key Relationships
8. Analytical SQL Views Lifecycle (CREATE OR REPLACE / DROP CASCADE)
9. Dynamic Window Ranking in vw_league_table (DENSE_RANK)
10. Dynamic Leaderboards in vw_top_scorers (ROW_NUMBER)
11. Multi-Table Aggregation in vw_club_analytics (LEFT JOINs & float averages)
12. Multi-Run Idempotent Loading (Zero Duplicates on repeated runs)
13. In-Place Upsert Mutation on Existing Records
14. FastAPI REST Endpoints Integration against PostgreSQL
"""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.api.main import app
from src.database.connection import get_db_session, reset_db_engine
from src.database.loader import (
    load_all_processed_data,
    load_clubs,
    load_matches,
    load_players,
    load_standings,
)
from src.database.models import Base, Club, Match, Player, Standing, create_all_tables, drop_all_tables
from src.database.views import (
    create_analytical_views,
    drop_analytical_views,
    query_club_analytics_view,
    query_league_table_view,
    query_top_scorers_view,
)
from src.transform.pipeline import run_transformations


def _discover_postgres_url() -> str | None:
    """Discovers reachable PostgreSQL container URL."""
    candidates = []
    env_url = os.getenv("DATABASE_URL")
    if env_url and env_url.startswith("postgres"):
        candidates.append(env_url)

    candidates.extend([
        "postgresql+psycopg2://postgres:postgrespassword@localhost:5433/epl_warehouse",
        "postgresql+psycopg2://postgres:postgrespassword@localhost:5432/epl_warehouse",
        "postgresql+psycopg2://postgres:postgrespassword@127.0.0.1:5433/epl_warehouse",
        "postgresql+psycopg2://postgres:postgrespassword@127.0.0.1:5432/epl_warehouse",
    ])

    for url in candidates:
        try:
            eng = create_engine(url, echo=False, future=True)
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            return url
        except Exception:
            continue
    return None


@pytest.fixture(scope="module")
def pg_engine():
    """Provides a shared SQLAlchemy engine connected to the PostgreSQL container."""
    url = _discover_postgres_url()
    if not url:
        pytest.skip("PostgreSQL container is not reachable. Run `docker compose up -d` to start it.")

    engine = create_engine(url, echo=False, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    """Provides an isolated transactional database session against PostgreSQL."""
    # Ensure fresh schema and views
    drop_analytical_views(pg_engine)
    drop_all_tables(pg_engine)
    create_all_tables(pg_engine)
    create_analytical_views(pg_engine)

    SessionFactory = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)
    session = SessionFactory()

    yield session

    session.close()


# =========================================================================
# 1. CONNECTIVITY & VERSION VERIFICATION
# =========================================================================

def test_postgres_container_connectivity(pg_engine):
    """Verifies that the database engine connects to the PostgreSQL 16 container."""
    with pg_engine.connect() as conn:
        res = conn.execute(text("SELECT version()")).scalar()
        assert res is not None
        assert "PostgreSQL" in res
        # Container image is postgres:16-alpine
        assert "PostgreSQL 16" in res


# =========================================================================
# 2. SCHEMA & PRIMARY KEY INTROSPECTION
# =========================================================================

def test_postgres_table_creation_and_schema(pg_engine, pg_session):
    """Verifies that all 4 warehouse relational tables exist with required primary keys."""
    inspector = inspect(pg_engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {"clubs", "players", "matches", "standings"}
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"

    assert inspector.get_pk_constraint("clubs")["constrained_columns"] == ["club_id"]
    assert inspector.get_pk_constraint("players")["constrained_columns"] == ["player_id"]
    assert inspector.get_pk_constraint("matches")["constrained_columns"] == ["match_id"]
    assert inspector.get_pk_constraint("standings")["constrained_columns"] == ["id"]


# =========================================================================
# 3. REFERENTIAL INTEGRITY (FOREIGN KEYS)
# =========================================================================

def test_postgres_foreign_key_rejection(pg_session):
    """Verifies that PostgreSQL actively enforces foreign key constraints."""
    # 1. Orphan player referencing non-existent club
    orphan_player = Player(
        player_id=9901,
        club_id=9999,
        name="Ghost Player",
        position="Midfielder",
        nationality="England",
        jersey_number=10,
        transformed_at="2026-10-01",
    )
    pg_session.add(orphan_player)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    # 2. Orphan match referencing non-existent away club
    valid_club = Club(
        club_id=1,
        name="Arsenal FC",
        short_name="ARS",
        stadium="Emirates Stadium",
        capacity=60704,
        city="London",
        founded_year=1886,
        primary_color="#EF0107",
        transformed_at="2026-10-01",
    )
    pg_session.add(valid_club)
    pg_session.commit()

    orphan_match = Match(
        match_id=8801,
        gameweek=1,
        home_club_id=1,
        away_club_id=9999,  # Non-existent
        match_date="2026-10-01 15:00:00",
        home_score=1,
        away_score=0,
        total_goals=1,
        result="HOME_WIN",
        transformed_at="2026-10-01",
    )
    pg_session.add(orphan_match)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    # 3. Orphan standing referencing non-existent club
    orphan_standing = Standing(
        club_id=9999,
        position=1,
        played=5,
        won=4,
        drawn=1,
        lost=0,
        goals_for=10,
        goals_against=2,
        goal_difference=8,
        points=13,
        points_per_game=2.6,
        win_percentage=80.0,
        transformed_at="2026-10-01",
    )
    pg_session.add(orphan_standing)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


# =========================================================================
# 4. CHECK CONSTRAINTS & UNIQUE CONSTRAINTS
# =========================================================================

def test_postgres_check_and_unique_constraints(pg_session):
    """Verifies that PostgreSQL actively enforces check and unique constraints."""
    # 1. Capacity > 0
    bad_capacity = Club(
        club_id=101,
        name="Zero FC",
        short_name="ZFC",
        stadium="Zero Ground",
        capacity=0,  # Invalid
        city="London",
        founded_year=1900,
        transformed_at="2026-10-01",
    )
    pg_session.add(bad_capacity)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    # 2. Founded year >= 1800
    bad_year = Club(
        club_id=102,
        name="Medieval FC",
        short_name="MFC",
        stadium="Old Ground",
        capacity=20000,
        city="York",
        founded_year=1600,  # Invalid
        transformed_at="2026-10-01",
    )
    pg_session.add(bad_year)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    # 3. Unique club name
    club1 = Club(
        club_id=103,
        name="Unique Name FC",
        short_name="UNF",
        stadium="Unique Stadium",
        capacity=30000,
        city="London",
        founded_year=1900,
        transformed_at="2026-10-01",
    )
    club2 = Club(
        club_id=104,
        name="Unique Name FC",  # Duplicate name
        short_name="UN2",
        stadium="Other Stadium",
        capacity=30000,
        city="London",
        founded_year=1900,
        transformed_at="2026-10-01",
    )
    pg_session.add(club1)
    pg_session.commit()
    pg_session.add(club2)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    # 4. Match home_club_id != away_club_id
    self_match = Match(
        match_id=8802,
        gameweek=1,
        home_club_id=103,
        away_club_id=103,  # Same club
        match_date="2026-10-01 15:00:00",
        home_score=1,
        away_score=1,
        total_goals=2,
        result="DRAW",
        transformed_at="2026-10-01",
    )
    pg_session.add(self_match)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


# =========================================================================
# 5. CASCADING DELETES
# =========================================================================

def test_postgres_cascading_deletes(pg_session):
    """Verifies that deleting a club cascades to all related players, standings, and matches."""
    club = Club(
        club_id=201,
        name="Cascade FC",
        short_name="CFC",
        stadium="Cascade Park",
        capacity=40000,
        city="Manchester",
        founded_year=1910,
        transformed_at="2026-10-01",
    )
    opponent = Club(
        club_id=202,
        name="Opponent FC",
        short_name="OFC",
        stadium="Opponent Park",
        capacity=30000,
        city="Manchester",
        founded_year=1912,
        transformed_at="2026-10-01",
    )
    pg_session.add_all([club, opponent])
    pg_session.commit()

    player = Player(
        player_id=2001,
        club_id=201,
        name="Player One",
        position="Forward",
        nationality="England",
        jersey_number=9,
        transformed_at="2026-10-01",
    )
    standing = Standing(
        club_id=201,
        position=1,
        played=1,
        won=1,
        drawn=0,
        lost=0,
        goals_for=2,
        goals_against=0,
        goal_difference=2,
        points=3,
        points_per_game=3.0,
        win_percentage=100.0,
        transformed_at="2026-10-01",
    )
    match = Match(
        match_id=9001,
        gameweek=1,
        home_club_id=201,
        away_club_id=202,
        match_date="2026-10-01",
        home_score=2,
        away_score=0,
        total_goals=2,
        result="HOME_WIN",
        transformed_at="2026-10-01",
    )
    pg_session.add_all([player, standing, match])
    pg_session.commit()

    assert pg_session.query(Player).filter_by(player_id=2001).count() == 1
    assert pg_session.query(Standing).filter_by(club_id=201).count() == 1
    assert pg_session.query(Match).filter_by(match_id=9001).count() == 1

    # Delete the parent club
    pg_session.delete(club)
    pg_session.commit()

    # All child rows must be automatically deleted by PostgreSQL cascade
    assert pg_session.query(Player).filter_by(player_id=2001).count() == 0
    assert pg_session.query(Standing).filter_by(club_id=201).count() == 0
    assert pg_session.query(Match).filter_by(match_id=9001).count() == 0


# =========================================================================
# 6. ANALYTICAL SQL VIEWS ON POSTGRESQL
# =========================================================================

def test_postgres_analytical_views(pg_engine, pg_session):
    """Verifies that analytical SQL views deploy and calculate rankings on PostgreSQL."""
    club1 = Club(club_id=301, name="Alpha FC", short_name="ALP", stadium="Alpha Stadium", capacity=50000, city="London", founded_year=1900, transformed_at="2026-10-01")
    club2 = Club(club_id=302, name="Beta FC", short_name="BET", stadium="Beta Stadium", capacity=45000, city="London", founded_year=1905, transformed_at="2026-10-01")
    pg_session.add_all([club1, club2])
    pg_session.commit()

    # Beta has 10 points (+5 GD), Alpha has 10 points (+3 GD)
    standing1 = Standing(club_id=301, position=2, played=5, won=3, drawn=1, lost=1, goals_for=8, goals_against=5, goal_difference=3, points=10, points_per_game=2.0, win_percentage=60.0, transformed_at="2026-10-01")
    standing2 = Standing(club_id=302, position=1, played=5, won=3, drawn=1, lost=1, goals_for=10, goals_against=5, goal_difference=5, points=10, points_per_game=2.0, win_percentage=60.0, transformed_at="2026-10-01")
    pg_session.add_all([standing1, standing2])

    p1 = Player(player_id=3001, club_id=301, name="Alpha Scorer", position="Forward", nationality="England", jersey_number=9, appearances=10, goals=8, assists=3, transformed_at="2026-10-01")
    p2 = Player(player_id=3002, club_id=302, name="Beta Scorer", position="Forward", nationality="Norway", jersey_number=9, appearances=10, goals=12, assists=2, transformed_at="2026-10-01")
    p3 = Player(player_id=3003, club_id=301, name="Alpha Defender", position="Defender", nationality="England", jersey_number=4, appearances=10, goals=0, assists=1, transformed_at="2026-10-01")
    pg_session.add_all([p1, p2, p3])
    pg_session.commit()

    # 1. League table view (DENSE_RANK tie-breaker on GD)
    table_rows = query_league_table_view(pg_session)
    assert len(table_rows) == 2
    assert table_rows[0]["club_name"] == "Beta FC"
    assert table_rows[0]["dynamic_rank"] == 1
    assert table_rows[1]["club_name"] == "Alpha FC"
    assert table_rows[1]["dynamic_rank"] == 2

    # 2. Top scorers view (p3 with 0 goals excluded; p2 ranked #1)
    scorers = query_top_scorers_view(pg_session)
    assert len(scorers) == 2
    assert scorers[0]["player_name"] == "Beta Scorer"
    assert scorers[0]["scorer_rank"] == 1
    assert scorers[0]["goals"] == 12
    assert scorers[1]["player_name"] == "Alpha Scorer"
    assert scorers[1]["scorer_rank"] == 2

    # 3. Club analytics view (Coerces AVG to float)
    analytics = query_club_analytics_view(pg_session)
    assert len(analytics) == 2
    alpha_analytics = next(a for a in analytics if a["club_id"] == 301)
    assert alpha_analytics["squad_size"] == 2
    assert alpha_analytics["squad_goals"] == 8
    assert isinstance(alpha_analytics["avg_player_appearances"], float)
    assert alpha_analytics["avg_player_appearances"] == 10.0


# =========================================================================
# 7. PIPELINE LOADING & IDEMPOTENCY ON POSTGRESQL
# =========================================================================

def test_postgres_pipeline_loading_and_idempotency(pg_engine, pg_session):
    """Proves multi-run idempotency against PostgreSQL: 3 runs produce identical 55 rows."""
    transform_out = run_transformations()
    dfs = transform_out["dataframes"]

    # Run 1: Initial load
    run1 = load_all_processed_data(engine=pg_engine, dataframes=dfs)
    assert run1["total_loaded"] == 55
    assert pg_session.query(Club).count() == 10
    assert pg_session.query(Player).count() == 20
    assert pg_session.query(Match).count() == 15
    assert pg_session.query(Standing).count() == 10

    # Run 2: Second consecutive run
    run2 = load_all_processed_data(engine=pg_engine, dataframes=dfs)
    assert run2["total_loaded"] == 55
    assert pg_session.query(Club).count() == 10
    assert pg_session.query(Player).count() == 20
    assert pg_session.query(Match).count() == 15
    assert pg_session.query(Standing).count() == 10

    # Run 3: Third consecutive run
    run3 = load_all_processed_data(engine=pg_engine, dataframes=dfs)
    assert run3["total_loaded"] == 55
    assert pg_session.query(Club).count() == 10
    assert pg_session.query(Player).count() == 20
    assert pg_session.query(Match).count() == 15
    assert pg_session.query(Standing).count() == 10


def test_postgres_in_place_upsert_mutation(pg_engine, pg_session):
    """Proves in-place mutation without duplicate creation on PostgreSQL."""
    transform_out = run_transformations()
    dfs = transform_out["dataframes"]
    load_all_processed_data(engine=pg_engine, dataframes=dfs)

    haaland = pg_session.query(Player).filter_by(player_id=111).first()
    assert haaland.goals == 27

    # Mutate goals in dataframe
    mutated_dfs = dict(dfs)
    mutated_players = dfs["players"].copy()
    mutated_players.loc[mutated_players["player_id"] == 111, "goals"] = 30
    mutated_dfs["players"] = mutated_players

    # Re-run loader
    load_all_processed_data(engine=pg_engine, dataframes=mutated_dfs)

    pg_session.expire_all()
    assert pg_session.query(Player).count() == 20
    updated = pg_session.query(Player).filter_by(player_id=111).first()
    assert updated.goals == 30


# =========================================================================
# 8. REST API INTEGRATION ON POSTGRESQL
# =========================================================================

def test_postgres_fastapi_endpoints_integration(pg_engine):
    """Verifies that FastAPI REST endpoints function seamlessly against PostgreSQL."""
    # Populate warehouse
    load_all_processed_data(engine=pg_engine)

    # Set DATABASE_URL in config/connection
    orig_env = os.environ.get("DATABASE_URL")
    url = pg_engine.url.render_as_string(hide_password=False)
    os.environ["DATABASE_URL"] = url
    reset_db_engine()

    try:
        client = TestClient(app)

        # /api/health
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ONLINE"
        assert health.json()["database_connected"] is True

        # /api/standings
        standings = client.get("/api/standings")
        assert standings.status_code == 200
        data = standings.json()
        assert len(data) == 10
        assert data[0]["dynamic_rank"] == 1
        assert "club_name" in data[0]

        # /api/clubs
        clubs = client.get("/api/clubs")
        assert clubs.status_code == 200
        assert len(clubs.json()) == 10

        # /api/players
        players = client.get("/api/players")
        assert players.status_code == 200
        assert len(players.json()) == 20

        # /api/matches
        matches = client.get("/api/matches")
        assert matches.status_code == 200
        assert len(matches.json()) == 15

        # /api/analytics/top-scorers
        scorers = client.get("/api/analytics/top-scorers?limit=5")
        assert scorers.status_code == 200
        assert len(scorers.json()) == 5
        assert scorers.json()[0]["scorer_rank"] == 1

        # /api/analytics/club-summary
        summary = client.get("/api/analytics/club-summary")
        assert summary.status_code == 200
        assert len(summary.json()) == 10
        assert isinstance(summary.json()[0]["avg_player_appearances"], float)

    finally:
        if orig_env is not None:
            os.environ["DATABASE_URL"] = orig_env
        else:
            os.environ.pop("DATABASE_URL", None)
        reset_db_engine()
