import logging
from typing import Any, Dict, List
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

VIEW_LEAGUE_TABLE_SQL = """
CREATE VIEW IF NOT EXISTS vw_league_table AS
SELECT
    DENSE_RANK() OVER (
        ORDER BY s.points DESC, s.goal_difference DESC, s.goals_for DESC, s.goals_against ASC
    ) AS dynamic_rank,
    c.club_id,
    c.name AS club_name,
    c.short_name,
    c.stadium,
    c.primary_color,
    s.played,
    s.won,
    s.drawn,
    s.lost,
    s.goals_for,
    s.goals_against,
    s.goal_difference,
    s.points,
    s.points_per_game,
    s.win_percentage,
    s.form
FROM standings s
JOIN clubs c ON s.club_id = c.club_id;
"""

VIEW_TOP_SCORERS_SQL = """
CREATE VIEW IF NOT EXISTS vw_top_scorers AS
SELECT
    ROW_NUMBER() OVER (
        ORDER BY p.goals DESC, p.assists DESC, p.appearances ASC
    ) AS scorer_rank,
    p.player_id,
    p.name AS player_name,
    c.name AS club_name,
    c.short_name AS club_short_name,
    c.primary_color AS club_color,
    p.position,
    p.nationality,
    p.jersey_number,
    p.appearances,
    p.goals,
    p.assists,
    p.goal_contributions,
    p.goals_per_game
FROM players p
JOIN clubs c ON p.club_id = c.club_id
WHERE p.goals > 0;
"""

VIEW_CLUB_ANALYTICS_SQL = """
CREATE VIEW IF NOT EXISTS vw_club_analytics AS
SELECT
    c.club_id,
    c.name AS club_name,
    c.short_name,
    c.stadium,
    c.capacity,
    c.city,
    c.primary_color,
    COUNT(DISTINCT p.player_id) AS squad_size,
    COALESCE(SUM(p.goals), 0) AS squad_goals,
    COALESCE(SUM(p.assists), 0) AS squad_assists,
    ROUND(AVG(p.appearances), 1) AS avg_player_appearances,
    COALESCE(s.position, 0) AS league_position,
    COALESCE(s.points, 0) AS points,
    COALESCE(s.goal_difference, 0) AS goal_difference,
    s.form
FROM clubs c
LEFT JOIN players p ON c.club_id = p.club_id
LEFT JOIN standings s ON c.club_id = s.club_id
GROUP BY
    c.club_id, c.name, c.short_name, c.stadium, c.capacity, c.city,
    c.primary_color, s.position, s.points, s.goal_difference, s.form;
"""


def create_analytical_views(engine: Engine) -> None:
    """Creates analytical SQL views demonstrating window functions, joins, and aggregations.

    Args:
        engine: Active SQLAlchemy Engine.
    """
    logger.info("Deploying analytical SQL views to data warehouse...")
    with engine.begin() as conn:
        conn.execute(text(VIEW_LEAGUE_TABLE_SQL))
        conn.execute(text(VIEW_TOP_SCORERS_SQL))
        conn.execute(text(VIEW_CLUB_ANALYTICS_SQL))
    logger.info("Successfully deployed all 3 analytical SQL views.")


def drop_analytical_views(engine: Engine) -> None:
    """Drops analytical SQL views."""
    with engine.begin() as conn:
        conn.execute(text("DROP VIEW IF EXISTS vw_league_table;"))
        conn.execute(text("DROP VIEW IF EXISTS vw_top_scorers;"))
        conn.execute(text("DROP VIEW IF EXISTS vw_club_analytics;"))
    logger.info("Dropped analytical views.")


def query_league_table_view(session: Session) -> List[Dict[str, Any]]:
    """Executes SELECT query on the windowed vw_league_table analytical view."""
    stmt = text("SELECT * FROM vw_league_table ORDER BY dynamic_rank ASC")
    result = session.execute(stmt)
    return [dict(row._mapping) for row in result]


def query_top_scorers_view(session: Session, limit: int = 10) -> List[Dict[str, Any]]:
    """Executes SELECT query on vw_top_scorers view with row limit."""
    stmt = text("SELECT * FROM vw_top_scorers ORDER BY scorer_rank ASC LIMIT :limit")
    result = session.execute(stmt, {"limit": limit})
    return [dict(row._mapping) for row in result]


def query_club_analytics_view(session: Session) -> List[Dict[str, Any]]:
    """Executes SELECT query on aggregated vw_club_analytics view."""
    stmt = text("SELECT * FROM vw_club_analytics ORDER BY league_position ASC")
    result = session.execute(stmt)
    return [dict(row._mapping) for row in result]
