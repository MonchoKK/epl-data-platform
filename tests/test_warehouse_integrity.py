import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Club, Match, Player, Standing, create_all_tables


@pytest.fixture
def warehouse_env():
    """Provides a fresh in-memory SQLite warehouse with foreign key PRAGMA enforcement enabled."""
    engine = create_engine("sqlite:///:memory:")

    # Enforce SQLite foreign key checking for test session
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    create_all_tables(engine)
    SessionFactory = sessionmaker(bind=engine)
    session = SessionFactory()

    yield engine, session

    session.close()


# =========================================================================
# 1. VERIFY TABLES ARE CREATED CORRECTLY
# =========================================================================

def test_tables_created_correctly(warehouse_env):
    """Verifies that all 4 warehouse relational tables exist with expected columns and primary keys."""
    engine, _ = warehouse_env
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    # Verify expected tables are present
    expected_tables = {"clubs", "players", "matches", "standings"}
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"

    # Verify clubs schema
    club_cols = {col["name"]: col for col in inspector.get_columns("clubs")}
    for expected_col in ["club_id", "name", "short_name", "stadium", "capacity", "city", "founded_year"]:
        assert expected_col in club_cols
    assert inspector.get_pk_constraint("clubs")["constrained_columns"] == ["club_id"]

    # Verify players schema
    player_cols = {col["name"]: col for col in inspector.get_columns("players")}
    for expected_col in ["player_id", "club_id", "name", "position", "jersey_number", "goals", "assists"]:
        assert expected_col in player_cols
    assert inspector.get_pk_constraint("players")["constrained_columns"] == ["player_id"]

    # Verify matches schema
    match_cols = {col["name"]: col for col in inspector.get_columns("matches")}
    for expected_col in ["match_id", "gameweek", "home_club_id", "away_club_id", "home_score", "away_score", "result"]:
        assert expected_col in match_cols
    assert inspector.get_pk_constraint("matches")["constrained_columns"] == ["match_id"]

    # Verify standings schema
    standing_cols = {col["name"]: col for col in inspector.get_columns("standings")}
    for expected_col in ["id", "club_id", "position", "played", "won", "drawn", "lost", "points", "goal_difference"]:
        assert expected_col in standing_cols
    assert inspector.get_pk_constraint("standings")["constrained_columns"] == ["id"]


# =========================================================================
# 2. VERIFY FOREIGN KEYS WORK
# =========================================================================

def test_foreign_keys_work(warehouse_env):
    """Verifies referential integrity: child inserts with invalid foreign keys are strictly rejected."""
    _, session = warehouse_env

    # 1. Player referencing non-existent club_id must raise IntegrityError
    orphan_player = Player(
        player_id=9001,
        club_id=9999,  # Non-existent club
        name="Ghost Player",
        position="Midfielder",
        nationality="England",
        jersey_number=10,
        transformed_at="2026-10-01T00:00:00Z",
    )
    session.add(orphan_player)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # 2. Match referencing non-existent home/away clubs must raise IntegrityError
    valid_club = Club(
        club_id=1,
        name="Arsenal",
        short_name="ARS",
        stadium="Emirates Stadium",
        capacity=60704,
        city="London",
        founded_year=1886,
        transformed_at="2026-10-01T00:00:00Z",
    )
    session.add(valid_club)
    session.commit()

    orphan_match = Match(
        match_id=8001,
        gameweek=1,
        home_club_id=1,
        away_club_id=9999,  # Non-existent away club
        match_date="2026-10-01 15:00:00",
        home_score=1,
        away_score=0,
        total_goals=1,
        result="HOME_WIN",
        transformed_at="2026-10-01T00:00:00Z",
    )
    session.add(orphan_match)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # 3. Standing referencing non-existent club must raise IntegrityError
    orphan_standing = Standing(
        club_id=9999,  # Non-existent club
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
        transformed_at="2026-10-01T00:00:00Z",
    )
    session.add(orphan_standing)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# =========================================================================
# 3. VERIFY CONSTRAINTS REJECT INVALID DATA
# =========================================================================

def test_constraints_reject_invalid_data(warehouse_env):
    """Verifies that CheckConstraints and UniqueConstraints reject domain violations."""
    _, session = warehouse_env

    # 1. Club check: capacity > 0
    bad_capacity_club = Club(
        club_id=10,
        name="Zero Stadium FC",
        short_name="ZFC",
        stadium="Ghost Ground",
        capacity=0,  # Invalid: capacity must be > 0
        city="London",
        founded_year=1900,
        transformed_at="2026-10-01T00:00:00Z",
    )
    session.add(bad_capacity_club)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # 2. Club check: founded_year >= 1800
    bad_year_club = Club(
        club_id=11,
        name="Ancient FC",
        short_name="ANC",
        stadium="Castle Ground",
        capacity=10000,
        city="York",
        founded_year=1600,  # Invalid: must be >= 1800
        transformed_at="2026-10-01T00:00:00Z",
    )
    session.add(bad_year_club)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # 3. Club unique constraint: duplicate name
    club_a = Club(
        club_id=1,
        name="Chelsea FC",
        short_name="CHE",
        stadium="Stamford Bridge",
        capacity=40343,
        city="London",
        founded_year=1905,
        transformed_at="2026-10-01T00:00:00Z",
    )
    club_b = Club(
        club_id=2,
        name="Chelsea FC",  # Duplicate name
        short_name="CH2",
        stadium="Second Bridge",
        capacity=20000,
        city="London",
        founded_year=1910,
        transformed_at="2026-10-01T00:00:00Z",
    )
    session.add(club_a)
    session.commit()
    session.add(club_b)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # 4. Player check: goals >= 0
    bad_player = Player(
        player_id=101,
        club_id=1,
        name="Negative Scorer",
        position="Forward",
        nationality="England",
        jersey_number=9,
        goals=-5,  # Invalid: goals cannot be negative
        transformed_at="2026-10-01T00:00:00Z",
    )
    session.add(bad_player)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # 5. Match check: home_club_id != away_club_id
    self_match = Match(
        match_id=1001,
        gameweek=1,
        home_club_id=1,
        away_club_id=1,  # Invalid: cannot play against self
        match_date="2026-10-01 15:00:00",
        home_score=1,
        away_score=1,
        total_goals=2,
        result="DRAW",
        transformed_at="2026-10-01T00:00:00Z",
    )
    session.add(self_match)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # 6. Standing unique constraint: 1 standing per club_id
    standing_1 = Standing(
        club_id=1,
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
        transformed_at="2026-10-01T00:00:00Z",
    )
    standing_duplicate = Standing(
        club_id=1,  # Duplicate standing for club_id 1
        position=2,
        played=1,
        won=1,
        drawn=0,
        lost=0,
        goals_for=1,
        goals_against=0,
        goal_difference=1,
        points=3,
        points_per_game=3.0,
        win_percentage=100.0,
        transformed_at="2026-10-01T00:00:00Z",
    )
    session.add(standing_1)
    session.commit()
    session.add(standing_duplicate)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# =========================================================================
# 4. VERIFY INDEXES EXIST
# =========================================================================

def test_indexes_exist(warehouse_env):
    """Verifies that single-column and composite B-Tree indexes are defined and registered."""
    engine, _ = warehouse_env
    inspector = inspect(engine)

    # Players indexes
    player_indexes = {idx["name"]: idx for idx in inspector.get_indexes("players")}
    assert "idx_player_club_position" in player_indexes
    assert player_indexes["idx_player_club_position"]["column_names"] == ["club_id", "position"]
    assert "ix_players_position" in player_indexes
    assert "ix_players_goals" in player_indexes

    # Standings indexes
    standing_indexes = {idx["name"]: idx for idx in inspector.get_indexes("standings")}
    assert "idx_standings_points_rank" in standing_indexes
    assert standing_indexes["idx_standings_points_rank"]["column_names"] == ["points", "goal_difference"]
    assert "ix_standings_points" in standing_indexes

    # Matches indexes
    match_indexes = {idx["name"]: idx for idx in inspector.get_indexes("matches")}
    assert "ix_matches_gameweek" in match_indexes
    assert "ix_matches_match_date" in match_indexes


# =========================================================================
# 5. VERIFY RELATIONSHIPS BEHAVE CORRECTLY
# =========================================================================

def test_relationships_behavior_and_cascade(warehouse_env):
    """Verifies ORM navigation across 1-N, N-1, 1-1, dual FKs, and cascade delete propagation."""
    _, session = warehouse_env

    # 1. Setup parent clubs
    arsenal = Club(
        club_id=1,
        name="Arsenal",
        short_name="ARS",
        stadium="Emirates Stadium",
        capacity=60704,
        city="London",
        founded_year=1886,
        transformed_at="2026-10-01T00:00:00Z",
    )
    city = Club(
        club_id=2,
        name="Manchester City",
        short_name="MCI",
        stadium="Etihad Stadium",
        capacity=53400,
        city="Manchester",
        founded_year=1880,
        transformed_at="2026-10-01T00:00:00Z",
    )

    # 2. Add players via relationship collection
    saka = Player(
        player_id=101,
        name="Bukayo Saka",
        position="Forward",
        nationality="England",
        jersey_number=7,
        goals=14,
        assists=9,
        appearances=32,
        transformed_at="2026-10-01T00:00:00Z",
    )
    odegaard = Player(
        player_id=102,
        name="Martin Ødegaard",
        position="Midfielder",
        nationality="Norway",
        jersey_number=8,
        goals=8,
        assists=10,
        appearances=31,
        transformed_at="2026-10-01T00:00:00Z",
    )
    arsenal.players.extend([saka, odegaard])

    # 3. Add match via dual FK relationship
    match = Match(
        match_id=2001,
        gameweek=5,
        home_club=city,
        away_club=arsenal,
        match_date="2026-10-01 16:30:00",
        home_score=2,
        away_score=2,
        total_goals=4,
        result="DRAW",
        transformed_at="2026-10-01T00:00:00Z",
    )

    # 4. Add standing via 1-to-1 relationship
    standing = Standing(
        club=arsenal,
        position=2,
        played=5,
        won=3,
        drawn=2,
        lost=0,
        goals_for=8,
        goals_against=3,
        goal_difference=5,
        points=11,
        points_per_game=2.2,
        win_percentage=60.0,
        form="W-W-D-W-D",
        transformed_at="2026-10-01T00:00:00Z",
    )

    session.add_all([arsenal, city, match, standing])
    session.commit()

    # --- Verification of Relationships ---
    # 1-to-many: Club -> Players
    loaded_arsenal = session.query(Club).filter_by(club_id=1).first()
    assert len(loaded_arsenal.players) == 2
    player_names = {p.name for p in loaded_arsenal.players}
    assert player_names == {"Bukayo Saka", "Martin Ødegaard"}

    # Many-to-1 backref: Player -> Club
    loaded_saka = session.query(Player).filter_by(player_id=101).first()
    assert loaded_saka.club.name == "Arsenal"

    # Dual Foreign Keys: Home and Away navigation
    assert len(loaded_arsenal.away_matches) == 1
    assert loaded_arsenal.away_matches[0].match_id == 2001
    loaded_city = session.query(Club).filter_by(club_id=2).first()
    assert len(loaded_city.home_matches) == 1
    assert loaded_city.home_matches[0].away_club.name == "Arsenal"

    # 1-to-1: Club -> Standing
    assert loaded_arsenal.standing is not None
    assert loaded_arsenal.standing.points == 11
    assert loaded_arsenal.standing.club.short_name == "ARS"

    # --- Verification of Cascading Deletes ---
    # Deleting Arsenal should automatically cascade and delete its squad players
    session.delete(loaded_arsenal)
    session.commit()

    assert session.query(Club).filter_by(club_id=1).first() is None
    remaining_players = session.query(Player).filter(Player.player_id.in_([101, 102])).all()
    assert len(remaining_players) == 0, "Players were not cascade-deleted with parent Club"
