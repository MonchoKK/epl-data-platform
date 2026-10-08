"""Unit & Integration Test Suite for Analytical SQL Views (Task 3).

Comprehensive testing for all 3 analytical SQL database views:
1. vw_league_table
   - Window function ranking via DENSE_RANK()
   - Multi-criteria tie-breaking hierarchy (points -> GD -> GF -> GA)
   - Absolute tie handling without rank gaps (DENSE_RANK behavior)
   - Negative goal difference ordering in relegation scenarios
   - Inner join semantics & empty table handling
   - Dynamic view re-computation on standings update

2. vw_top_scorers
   - Window function ranking via ROW_NUMBER()
   - Strict exclusion of non-scorers (WHERE p.goals > 0)
   - Golden boot tie-breaking rules (goals -> assists -> fewest appearances)
   - Unique sequential row numbers even for tied statistics
   - Parameterized query row limiting (LIMIT :limit)
   - Dynamic view recalculation on player statistics update

3. vw_club_analytics
   - Multi-table LEFT JOIN across clubs, players, and standings
   - Squad aggregation accuracy: COUNT(DISTINCT), SUM(goals), SUM(assists), ROUND(AVG(appearances), 1)
   - LEFT JOIN resilience: clubs with 0 players, clubs with no standings, isolated clubs
   - Ascending league position ordering
   - Dynamic squad recalculation upon player transfers and updates

4. View Lifecycle & Management
   - Idempotent view deployment (CREATE VIEW IF NOT EXISTS)
   - Clean view removal (DROP VIEW IF EXISTS)
   - View re-creation and recovery

5. Full Pipeline & API Integration
   - Real test warehouse dataset verification
   - FastAPI REST API endpoints integration (/api/standings, /api/analytics/top-scorers, /api/analytics/club-summary)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from src.api.main import app
from src.database.connection import get_db_engine, get_db_session
from src.database.loader import load_all_processed_data
from src.database.models import Club, Player, Standing, create_all_tables
from src.database.views import (
    create_analytical_views,
    drop_analytical_views,
    query_club_analytics_view,
    query_league_table_view,
    query_top_scorers_view,
)
from src.transform.pipeline import run_transformations


# =========================================================================
# TEST FIXTURES
# =========================================================================

@pytest.fixture
def view_db():
    """Provides an isolated in-memory SQLite database with foreign keys enabled,

    relational tables initialized, and analytical views deployed.
    """
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    create_all_tables(engine)
    create_analytical_views(engine)

    SessionFactory = sessionmaker(bind=engine)
    session = SessionFactory()

    yield engine, session

    session.close()


def _create_sample_club(session: Session, club_id: int, name: str, short_name: str) -> Club:
    """Helper to create and persist a valid club."""
    club = Club(
        club_id=club_id,
        name=name,
        short_name=short_name,
        stadium=f"{name} Stadium",
        capacity=50000,
        city="London",
        founded_year=1900,
        primary_color="#1E293B",
        transformed_at="2026-10-01T00:00:00Z",
    )
    session.add(club)
    session.commit()
    return club


# =========================================================================
# 1. TESTS FOR vw_league_table
# =========================================================================

def test_league_table_schema_and_columns(view_db):
    """Verifies that vw_league_table projects all expected columns with correct metadata."""
    _, session = view_db
    club = _create_sample_club(session, club_id=1, name="Arsenal FC", short_name="ARS")

    standing = Standing(
        club_id=1,
        position=1,
        played=10,
        won=8,
        drawn=1,
        lost=1,
        goals_for=24,
        goals_against=8,
        goal_difference=16,
        points=25,
        points_per_game=2.5,
        win_percentage=80.0,
        form="W-W-W-D-W",
        transformed_at="2026-10-01T00:00:00Z",
    )
    session.add(standing)
    session.commit()

    rows = query_league_table_view(session)
    assert len(rows) == 1
    row = rows[0]

    expected_fields = {
        "dynamic_rank",
        "club_id",
        "club_name",
        "short_name",
        "stadium",
        "primary_color",
        "played",
        "won",
        "drawn",
        "lost",
        "goals_for",
        "goals_against",
        "goal_difference",
        "points",
        "points_per_game",
        "win_percentage",
        "form",
    }
    assert expected_fields.issubset(set(row.keys()))
    assert row["dynamic_rank"] == 1
    assert row["club_name"] == "Arsenal FC"
    assert row["short_name"] == "ARS"
    assert row["stadium"] == "Arsenal FC Stadium"
    assert row["points"] == 25
    assert row["goal_difference"] == 16
    assert row["win_percentage"] == 80.0
    assert row["form"] == "W-W-W-D-W"


def test_league_table_points_ranking(view_db):
    """Verifies that teams are ranked strictly in descending order of total points."""
    _, session = view_db
    _create_sample_club(session, 1, "Arsenal FC", "ARS")
    _create_sample_club(session, 2, "Chelsea FC", "CHE")
    _create_sample_club(session, 3, "Liverpool FC", "LIV")

    # Chelsea (25 pts), Arsenal (20 pts), Liverpool (15 pts)
    session.add_all([
        Standing(club_id=1, position=2, played=10, won=6, drawn=2, lost=2, goals_for=18, goals_against=10, goal_difference=8, points=20, points_per_game=2.0, win_percentage=60.0, transformed_at="2026-10-01"),
        Standing(club_id=2, position=1, played=10, won=8, drawn=1, lost=1, goals_for=22, goals_against=7, goal_difference=15, points=25, points_per_game=2.5, win_percentage=80.0, transformed_at="2026-10-01"),
        Standing(club_id=3, position=3, played=10, won=4, drawn=3, lost=3, goals_for=14, goals_against=12, goal_difference=2, points=15, points_per_game=1.5, win_percentage=40.0, transformed_at="2026-10-01"),
    ])
    session.commit()

    rows = query_league_table_view(session)
    assert len(rows) == 3

    assert [r["dynamic_rank"] for r in rows] == [1, 2, 3]
    assert [r["club_id"] for r in rows] == [2, 1, 3]
    assert [r["short_name"] for r in rows] == ["CHE", "ARS", "LIV"]
    assert [r["points"] for r in rows] == [25, 20, 15]


def test_league_table_tie_breaker_goal_difference(view_db):
    """Verifies Tie-Breaker 1: When points are equal, team with superior goal difference ranks higher."""
    _, session = view_db
    _create_sample_club(session, 1, "Club High GD", "HGD")
    _create_sample_club(session, 2, "Club Low GD", "LGD")

    # Both have 20 points, but HGD has +10 GD vs LGD +4 GD
    session.add_all([
        Standing(club_id=1, position=1, played=10, won=6, drawn=2, lost=2, goals_for=20, goals_against=10, goal_difference=10, points=20, points_per_game=2.0, win_percentage=60.0, transformed_at="2026-10-01"),
        Standing(club_id=2, position=2, played=10, won=6, drawn=2, lost=2, goals_for=16, goals_against=12, goal_difference=4, points=20, points_per_game=2.0, win_percentage=60.0, transformed_at="2026-10-01"),
    ])
    session.commit()

    rows = query_league_table_view(session)
    assert len(rows) == 2
    assert rows[0]["short_name"] == "HGD"
    assert rows[0]["dynamic_rank"] == 1
    assert rows[1]["short_name"] == "LGD"
    assert rows[1]["dynamic_rank"] == 2


def test_league_table_tie_breaker_goals_for(view_db):
    """Verifies Tie-Breaker 2: When points AND goal difference are equal, team with more goals scored ranks higher."""
    _, session = view_db
    _create_sample_club(session, 1, "Attack Heavy FC", "ATT")
    _create_sample_club(session, 2, "Defensive FC", "DEF")

    # Both have 20 points and GD of +5
    # ATT: 25 goals for, 20 goals against (+5 GD)
    # DEF: 15 goals for, 10 goals against (+5 GD)
    session.add_all([
        Standing(club_id=1, position=1, played=10, won=6, drawn=2, lost=2, goals_for=25, goals_against=20, goal_difference=5, points=20, points_per_game=2.0, win_percentage=60.0, transformed_at="2026-10-01"),
        Standing(club_id=2, position=2, played=10, won=6, drawn=2, lost=2, goals_for=15, goals_against=10, goal_difference=5, points=20, points_per_game=2.0, win_percentage=60.0, transformed_at="2026-10-01"),
    ])
    session.commit()

    rows = query_league_table_view(session)
    assert len(rows) == 2
    assert rows[0]["short_name"] == "ATT"
    assert rows[0]["dynamic_rank"] == 1
    assert rows[0]["goals_for"] == 25
    assert rows[1]["short_name"] == "DEF"
    assert rows[1]["dynamic_rank"] == 2
    assert rows[1]["goals_for"] == 15


def test_league_table_absolute_tie_dense_rank_behavior(view_db):
    """Verifies DENSE_RANK() behavior:

    1. Teams completely tied across all 4 criteria receive the SAME rank.
    2. The subsequent team receives the immediate next rank (no rank skipping).
    """
    _, session = view_db
    _create_sample_club(session, 1, "Twin Club Alpha", "TCA")
    _create_sample_club(session, 2, "Twin Club Beta", "TCB")
    _create_sample_club(session, 3, "Chaser Club", "CHA")

    # TCA and TCB have identical points (18), GD (+6), GF (20), GA (14)
    # CHA has 15 points
    session.add_all([
        Standing(club_id=1, position=1, played=10, won=5, drawn=3, lost=2, goals_for=20, goals_against=14, goal_difference=6, points=18, points_per_game=1.8, win_percentage=50.0, transformed_at="2026-10-01"),
        Standing(club_id=2, position=2, played=10, won=5, drawn=3, lost=2, goals_for=20, goals_against=14, goal_difference=6, points=18, points_per_game=1.8, win_percentage=50.0, transformed_at="2026-10-01"),
        Standing(club_id=3, position=3, played=10, won=4, drawn=3, lost=3, goals_for=16, goals_against=12, goal_difference=4, points=15, points_per_game=1.5, win_percentage=40.0, transformed_at="2026-10-01"),
    ])
    session.commit()

    rows = query_league_table_view(session)
    assert len(rows) == 3

    # Both tied clubs get dynamic_rank 1
    assert rows[0]["dynamic_rank"] == 1
    assert rows[1]["dynamic_rank"] == 1
    tied_names = {rows[0]["short_name"], rows[1]["short_name"]}
    assert tied_names == {"TCA", "TCB"}

    # DENSE_RANK must award rank 2 to the third team (unlike regular RANK which would produce 3)
    assert rows[2]["short_name"] == "CHA"
    assert rows[2]["dynamic_rank"] == 2


def test_league_table_negative_goal_difference(view_db):
    """Verifies that relegation zone ranking correctly handles negative signed goal differences."""
    _, session = view_db
    _create_sample_club(session, 1, "Relegation A", "RGA")
    _create_sample_club(session, 2, "Relegation B", "RGB")

    # Both have 6 points:
    # RGA has GD -3 (goals_for=8, goals_against=11)
    # RGB has GD -12 (goals_for=4, goals_against=16)
    # -3 is greater than -12, so RGA must be ranked higher
    session.add_all([
        Standing(club_id=1, position=1, played=10, won=1, drawn=3, lost=6, goals_for=8, goals_against=11, goal_difference=-3, points=6, points_per_game=0.6, win_percentage=10.0, transformed_at="2026-10-01"),
        Standing(club_id=2, position=2, played=10, won=1, drawn=3, lost=6, goals_for=4, goals_against=16, goal_difference=-12, points=6, points_per_game=0.6, win_percentage=10.0, transformed_at="2026-10-01"),
    ])
    session.commit()

    rows = query_league_table_view(session)
    assert len(rows) == 2
    assert rows[0]["short_name"] == "RGA"
    assert rows[0]["dynamic_rank"] == 1
    assert rows[1]["short_name"] == "RGB"
    assert rows[1]["dynamic_rank"] == 2


def test_league_table_inner_join_semantics(view_db):
    """Verifies inner join semantics: clubs with no standings entries are excluded,

    and an empty standings table produces an empty result list.
    """
    _, session = view_db
    _create_sample_club(session, 1, "Unranked Club A", "UA")
    _create_sample_club(session, 2, "Unranked Club B", "UB")

    # Clubs exist in DB but no standings records
    rows = query_league_table_view(session)
    assert rows == []

    # Add standing for Club 1 only
    session.add(
        Standing(club_id=1, position=1, played=1, won=1, drawn=0, lost=0, goals_for=2, goals_against=0, goal_difference=2, points=3, points_per_game=3.0, win_percentage=100.0, transformed_at="2026-10-01")
    )
    session.commit()

    rows_after = query_league_table_view(session)
    assert len(rows_after) == 1
    assert rows_after[0]["club_id"] == 1


def test_league_table_dynamic_recalculation(view_db):
    """Verifies that vw_league_table is a true dynamic SQL view:

    modifying underlying standings records immediately recalculates dynamic_rank without reloading.
    """
    _, session = view_db
    _create_sample_club(session, 1, "Arsenal FC", "ARS")
    _create_sample_club(session, 2, "Manchester City", "MCI")

    standing_ars = Standing(club_id=1, position=1, played=5, won=4, drawn=0, lost=1, goals_for=10, goals_against=3, goal_difference=7, points=12, points_per_game=2.4, win_percentage=80.0, transformed_at="2026-10-01")
    standing_mci = Standing(club_id=2, position=2, played=5, won=3, drawn=1, lost=1, goals_for=8, goals_against=4, goal_difference=4, points=10, points_per_game=2.0, win_percentage=60.0, transformed_at="2026-10-01")
    session.add_all([standing_ars, standing_mci])
    session.commit()

    initial = query_league_table_view(session)
    assert initial[0]["short_name"] == "ARS"
    assert initial[0]["dynamic_rank"] == 1
    assert initial[1]["short_name"] == "MCI"
    assert initial[1]["dynamic_rank"] == 2

    # Update Manchester City's points so they overtake Arsenal
    standing_mci.points = 15
    standing_mci.goal_difference = 10
    session.commit()

    updated = query_league_table_view(session)
    assert updated[0]["short_name"] == "MCI"
    assert updated[0]["dynamic_rank"] == 1
    assert updated[1]["short_name"] == "ARS"
    assert updated[1]["dynamic_rank"] == 2


# =========================================================================
# 2. TESTS FOR vw_top_scorers
# =========================================================================

def test_top_scorers_schema_and_columns(view_db):
    """Verifies that vw_top_scorers projects all expected columns and joins club metadata."""
    _, session = view_db
    _create_sample_club(session, 1, "Manchester City", "MCI")

    player = Player(
        player_id=101,
        club_id=1,
        name="Erling Haaland",
        position="Forward",
        nationality="Norway",
        jersey_number=9,
        appearances=28,
        goals=25,
        assists=5,
        goal_contributions=30,
        goals_per_game=0.89,
        transformed_at="2026-10-01T00:00:00Z",
    )
    session.add(player)
    session.commit()

    rows = query_top_scorers_view(session)
    assert len(rows) == 1
    row = rows[0]

    expected_fields = {
        "scorer_rank",
        "player_id",
        "player_name",
        "club_name",
        "club_short_name",
        "club_color",
        "position",
        "nationality",
        "jersey_number",
        "appearances",
        "goals",
        "assists",
        "goal_contributions",
        "goals_per_game",
    }
    assert expected_fields.issubset(set(row.keys()))
    assert row["scorer_rank"] == 1
    assert row["player_name"] == "Erling Haaland"
    assert row["club_name"] == "Manchester City"
    assert row["club_short_name"] == "MCI"
    assert row["goals"] == 25
    assert row["assists"] == 5
    assert row["goal_contributions"] == 30


def test_top_scorers_filter_excludes_zero_goals(view_db):
    """Verifies the WHERE p.goals > 0 clause strictly filters out goalkeepers, defenders, and non-scorers."""
    _, session = view_db
    _create_sample_club(session, 1, "Arsenal FC", "ARS")

    session.add_all([
        Player(player_id=101, club_id=1, name="David Raya", position="Goalkeeper", nationality="Spain", jersey_number=22, appearances=30, goals=0, assists=0, transformed_at="2026-10-01"),
        Player(player_id=102, club_id=1, name="William Saliba", position="Defender", nationality="France", jersey_number=2, appearances=32, goals=0, assists=1, transformed_at="2026-10-01"),
        Player(player_id=103, club_id=1, name="Bukayo Saka", position="Forward", nationality="England", jersey_number=7, appearances=30, goals=15, assists=9, transformed_at="2026-10-01"),
    ])
    session.commit()

    rows = query_top_scorers_view(session)
    # Only Bukayo Saka (goals=15) must appear; 0-goal players must be omitted
    assert len(rows) == 1
    assert rows[0]["player_name"] == "Bukayo Saka"
    assert rows[0]["goals"] == 15


def test_top_scorers_empty_when_all_goals_zero(view_db):
    """Verifies that if no players have scored goals, vw_top_scorers returns an empty list."""
    _, session = view_db
    _create_sample_club(session, 1, "Defenders FC", "DFC")

    session.add_all([
        Player(player_id=1, club_id=1, name="Keeper", position="Goalkeeper", nationality="Test", jersey_number=1, appearances=10, goals=0, assists=0, transformed_at="2026-10-01"),
        Player(player_id=2, club_id=1, name="Back", position="Defender", nationality="Test", jersey_number=4, appearances=10, goals=0, assists=0, transformed_at="2026-10-01"),
    ])
    session.commit()

    rows = query_top_scorers_view(session)
    assert rows == []


def test_top_scorers_tie_breaker_assists(view_db):
    """Verifies Golden Boot Tie-Breaker 1: When goals are equal, player with more assists ranks higher."""
    _, session = view_db
    _create_sample_club(session, 1, "Test FC", "TFC")

    # Both scored 15 goals. Player A has 10 assists, Player B has 4 assists.
    session.add_all([
        Player(player_id=101, club_id=1, name="Player Playmaker", position="Forward", nationality="Test", jersey_number=10, appearances=25, goals=15, assists=10, transformed_at="2026-10-01"),
        Player(player_id=102, club_id=1, name="Player Finisher", position="Forward", nationality="Test", jersey_number=9, appearances=25, goals=15, assists=4, transformed_at="2026-10-01"),
    ])
    session.commit()

    rows = query_top_scorers_view(session)
    assert len(rows) == 2
    assert rows[0]["player_name"] == "Player Playmaker"
    assert rows[0]["scorer_rank"] == 1
    assert rows[0]["assists"] == 10
    assert rows[1]["player_name"] == "Player Finisher"
    assert rows[1]["scorer_rank"] == 2
    assert rows[1]["assists"] == 4


def test_top_scorers_tie_breaker_appearances_efficiency(view_db):
    """Verifies Golden Boot Tie-Breaker 2: When goals and assists are tied,

    player with fewer appearances (higher scoring efficiency) ranks higher.
    """
    _, session = view_db
    _create_sample_club(session, 1, "Test FC", "TFC")

    # Both scored 12 goals and have 6 assists.
    # Player Efficient played 18 games. Player Durable played 32 games.
    session.add_all([
        Player(player_id=101, club_id=1, name="Player Efficient", position="Forward", nationality="Test", jersey_number=11, appearances=18, goals=12, assists=6, transformed_at="2026-10-01"),
        Player(player_id=102, club_id=1, name="Player Durable", position="Forward", nationality="Test", jersey_number=7, appearances=32, goals=12, assists=6, transformed_at="2026-10-01"),
    ])
    session.commit()

    rows = query_top_scorers_view(session)
    assert len(rows) == 2
    assert rows[0]["player_name"] == "Player Efficient"
    assert rows[0]["scorer_rank"] == 1
    assert rows[0]["appearances"] == 18
    assert rows[1]["player_name"] == "Player Durable"
    assert rows[1]["scorer_rank"] == 2
    assert rows[1]["appearances"] == 32


def test_top_scorers_row_number_uniqueness(view_db):
    """Verifies ROW_NUMBER() ensures unique, sequential ranks without duplicate values even on full ties."""
    _, session = view_db
    _create_sample_club(session, 1, "Test FC", "TFC")

    # Identical stats across goals (10), assists (2), appearances (20)
    session.add_all([
        Player(player_id=101, club_id=1, name="Twin Striker 1", position="Forward", nationality="Test", jersey_number=9, appearances=20, goals=10, assists=2, transformed_at="2026-10-01"),
        Player(player_id=102, club_id=1, name="Twin Striker 2", position="Forward", nationality="Test", jersey_number=19, appearances=20, goals=10, assists=2, transformed_at="2026-10-01"),
    ])
    session.commit()

    rows = query_top_scorers_view(session)
    assert len(rows) == 2
    ranks = [r["scorer_rank"] for r in rows]
    # ROW_NUMBER must guarantee distinct [1, 2], not [1, 1]
    assert ranks == [1, 2]


def test_top_scorers_limit_parameter(view_db):
    """Verifies that query_top_scorers_view respects the limit parameter."""
    _, session = view_db
    _create_sample_club(session, 1, "Test FC", "TFC")

    for i in range(1, 8):
        session.add(
            Player(player_id=100 + i, club_id=1, name=f"Scorer {i}", position="Forward", nationality="Test", jersey_number=i, appearances=20, goals=i * 2, assists=i, transformed_at="2026-10-01")
        )
    session.commit()

    # Limit = 1 (top scorer only)
    top_1 = query_top_scorers_view(session, limit=1)
    assert len(top_1) == 1
    assert top_1[0]["player_name"] == "Scorer 7"
    assert top_1[0]["goals"] == 14

    # Limit = 3
    top_3 = query_top_scorers_view(session, limit=3)
    assert len(top_3) == 3
    assert [r["scorer_rank"] for r in top_3] == [1, 2, 3]
    assert [r["goals"] for r in top_3] == [14, 12, 10]

    # Limit = 50 (larger than total records)
    all_scorers = query_top_scorers_view(session, limit=50)
    assert len(all_scorers) == 7


def test_top_scorers_dynamic_updates(view_db):
    """Verifies that modifying player records dynamically updates the top scorers view."""
    _, session = view_db
    _create_sample_club(session, 1, "Arsenal FC", "ARS")

    player = Player(player_id=101, club_id=1, name="Kai Havertz", position="Forward", nationality="Germany", jersey_number=29, appearances=20, goals=0, assists=2, transformed_at="2026-10-01")
    session.add(player)
    session.commit()

    # With 0 goals, player does not appear in top scorers
    assert len(query_top_scorers_view(session)) == 0

    # Havertz scores 5 goals -> immediately appears in view
    player.goals = 5
    session.commit()

    scorers = query_top_scorers_view(session)
    assert len(scorers) == 1
    assert scorers[0]["player_name"] == "Kai Havertz"
    assert scorers[0]["goals"] == 5


# =========================================================================
# 3. TESTS FOR vw_club_analytics
# =========================================================================

def test_club_analytics_schema_and_columns(view_db):
    """Verifies that vw_club_analytics projects all 15 expected columns."""
    _, session = view_db
    _create_sample_club(session, 1, "Arsenal FC", "ARS")

    session.add(
        Standing(club_id=1, position=2, played=5, won=4, drawn=0, lost=1, goals_for=10, goals_against=3, goal_difference=7, points=12, points_per_game=2.4, win_percentage=80.0, form="W-W-W-L-W", transformed_at="2026-10-01")
    )
    session.add_all([
        Player(player_id=101, club_id=1, name="Bukayo Saka", position="Forward", nationality="England", jersey_number=7, appearances=30, goals=15, assists=10, transformed_at="2026-10-01"),
        Player(player_id=102, club_id=1, name="Martin Ødegaard", position="Midfielder", nationality="Norway", jersey_number=8, appearances=28, goals=8, assists=8, transformed_at="2026-10-01"),
    ])
    session.commit()

    rows = query_club_analytics_view(session)
    assert len(rows) == 1
    row = rows[0]

    expected_fields = {
        "club_id",
        "club_name",
        "short_name",
        "stadium",
        "capacity",
        "city",
        "primary_color",
        "squad_size",
        "squad_goals",
        "squad_assists",
        "avg_player_appearances",
        "league_position",
        "points",
        "goal_difference",
        "form",
    }
    assert expected_fields.issubset(set(row.keys()))


def test_club_analytics_aggregation_accuracy(view_db):
    """Verifies squad_size, squad_goals, squad_assists, and avg_player_appearances calculations."""
    _, session = view_db
    _create_sample_club(session, 1, "Chelsea FC", "CHE")

    session.add(
        Standing(club_id=1, position=4, played=6, won=3, drawn=2, lost=1, goals_for=11, goals_against=7, goal_difference=4, points=11, points_per_game=1.83, win_percentage=50.0, form="W-D-W-L-D", transformed_at="2026-10-01")
    )
    # 3 players: appearances=[30, 25, 20], goals=[12, 6, 0], assists=[8, 4, 1]
    session.add_all([
        Player(player_id=101, club_id=1, name="Player A", position="Forward", nationality="Test", jersey_number=10, appearances=30, goals=12, assists=8, transformed_at="2026-10-01"),
        Player(player_id=102, club_id=1, name="Player B", position="Midfielder", nationality="Test", jersey_number=8, appearances=25, goals=6, assists=4, transformed_at="2026-10-01"),
        Player(player_id=103, club_id=1, name="Player C", position="Defender", nationality="Test", jersey_number=4, appearances=20, goals=0, assists=1, transformed_at="2026-10-01"),
    ])
    session.commit()

    rows = query_club_analytics_view(session)
    assert len(rows) == 1
    row = rows[0]

    # Squad size = 3 distinct players
    assert row["squad_size"] == 3
    # Squad goals = 12 + 6 + 0 = 18
    assert row["squad_goals"] == 18
    # Squad assists = 8 + 4 + 1 = 13
    assert row["squad_assists"] == 13
    # Avg appearances = (30 + 25 + 20) / 3 = 75 / 3 = 25.0
    assert row["avg_player_appearances"] == 25.0
    # Standings fields
    assert row["league_position"] == 4
    assert row["points"] == 11
    assert row["goal_difference"] == 4
    assert row["form"] == "W-D-W-L-D"


def test_club_analytics_left_join_club_without_players(view_db):
    """Verifies LEFT JOIN resilience when a club has standings but zero registered players."""
    _, session = view_db
    _create_sample_club(session, 1, "Rosterless FC", "RFC")

    session.add(
        Standing(club_id=1, position=5, played=5, won=2, drawn=2, lost=1, goals_for=6, goals_against=5, goal_difference=1, points=8, points_per_game=1.6, win_percentage=40.0, form="D-W-D-W-L", transformed_at="2026-10-01")
    )
    session.commit()

    rows = query_club_analytics_view(session)
    assert len(rows) == 1
    row = rows[0]

    # COALESCE defaults squad goals and assists to 0, squad size is 0
    assert row["squad_size"] == 0
    assert row["squad_goals"] == 0
    assert row["squad_assists"] == 0
    assert row["avg_player_appearances"] is None  # AVG over empty set is NULL
    # Standings metrics are preserved
    assert row["league_position"] == 5
    assert row["points"] == 8
    assert row["goal_difference"] == 1
    assert row["form"] == "D-W-D-W-L"


def test_club_analytics_left_join_club_without_standings(view_db):
    """Verifies LEFT JOIN resilience when a club has players but no standings record."""
    _, session = view_db
    _create_sample_club(session, 1, "New Academy FC", "NAF")

    session.add_all([
        Player(player_id=101, club_id=1, name="Prospect One", position="Forward", nationality="Test", jersey_number=9, appearances=10, goals=5, assists=3, transformed_at="2026-10-01"),
        Player(player_id=102, club_id=1, name="Prospect Two", position="Midfielder", nationality="Test", jersey_number=10, appearances=8, goals=2, assists=4, transformed_at="2026-10-01"),
    ])
    session.commit()

    rows = query_club_analytics_view(session)
    assert len(rows) == 1
    row = rows[0]

    # Squad metrics are preserved
    assert row["squad_size"] == 2
    assert row["squad_goals"] == 7
    assert row["squad_assists"] == 7
    assert row["avg_player_appearances"] == 9.0
    # COALESCE defaults standing metrics to 0
    assert row["league_position"] == 0
    assert row["points"] == 0
    assert row["goal_difference"] == 0
    assert row["form"] is None


def test_club_analytics_isolated_club(view_db):
    """Verifies LEFT JOIN resilience for an isolated club with neither players nor standings."""
    _, session = view_db
    _create_sample_club(session, 1, "Isolated FC", "ISO")

    rows = query_club_analytics_view(session)
    assert len(rows) == 1
    row = rows[0]

    assert row["club_name"] == "Isolated FC"
    assert row["squad_size"] == 0
    assert row["squad_goals"] == 0
    assert row["squad_assists"] == 0
    assert row["avg_player_appearances"] is None
    assert row["league_position"] == 0
    assert row["points"] == 0
    assert row["goal_difference"] == 0
    assert row["form"] is None


def test_club_analytics_league_position_ordering(view_db):
    """Verifies that query_club_analytics_view sorts records by league_position ASC."""
    _, session = view_db
    _create_sample_club(session, 1, "Midtable FC", "MFC")
    _create_sample_club(session, 2, "Leader FC", "LFC")
    _create_sample_club(session, 3, "Basement FC", "BFC")

    session.add_all([
        Standing(club_id=1, position=10, played=5, won=2, drawn=1, lost=2, goals_for=6, goals_against=6, goal_difference=0, points=7, points_per_game=1.4, win_percentage=40.0, transformed_at="2026-10-01"),
        Standing(club_id=2, position=1, played=5, won=5, drawn=0, lost=0, goals_for=15, goals_against=2, goal_difference=13, points=15, points_per_game=3.0, win_percentage=100.0, transformed_at="2026-10-01"),
        Standing(club_id=3, position=20, played=5, won=0, drawn=1, lost=4, goals_for=2, goals_against=12, goal_difference=-10, points=1, points_per_game=0.2, win_percentage=0.0, transformed_at="2026-10-01"),
    ])
    session.commit()

    rows = query_club_analytics_view(session)
    assert len(rows) == 3
    assert [r["short_name"] for r in rows] == ["LFC", "MFC", "BFC"]
    assert [r["league_position"] for r in rows] == [1, 10, 20]


def test_club_analytics_dynamic_aggregation(view_db):
    """Verifies that adding a new player immediately updates squad aggregations in real-time."""
    _, session = view_db
    _create_sample_club(session, 1, "Arsenal FC", "ARS")

    player1 = Player(player_id=101, club_id=1, name="Saka", position="Forward", nationality="England", jersey_number=7, appearances=20, goals=10, assists=5, transformed_at="2026-10-01")
    session.add(player1)
    session.commit()

    initial = query_club_analytics_view(session)
    assert initial[0]["squad_size"] == 1
    assert initial[0]["squad_goals"] == 10
    assert initial[0]["squad_assists"] == 5

    # Transfer in a second player
    player2 = Player(player_id=102, club_id=1, name="Rice", position="Midfielder", nationality="England", jersey_number=41, appearances=22, goals=4, assists=6, transformed_at="2026-10-01")
    session.add(player2)
    session.commit()

    updated = query_club_analytics_view(session)
    assert updated[0]["squad_size"] == 2
    assert updated[0]["squad_goals"] == 14
    assert updated[0]["squad_assists"] == 11
    assert updated[0]["avg_player_appearances"] == 21.0  # (20 + 22) / 2


# =========================================================================
# 4. TESTS FOR VIEW LIFECYCLE & MANAGEMENT
# =========================================================================

def test_create_analytical_views_idempotency(view_db):
    """Verifies that create_analytical_views can be called repeatedly without throwing errors."""
    engine, session = view_db
    # Call a second and third time
    create_analytical_views(engine)
    create_analytical_views(engine)

    # Views must remain functional
    assert query_league_table_view(session) == []
    assert query_top_scorers_view(session) == []
    assert query_club_analytics_view(session) == []


def test_drop_analytical_views_and_recreate(view_db):
    """Verifies that drop_analytical_views cleanly removes views and recreating restores them."""
    engine, session = view_db

    # Drop all 3 views
    drop_analytical_views(engine)

    # Calling drop again must be idempotent
    drop_analytical_views(engine)

    # Querying dropped view must raise OperationalError
    with pytest.raises(Exception):
        session.execute(text("SELECT * FROM vw_league_table"))

    # Recreate and verify restored functionality
    create_analytical_views(engine)
    res = session.execute(text("SELECT * FROM vw_league_table"))
    assert res.fetchall() == []


# =========================================================================
# 5. TESTS FOR PIPELINE WAREHOUSE DATASET & FASTAPI INTEGRATION
# =========================================================================

def test_analytical_views_on_pipeline_warehouse():
    """End-to-End Validation: Runs full transformation and loader on realistic data,

    then validates all 3 views against the populated warehouse.
    """
    engine = create_engine("sqlite:///:memory:")
    create_all_tables(engine)
    create_analytical_views(engine)

    transform_out = run_transformations()
    dfs = transform_out["dataframes"]
    load_all_processed_data(engine=engine, dataframes=dfs)

    SessionFactory = sessionmaker(bind=engine)
    session = SessionFactory()

    try:
        # 1. League Table View
        league_table = query_league_table_view(session)
        assert len(league_table) == 10
        # Check monotonic rank ordering 1 to 10
        ranks = [row["dynamic_rank"] for row in league_table]
        assert ranks == list(range(1, 11))
        # Top team should be Manchester City (13 points)
        assert league_table[0]["short_name"] == "MCI"
        assert league_table[0]["points"] == 13

        # 2. Top Scorers View
        top_scorers = query_top_scorers_view(session, limit=10)
        assert len(top_scorers) == 10
        # Golden boot leader: Erling Haaland with 27 goals
        assert top_scorers[0]["player_name"] == "Erling Haaland"
        assert top_scorers[0]["goals"] == 27
        assert top_scorers[0]["scorer_rank"] == 1
        # Check strictly non-increasing goals
        goals_list = [s["goals"] for s in top_scorers]
        assert goals_list == sorted(goals_list, reverse=True)
        # Check all scorers have goals > 0
        assert all(s["goals"] > 0 for s in top_scorers)

        # 3. Club Analytics View
        club_analytics = query_club_analytics_view(session)
        assert len(club_analytics) == 10
        # Total players counted across all clubs in analytics must equal 20
        total_players_in_view = sum(c["squad_size"] for c in club_analytics)
        assert total_players_in_view == 20
        # Man City squad size in test dataset is 4
        mci = next(c for c in club_analytics if c["short_name"] == "MCI")
        assert mci["squad_size"] == 4
        assert mci["league_position"] == 1
    finally:
        session.close()


def test_fastapi_endpoints_serve_analytical_views():
    """Verifies that FastAPI REST endpoints properly expose the analytical SQL views."""
    engine = get_db_engine()
    create_all_tables(engine)
    create_analytical_views(engine)

    with TestClient(app) as client:
        # 1. /api/standings
        resp_standings = client.get("/api/standings")
        assert resp_standings.status_code == 200
        standings_data = resp_standings.json()
        assert isinstance(standings_data, list)
        if len(standings_data) > 0:
            assert "dynamic_rank" in standings_data[0]
            assert "club_name" in standings_data[0]
            assert standings_data[0]["dynamic_rank"] == 1

        # 2. /api/analytics/top-scorers with limit query parameter
        resp_scorers = client.get("/api/analytics/top-scorers?limit=5")
        assert resp_scorers.status_code == 200
        scorers_data = resp_scorers.json()
        assert isinstance(scorers_data, list)
        if len(scorers_data) >= 2:
            assert len(scorers_data) <= 5
            assert scorers_data[0]["scorer_rank"] == 1
            assert scorers_data[0]["goals"] >= scorers_data[1]["goals"]

        # 3. /api/analytics/club-summary
        resp_clubs = client.get("/api/analytics/club-summary")
        assert resp_clubs.status_code == 200
        clubs_data = resp_clubs.json()
        assert isinstance(clubs_data, list)
        if len(clubs_data) > 0:
            assert "squad_size" in clubs_data[0]
            assert "squad_goals" in clubs_data[0]
