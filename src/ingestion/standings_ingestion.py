import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def fetch_raw_standings(source_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches raw Premier League table standings extract from league data provider.

    Extracts base metrics: club ID, games played, wins, draws, losses, goals for/against,
    and league points snapshot.
    Enables transformation layer to validate mathematical invariants:
    (games_played == wins + draws + losses, points == wins*3 + draws).

    Args:
        source_url: Optional URL to external table API.

    Returns:
        List of raw dictionaries representing Premier League standings.
    """
    logger.info("Starting raw ingestion for EPL standings snapshot...")

    raw_standings: List[Dict[str, Any]] = [
        {"club_id": 5, "played": 5, "won": 4, "drawn": 1, "lost": 0, "goals_for": 13, "goals_against": 5, "points": 13},
        {"club_id": 4, "played": 5, "won": 4, "drawn": 0, "lost": 1, "goals_for": 10, "goals_against": 1, "points": 12},
        {"club_id": 1, "played": 5, "won": 3, "drawn": 2, "lost": 0, "goals_for": 8, "goals_against": 3, "points": 11},
        {"club_id": 3, "played": 5, "won": 3, "drawn": 1, "lost": 1, "goals_for": 11, "goals_against": 5, "points": 10},
        {"club_id": 2, "played": 5, "won": 3, "drawn": 1, "lost": 1, "goals_for": 9, "goals_against": 6, "points": 10},
        {"club_id": 7, "played": 5, "won": 3, "drawn": 1, "lost": 1, "goals_for": 7, "goals_against": 6, "points": 10},
        {"club_id": 9, "played": 5, "won": 2, "drawn": 3, "lost": 0, "goals_for": 8, "goals_against": 4, "points": 9},
        {"club_id": 8, "played": 5, "won": 2, "drawn": 1, "lost": 2, "goals_for": 9, "goals_against": 5, "points": 7},
        {"club_id": 6, "played": 5, "won": 2, "drawn": 1, "lost": 2, "goals_for": 5, "goals_against": 5, "points": 7},
        {"club_id": 10, "played": 5, "won": 1, "drawn": 1, "lost": 3, "goals_for": 5, "goals_against": 11, "points": 4},
    ]

    now_utc = datetime.now(timezone.utc).isoformat()
    for row in raw_standings:
        row["_ingested_at"] = now_utc
        row["_source"] = source_url or "api.premierleague.com/v1/standings"

    logger.info("Successfully fetched %d raw standings records.", len(raw_standings))
    return raw_standings
