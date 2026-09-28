import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session

from src.database.connection import check_connection, get_db_session
from src.database.models import Club, Match, Player, Standing
from src.database.views import (
    query_club_analytics_view,
    query_league_table_view,
    query_top_scorers_view,
)
from src.pipeline_runner import run_full_pipeline

logger = logging.getLogger(__name__)

api_router = APIRouter(prefix="/api", tags=["EPL Data Platform API"])


@api_router.get("/health")
def get_health() -> Dict[str, Any]:
    """Returns warehouse and pipeline operational health metrics."""
    db_healthy = check_connection()
    return {
        "status": "ONLINE" if db_healthy else "DEGRADED",
        "database_connected": db_healthy,
        "platform": "EPL Data Engineering Platform",
        "version": "1.0.0",
    }


# =========================================================================
# CLUBS ENDPOINTS
# =========================================================================

@api_router.get("/clubs")
def get_clubs(
    city: Optional[str] = Query(None, description="Filter clubs by city"),
) -> List[Dict[str, Any]]:
    """Retrieves all Premier League clubs with optional city filtering."""
    with get_db_session() as session:
        query = session.query(Club)
        if city:
            query = query.filter(Club.city.ilike(f"%{city}%"))
        clubs = query.order_by(Club.name.asc()).all()
        return [c.to_dict() for c in clubs]


@api_router.get("/clubs/{club_id}")
def get_club_detail(club_id: int) -> Dict[str, Any]:
    """Retrieves full club profile including squad players, standing, and matches."""
    with get_db_session() as session:
        club = session.query(Club).filter_by(club_id=club_id).first()
        if not club:
            raise HTTPException(status_code=404, detail=f"Club ID {club_id} not found")

        squad = [p.to_dict() for p in club.players]
        standing = club.standing.to_dict() if club.standing else None

        # Fetch recent matches for this club
        matches = (
            session.query(Match)
            .filter((Match.home_club_id == club_id) | (Match.away_club_id == club_id))
            .order_by(Match.match_date.desc())
            .all()
        )

        data = club.to_dict()
        data["squad_count"] = len(squad)
        data["squad"] = squad
        data["standing"] = standing
        data["matches"] = [m.to_dict() for m in matches]
        return data


# =========================================================================
# PLAYERS ENDPOINTS
# =========================================================================

@api_router.get("/players")
def get_players(
    club_id: Optional[int] = Query(None, description="Filter by club ID"),
    position: Optional[str] = Query(None, description="Filter by position (e.g. Forward, Midfielder)"),
    search: Optional[str] = Query(None, description="Search player name"),
    limit: int = Query(50, ge=1, le=100),
) -> List[Dict[str, Any]]:
    """Retrieves player entities with relational filters, sorting, and pagination."""
    with get_db_session() as session:
        query = session.query(Player)
        if club_id is not None:
            query = query.filter(Player.club_id == club_id)
        if position:
            query = query.filter(Player.position.ilike(f"%{position}%"))
        if search:
            query = query.filter(Player.name.ilike(f"%{search}%"))

        players = query.order_by(Player.goals.desc(), Player.assists.desc()).limit(limit).all()
        return [p.to_dict() for p in players]


@api_router.get("/players/{player_id}")
def get_player_detail(player_id: int) -> Dict[str, Any]:
    """Retrieves specific player statistics and associated club metadata."""
    with get_db_session() as session:
        player = session.query(Player).filter_by(player_id=player_id).first()
        if not player:
            raise HTTPException(status_code=404, detail=f"Player ID {player_id} not found")
        return player.to_dict()


# =========================================================================
# MATCHES ENDPOINTS
# =========================================================================

@api_router.get("/matches")
def get_matches(
    gameweek: Optional[int] = Query(None, description="Filter by gameweek"),
    club_id: Optional[int] = Query(None, description="Filter by participating club ID"),
) -> List[Dict[str, Any]]:
    """Retrieves match fixtures and scores with relational club names."""
    with get_db_session() as session:
        query = session.query(Match)
        if gameweek is not None:
            query = query.filter(Match.gameweek == gameweek)
        if club_id is not None:
            query = query.filter((Match.home_club_id == club_id) | (Match.away_club_id == club_id))

        matches = query.order_by(Match.gameweek.asc(), Match.match_date.asc()).all()
        return [m.to_dict() for m in matches]


# =========================================================================
# STANDINGS & ANALYTICAL SQL VIEW ENDPOINTS
# =========================================================================

@api_router.get("/standings")
def get_league_standings() -> List[Dict[str, Any]]:
    """Retrieves official league table computed via SQL window function view vw_league_table."""
    with get_db_session() as session:
        return query_league_table_view(session)


@api_router.get("/analytics/top-scorers")
def get_top_scorers(limit: int = Query(10, ge=1, le=50)) -> List[Dict[str, Any]]:
    """Retrieves top goal scorers leaderboard from SQL analytical view vw_top_scorers."""
    with get_db_session() as session:
        return query_top_scorers_view(session, limit=limit)


@api_router.get("/analytics/club-summary")
def get_club_analytics() -> List[Dict[str, Any]]:
    """Retrieves club aggregation statistics from SQL analytical view vw_club_analytics."""
    with get_db_session() as session:
        return query_club_analytics_view(session)


# =========================================================================
# PIPELINE TRIGGER ENDPOINT
# =========================================================================

@api_router.post("/pipeline/trigger")
def trigger_pipeline() -> Dict[str, Any]:
    """Triggers on-demand execution of the full ELT data engineering pipeline."""
    try:
        report = run_full_pipeline()
        return {"success": True, "report": report}
    except Exception as exc:
        logger.error("Pipeline trigger failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(exc)}")
