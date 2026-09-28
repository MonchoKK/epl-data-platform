import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.config import PROCESSED_DATA_DIR
from src.database.connection import get_db_engine, get_db_session
from src.database.models import Club, Match, Player, Standing, create_all_tables
from src.database.views import create_analytical_views

logger = logging.getLogger(__name__)


def load_clubs(session: Session, clubs_df: pd.DataFrame) -> int:
    """Idempotently loads cleaned clubs records into the warehouse dimension table.

    Demonstrates upsert / merge pattern on primary key.

    Args:
        session: Active database session.
        clubs_df: Cleaned clubs DataFrame.

    Returns:
        Number of clubs loaded.
    """
    logger.info("Loading %d clubs into database...", len(clubs_df))
    loaded = 0
    for _, row in clubs_df.iterrows():
        existing = session.query(Club).filter_by(club_id=int(row["club_id"])).first()
        if existing:
            existing.name = str(row["name"])
            existing.short_name = str(row["short_name"])
            existing.stadium = str(row["stadium"])
            existing.capacity = int(row["capacity"])
            existing.city = str(row["city"])
            existing.founded_year = int(row["founded_year"])
            existing.primary_color = str(row["primary_color"])
            existing.transformed_at = str(row["transformed_at"])
        else:
            club = Club(
                club_id=int(row["club_id"]),
                name=str(row["name"]),
                short_name=str(row["short_name"]),
                stadium=str(row["stadium"]),
                capacity=int(row["capacity"]),
                city=str(row["city"]),
                founded_year=int(row["founded_year"]),
                primary_color=str(row["primary_color"]),
                transformed_at=str(row["transformed_at"]),
            )
            session.add(club)
        loaded += 1
    session.flush()
    return loaded


def load_players(session: Session, players_df: pd.DataFrame) -> int:
    """Idempotently loads cleaned players records into the players dimension table.

    Args:
        session: Active database session.
        players_df: Cleaned players DataFrame.

    Returns:
        Number of players loaded.
    """
    logger.info("Loading %d players into database...", len(players_df))
    loaded = 0
    for _, row in players_df.iterrows():
        existing = session.query(Player).filter_by(player_id=int(row["player_id"])).first()
        if existing:
            existing.club_id = int(row["club_id"])
            existing.name = str(row["name"])
            existing.position = str(row["position"])
            existing.nationality = str(row["nationality"])
            existing.jersey_number = int(row["jersey_number"])
            existing.appearances = int(row["appearances"])
            existing.goals = int(row["goals"])
            existing.assists = int(row["assists"])
            existing.goal_contributions = int(row["goal_contributions"])
            existing.goals_per_game = float(row["goals_per_game"])
            existing.transformed_at = str(row["transformed_at"])
        else:
            player = Player(
                player_id=int(row["player_id"]),
                club_id=int(row["club_id"]),
                name=str(row["name"]),
                position=str(row["position"]),
                nationality=str(row["nationality"]),
                jersey_number=int(row["jersey_number"]),
                appearances=int(row["appearances"]),
                goals=int(row["goals"]),
                assists=int(row["assists"]),
                goal_contributions=int(row["goal_contributions"]),
                goals_per_game=float(row["goals_per_game"]),
                transformed_at=str(row["transformed_at"]),
            )
            session.add(player)
        loaded += 1
    session.flush()
    return loaded


def load_matches(session: Session, matches_df: pd.DataFrame) -> int:
    """Idempotently loads cleaned match records into the matches fact table.

    Args:
        session: Active database session.
        matches_df: Cleaned matches DataFrame.

    Returns:
        Number of matches loaded.
    """
    logger.info("Loading %d matches into database...", len(matches_df))
    loaded = 0
    for _, row in matches_df.iterrows():
        existing = session.query(Match).filter_by(match_id=int(row["match_id"])).first()
        if existing:
            existing.gameweek = int(row["gameweek"])
            existing.home_club_id = int(row["home_club_id"])
            existing.away_club_id = int(row["away_club_id"])
            existing.match_date = str(row["match_date"])
            existing.home_score = int(row["home_score"])
            existing.away_score = int(row["away_score"])
            existing.total_goals = int(row["total_goals"])
            existing.result = str(row["result"])
            existing.status = str(row["status"])
            existing.transformed_at = str(row["transformed_at"])
        else:
            match = Match(
                match_id=int(row["match_id"]),
                gameweek=int(row["gameweek"]),
                home_club_id=int(row["home_club_id"]),
                away_club_id=int(row["away_club_id"]),
                match_date=str(row["match_date"]),
                home_score=int(row["home_score"]),
                away_score=int(row["away_score"]),
                total_goals=int(row["total_goals"]),
                result=str(row["result"]),
                status=str(row["status"]),
                transformed_at=str(row["transformed_at"]),
            )
            session.add(match)
        loaded += 1
    session.flush()
    return loaded


def load_standings(session: Session, standings_df: pd.DataFrame) -> int:
    """Idempotently loads cleaned league table records into standings table.

    Args:
        session: Active database session.
        standings_df: Cleaned standings DataFrame.

    Returns:
        Number of standings records loaded.
    """
    logger.info("Loading %d standings records into database...", len(standings_df))
    loaded = 0
    for _, row in standings_df.iterrows():
        existing = session.query(Standing).filter_by(club_id=int(row["club_id"])).first()
        if existing:
            existing.position = int(row["position"])
            existing.played = int(row["played"])
            existing.won = int(row["won"])
            existing.drawn = int(row["drawn"])
            existing.lost = int(row["lost"])
            existing.goals_for = int(row["goals_for"])
            existing.goals_against = int(row["goals_against"])
            existing.goal_difference = int(row["goal_difference"])
            existing.points = int(row["points"])
            existing.points_per_game = float(row["points_per_game"])
            existing.win_percentage = float(row["win_percentage"])
            existing.form = str(row["form"])
            existing.transformed_at = str(row["transformed_at"])
        else:
            standing = Standing(
                club_id=int(row["club_id"]),
                position=int(row["position"]),
                played=int(row["played"]),
                won=int(row["won"]),
                drawn=int(row["drawn"]),
                lost=int(row["lost"]),
                goals_for=int(row["goals_for"]),
                goals_against=int(row["goals_against"]),
                goal_difference=int(row["goal_difference"]),
                points=int(row["points"]),
                points_per_game=float(row["points_per_game"]),
                win_percentage=float(row["win_percentage"]),
                form=str(row["form"]),
                transformed_at=str(row["transformed_at"]),
            )
            session.add(standing)
        loaded += 1
    session.flush()
    return loaded


def load_all_processed_data(
    engine: Optional[Engine] = None,
    dataframes: Optional[Dict[str, pd.DataFrame]] = None,
) -> Dict[str, Any]:
    """Orchestrates end-to-end data warehouse loading pipeline.

    Creates tables and views if missing, then loads clubs, players,
    matches, and standings in strict referential dependency order.

    Args:
        engine: Optional Engine instance.
        dataframes: Optional dictionary of DataFrames. If None, reads from data/processed/.

    Returns:
        Summary dict of loaded rows and execution status.
    """
    eng = engine or get_db_engine()

    # 1. Ensure DDL Schema and Analytical Views are initialized
    create_all_tables(eng)
    create_analytical_views(eng)

    # 2. Retrieve DataFrames (either passed in or loaded from data/processed/ CSVs)
    if dataframes is None:
        clubs_df = pd.read_csv(PROCESSED_DATA_DIR / "clubs_clean.csv")
        players_df = pd.read_csv(PROCESSED_DATA_DIR / "players_clean.csv")
        matches_df = pd.read_csv(PROCESSED_DATA_DIR / "matches_clean.csv")
        standings_df = pd.read_csv(PROCESSED_DATA_DIR / "standings_clean.csv")
    else:
        clubs_df = dataframes["clubs"]
        players_df = dataframes["players"]
        matches_df = dataframes["matches"]
        standings_df = dataframes["standings"]

    # 3. Load in transactional session in referential integrity order:
    # Clubs (parent) -> Players (child) -> Matches (child) -> Standings (child)
    with get_db_session(eng) as session:
        clubs_count = load_clubs(session, clubs_df)
        players_count = load_players(session, players_df)
        matches_count = load_matches(session, matches_df)
        standings_count = load_standings(session, standings_df)

    logger.info(
        "Warehouse loading complete! (Clubs: %d, Players: %d, Matches: %d, Standings: %d)",
        clubs_count,
        players_count,
        matches_count,
        standings_count,
    )

    return {
        "status": "SUCCESS",
        "counts": {
            "clubs": clubs_count,
            "players": players_count,
            "matches": matches_count,
            "standings": standings_count,
        },
        "total_loaded": clubs_count + players_count + matches_count + standings_count,
    }


if __name__ == "__main__":
    load_all_processed_data()
