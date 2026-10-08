import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.connection import Base
from src.database.loader import load_clubs, load_players
from src.database.models import Club, Player, Standing, create_all_tables
from src.database.views import (
    create_analytical_views,
    query_club_analytics_view,
    query_league_table_view,
    query_top_scorers_view,
)
from src.transform.clean_clubs import clean_clubs_data
from src.transform.clean_players import clean_players_data


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    create_all_tables(engine)
    create_analytical_views(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session, engine
    session.close()


def test_database_idempotent_loading(in_memory_db):
    session, engine = in_memory_db

    # Clean club and player data
    raw_clubs = [
        {
            "club_id": 1,
            "name": "Arsenal",
            "short_name": "ARS",
            "stadium": "Emirates Stadium",
            "capacity": 60000,
            "city": "London",
            "founded_year": 1886,
            "primary_color": "#EF0107",
        }
    ]
    raw_players = [
        {
            "player_id": 101,
            "club_id": 1,
            "name": "Bukayo Saka",
            "position": "Forward",
            "nationality": "England",
            "jersey_number": 7,
            "appearances": 30,
            "goals": 15,
            "assists": 10,
        }
    ]

    clubs_df = clean_clubs_data(raw_clubs)
    players_df = clean_players_data(raw_players)

    # 1st load
    load_clubs(session, clubs_df)
    load_players(session, players_df)
    session.commit()

    assert session.query(Club).count() == 1
    assert session.query(Player).count() == 1

    # 2nd load with updated goals (testing idempotency)
    players_df.loc[0, "goals"] = 16
    load_players(session, players_df)
    session.commit()

    # Total count remains 1, but goals updated
    assert session.query(Player).count() == 1
    updated_player = session.query(Player).filter_by(player_id=101).first()
    assert updated_player.goals == 16

    # Test analytical SQL views
    scorers = query_top_scorers_view(session)
    assert len(scorers) == 1
    assert scorers[0]["player_name"] == "Bukayo Saka"
    assert scorers[0]["goals"] == 16

    standing = Standing(
        club_id=1,
        position=1,
        played=30,
        won=20,
        drawn=5,
        lost=5,
        goals_for=65,
        goals_against=25,
        goal_difference=40,
        points=65,
        points_per_game=2.17,
        win_percentage=66.7,
        form="W-W-D-W-L",
        transformed_at="2026-10-01",
    )
    session.add(standing)
    session.commit()

    league_table = query_league_table_view(session)
    assert len(league_table) == 1
    assert league_table[0]["club_name"] == "Arsenal"
    assert league_table[0]["dynamic_rank"] == 1
    assert league_table[0]["points"] == 65

    club_analytics = query_club_analytics_view(session)
    assert len(club_analytics) == 1
    assert club_analytics[0]["club_name"] == "Arsenal"
    assert club_analytics[0]["squad_size"] == 1
    assert club_analytics[0]["squad_goals"] == 16
    assert club_analytics[0]["league_position"] == 1
