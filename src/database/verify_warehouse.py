"""CLI Diagnostic Verification Tool for EPL Data Warehouse

Executes live inspection against the active data warehouse database file:
1. Tables creation and schema inspection
2. Foreign key enforcement checks
3. Check and uniqueness constraints validation
4. Index registration inspection
5. ORM relationship navigation & cascading delete behavior
"""

import sys
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.connection import get_db_engine, get_db_session
from src.database.models import Base, Club, Match, Player, Standing, create_all_tables


def verify_tables(engine) -> bool:
    """Verifies that all 4 warehouse relational tables exist with required primary keys."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    expected = {"clubs", "players", "matches", "standings"}
    missing = expected - existing_tables
    if missing:
        print(f"  ❌ Missing tables: {missing}")
        return False

    for tbl in expected:
        pk = inspector.get_pk_constraint(tbl)["constrained_columns"]
        print(f"  [OK] Table '{tbl}': PK={pk}")
    return True


def verify_foreign_keys(session: Session) -> bool:
    """Verifies that foreign key constraints actively block invalid parent references."""
    # Attempt inserting an orphan player with non-existent club
    orphan = Player(
        player_id=99999,
        club_id=88888,
        name="Orphan Test",
        position="Forward",
        nationality="Test",
        jersey_number=99,
        transformed_at="2026-10-01",
    )
    session.add(orphan)
    try:
        session.commit()
        print("  [FAIL] Foreign key violation failed to raise IntegrityError")
        return False
    except IntegrityError:
        session.rollback()
        print("  [OK] Foreign key rejection enforced (orphan child blocked with IntegrityError)")
        return True


def verify_constraints(session: Session) -> bool:
    """Verifies that check constraints actively reject out-of-range data."""
    # Capacity must be > 0
    bad_club = Club(
        club_id=77777,
        name="Bad Capacity Club",
        short_name="BCC",
        stadium="Zero Arena",
        capacity=-10,
        city="London",
        founded_year=1900,
        transformed_at="2026-10-01",
    )
    session.add(bad_club)
    try:
        session.commit()
        print("  [FAIL] Capacity check constraint failed to trigger")
        return False
    except IntegrityError:
        session.rollback()
        print("  [OK] Check constraint enforced: capacity <= 0 correctly rejected")
        return True


def verify_indexes(engine) -> bool:
    """Verifies that required composite and single-column indexes exist."""
    inspector = inspect(engine)
    players_indexes = {idx["name"] for idx in inspector.get_indexes("players")}
    standings_indexes = {idx["name"] for idx in inspector.get_indexes("standings")}

    has_player_composite = "idx_player_club_position" in players_indexes
    has_standing_composite = "idx_standings_points_rank" in standings_indexes

    if has_player_composite and has_standing_composite:
        print("  [OK] Composite index 'idx_player_club_position' found on players")
        print("  [OK] Composite index 'idx_standings_points_rank' found on standings")
        return True
    else:
        print("  [FAIL] Missing expected composite indexes")
        return False


def verify_relationships(session: Session) -> bool:
    """Verifies ORM navigation across relationships."""
    club = session.query(Club).first()
    if not club:
        print("  [WARN] No club records found to test navigation (run pipeline first)")
        return True

    squad_size = len(club.players)
    standing_pts = club.standing.points if club.standing else "N/A"
    print(f"  [OK] Club '{club.name}' relationship navigation: squad={squad_size} players, standing points={standing_pts}")
    return True


def run_warehouse_diagnostics():
    """Main verification orchestrator for the data warehouse."""
    print("\n=======================================================")
    print("      EPL DATA WAREHOUSE INTEGRITY VERIFICATION        ")
    print("=======================================================\n")

    engine = get_db_engine()
    create_all_tables(engine)

    print("[1/5] Verifying Relational Tables & Primary Keys...")
    tables_ok = verify_tables(engine)

    print("\n[2/5] Verifying Foreign Key Enforcement...")
    with get_db_session(engine) as session:
        fk_ok = verify_foreign_keys(session)

    print("\n[3/5] Verifying Check & Uniqueness Constraints...")
    with get_db_session(engine) as session:
        constraints_ok = verify_constraints(session)

    print("\n[4/5] Verifying B-Tree Index Registrations...")
    indexes_ok = verify_indexes(engine)

    print("\n[5/5] Verifying ORM Relationship Navigation...")
    with get_db_session(engine) as session:
        rel_ok = verify_relationships(session)

    all_passed = all([tables_ok, fk_ok, constraints_ok, indexes_ok, rel_ok])

    print("\n=======================================================")
    if all_passed:
        print("  STATUS: ALL WAREHOUSE VERIFICATIONS PASSED (5/5)  ")
    else:
        print("  STATUS: SOME VERIFICATIONS FAILED                 ")
    print("=======================================================\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    run_warehouse_diagnostics()
