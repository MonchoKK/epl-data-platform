import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.connection import Base
from src.database.loader import (
    load_all_processed_data,
    load_clubs,
    load_matches,
    load_players,
    load_standings,
)
from src.database.models import Club, Match, Player, Standing, create_all_tables
from src.transform.pipeline import run_transformations


@pytest.fixture
def fresh_warehouse():
    """Provides an isolated database for multi-run idempotency validation."""
    engine = create_engine("sqlite:///:memory:")
    create_all_tables(engine)
    SessionFactory = sessionmaker(bind=engine)
    session = SessionFactory()
    yield engine, session
    session.close()


def test_multi_run_idempotency(fresh_warehouse):
    """Proves that running the warehouse loading pipeline multiple times produces no duplicates:

    Run 1 -> 55 records
    Run 2 -> 55 records
    Run 3 -> 55 records
    """
    engine, session = fresh_warehouse
    transform_out = run_transformations()
    dfs = transform_out["dataframes"]

    # --- EXECUTION 1: INITIAL LOAD ---
    run1 = load_all_processed_data(engine=engine, dataframes=dfs)
    assert run1["counts"]["clubs"] == 10
    assert run1["counts"]["players"] == 20
    assert run1["counts"]["matches"] == 15
    assert run1["counts"]["standings"] == 10
    assert run1["total_loaded"] == 55

    assert session.query(Club).count() == 10
    assert session.query(Player).count() == 20
    assert session.query(Match).count() == 15
    assert session.query(Standing).count() == 10

    # --- EXECUTION 2: RE-RUN (UPSERT MERGE) ---
    run2 = load_all_processed_data(engine=engine, dataframes=dfs)
    assert run2["total_loaded"] == 55
    # Total row counts in DB must remain identical (zero duplicate rows created)
    assert session.query(Club).count() == 10
    assert session.query(Player).count() == 20
    assert session.query(Match).count() == 15
    assert session.query(Standing).count() == 10

    # --- EXECUTION 3: THIRD CONSECUTIVE RUN ---
    run3 = load_all_processed_data(engine=engine, dataframes=dfs)
    assert run3["total_loaded"] == 55
    assert session.query(Club).count() == 10
    assert session.query(Player).count() == 20
    assert session.query(Match).count() == 15
    assert session.query(Standing).count() == 10


def test_in_place_upsert_mutation(fresh_warehouse):
    """Proves that changes to existing records are updated in place rather than duplicated."""
    engine, session = fresh_warehouse
    transform_out = run_transformations()
    dfs = transform_out["dataframes"]

    # Initial load
    load_all_processed_data(engine=engine, dataframes=dfs)
    haaland = session.query(Player).filter_by(player_id=111).first()
    assert haaland.goals == 27

    # Mutate data payload (simulate next matchday where Haaland scores 2 more goals)
    mutated_players_df = dfs["players"].copy()
    mutated_players_df.loc[mutated_players_df["player_id"] == 111, "goals"] = 29
    mutated_dfs = dict(dfs)
    mutated_dfs["players"] = mutated_players_df

    # Re-run loader
    load_all_processed_data(engine=engine, dataframes=mutated_dfs)

    # Expire test session identity cache to reflect changes committed by loader
    session.expire_all()

    # Verify count remains exactly 20 (no duplicates), but Haaland's goals are updated in place
    assert session.query(Player).count() == 20
    updated_haaland = session.query(Player).filter_by(player_id=111).first()
    assert updated_haaland.goals == 29
