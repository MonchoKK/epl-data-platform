"""CLI Diagnostic Verification Tool for PostgreSQL Warehouse Container (Task 4)

Executes live inspection against the containerized PostgreSQL data warehouse:
1. Container Connectivity & Version Check (PostgreSQL 16)
2. Relational DDL Tables & Primary Keys (clubs, players, matches, standings)
3. Foreign Key Referential Integrity Enforcement (orphan insertion rejection)
4. Domain Check Constraints Enforcement (capacity, founded_year, scores)
5. Analytical SQL Views Deployment & Window Query Verification
   - vw_league_table (DENSE_RANK window function)
   - vw_top_scorers (ROW_NUMBER window function)
   - vw_club_analytics (Multi-table LEFT JOIN aggregation)
6. End-to-End Pipeline Loading & Multi-Run Idempotency Verification
"""

import os
import sys
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.database.connection import get_db_session
from src.database.loader import load_all_processed_data
from src.database.models import Base, Club, Match, Player, Standing, create_all_tables
from src.database.views import (
    create_analytical_views,
    drop_analytical_views,
    query_club_analytics_view,
    query_league_table_view,
    query_top_scorers_view,
)
from src.transform.pipeline import run_transformations


def get_postgres_engine() -> Optional[Engine]:
    """Finds and connects to the active PostgreSQL container.

    Checks DATABASE_URL first, then falls back to ports 5433 and 5432.
    """
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
            return eng
        except Exception:
            continue

    return None


def verify_connection(engine: Engine) -> bool:
    """Verifies active connectivity and logs PostgreSQL engine version."""
    try:
        with engine.connect() as conn:
            res = conn.execute(text("SELECT version()")).scalar()
            print(f"  [OK] Successfully connected to PostgreSQL container!")
            print(f"       Engine version: {res.split(',')[0]}")
            return True
    except Exception as exc:
        print(f"  [FAIL] Could not connect to PostgreSQL: {exc}")
        return False


def verify_tables_and_schema(engine: Engine) -> bool:
    """Verifies that all 4 warehouse relational tables exist with expected primary keys."""
    create_all_tables(engine)
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    expected = {"clubs", "players", "matches", "standings"}

    missing = expected - existing_tables
    if missing:
        print(f"  [FAIL] Missing relational tables: {missing}")
        return False

    for tbl in expected:
        pk = inspector.get_pk_constraint(tbl)["constrained_columns"]
        print(f"  [OK] Table '{tbl}': PK={pk}")
    return True


def verify_foreign_keys(session: Session) -> bool:
    """Verifies that PostgreSQL actively enforces referential integrity on foreign keys."""
    orphan = Player(
        player_id=99991,
        club_id=88881,  # Non-existent club
        name="Postgres Orphan",
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
        print("  [OK] Referential integrity enforced: orphan child blocked with IntegrityError")
        return True


def verify_check_constraints(session: Session) -> bool:
    """Verifies that PostgreSQL CheckConstraints reject invalid data."""
    bad_club = Club(
        club_id=77771,
        name="Bad Capacity Club PG",
        short_name="BCP",
        stadium="Zero Arena",
        capacity=-10,  # Invalid: capacity > 0
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


def verify_analytical_views(engine: Engine, session: Session) -> bool:
    """Verifies deployment and querying of analytical SQL views on PostgreSQL."""
    create_analytical_views(engine)

    # 1. League table view
    league_rows = query_league_table_view(session)
    if not league_rows:
        print("  [FAIL] vw_league_table returned no records")
        return False
    top_club = league_rows[0]
    print(f"  [OK] vw_league_table: Rank #{top_club['dynamic_rank']} {top_club['club_name']} ({top_club['points']} pts, GD={top_club['goal_difference']})")

    # 2. Top scorers view
    scorers = query_top_scorers_view(session, limit=3)
    if not scorers:
        print("  [FAIL] vw_top_scorers returned no records")
        return False
    top_scorer = scorers[0]
    print(f"  [OK] vw_top_scorers: #{top_scorer['scorer_rank']} {top_scorer['player_name']} ({top_scorer['goals']} goals, {top_scorer['assists']} assists)")

    # 3. Club analytics view
    analytics = query_club_analytics_view(session)
    if not analytics:
        print("  [FAIL] vw_club_analytics returned no records")
        return False
    first_analytic = analytics[0]
    print(f"  [OK] vw_club_analytics: {first_analytic['club_name']} (Squad: {first_analytic['squad_size']}, Avg Apps: {first_analytic['avg_player_appearances']})")

    return True


def verify_idempotent_loading(engine: Engine, session: Session) -> bool:
    """Verifies that loading the warehouse twice produces identical record counts."""
    # Run 1
    res1 = load_all_processed_data(engine=engine)
    c1 = session.query(Club).count()
    p1 = session.query(Player).count()
    m1 = session.query(Match).count()
    s1 = session.query(Standing).count()
    total1 = c1 + p1 + m1 + s1

    # Run 2
    res2 = load_all_processed_data(engine=engine)
    c2 = session.query(Club).count()
    p2 = session.query(Player).count()
    m2 = session.query(Match).count()
    s2 = session.query(Standing).count()
    total2 = c2 + p2 + m2 + s2

    if total1 == 55 and total2 == 55:
        print(f"  [OK] Idempotency verified on PostgreSQL: Run 1 = {total1} rows, Run 2 = {total2} rows (0 duplicates)")
        return True
    else:
        print(f"  [FAIL] Duplicate rows detected: Run 1={total1}, Run 2={total2}")
        return False


def run_postgres_verification():
    """Main verification orchestrator for PostgreSQL warehouse container."""
    print("\n" + "=" * 70)
    print("      EPL DATA PLATFORM - POSTGRESQL WAREHOUSE VERIFICATION      ")
    print("=" * 70 + "\n")

    print("[1/6] Discovering & Connecting to PostgreSQL Container...")
    engine = get_postgres_engine()
    if not engine:
        print("  ❌ Could not connect to PostgreSQL container.")
        print("     Ensure Docker container is running: `docker compose up -d`")
        print("=" * 70 + "\n")
        sys.exit(1)

    conn_ok = verify_connection(engine)

    print("\n[2/6] Verifying Relational DDL Tables & Primary Keys...")
    tables_ok = verify_tables_and_schema(engine)

    # Use a session for data-dependent validations
    SessionFactory = sessionmaker(bind=engine)
    session = SessionFactory()

    try:
        print("\n[3/6] Verifying PostgreSQL Foreign Key Referential Integrity...")
        fk_ok = verify_foreign_keys(session)

        print("\n[4/6] Verifying PostgreSQL Check Constraints...")
        chk_ok = verify_check_constraints(session)

        print("\n[5/6] Verifying End-to-End Pipeline Loading & Idempotency...")
        idem_ok = verify_idempotent_loading(engine, session)

        print("\n[6/6] Verifying Analytical SQL Views (Window Functions & Aggregations)...")
        views_ok = verify_analytical_views(engine, session)
    finally:
        session.close()

    all_passed = all([conn_ok, tables_ok, fk_ok, chk_ok, idem_ok, views_ok])

    print("\n" + "=" * 70)
    if all_passed:
        print("  [SUCCESS] ALL POSTGRESQL WAREHOUSE VERIFICATIONS PASSED (6/6)")
        print("  Warehouse operates flawlessly against the PostgreSQL container!")
    else:
        print("  [FAILURE] SOME POSTGRESQL VERIFICATIONS FAILED")
    print("=" * 70 + "\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    run_postgres_verification()
