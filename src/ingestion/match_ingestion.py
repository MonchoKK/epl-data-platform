import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def fetch_raw_matches(source_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches raw Premier League match records from external fixture feed.

    Extracts matches including match date, gameweek, raw unparsed score string (e.g. '2 - 0'),
    home and away club identifiers, and match status.
    Demonstrates data engineering needs for string splitting, type coercion, and validation.

    Args:
        source_url: Optional URL to external match API or feed.

    Returns:
        List of raw dictionaries representing EPL match fixtures and results.
    """
    logger.info("Starting raw ingestion for EPL matches...")

    raw_matches: List[Dict[str, Any]] = [
        # Gameweek 1
        {
            "match_id": 1001,
            "gameweek": 1,
            "home_club_id": 6,  # Man United
            "away_club_id": 9,  # Brighton
            "match_date": "2024-08-16 20:00:00",
            "raw_score": "1 - 0",
            "status": "FINISHED",
        },
        {
            "match_id": 1002,
            "gameweek": 1,
            "home_club_id": 1,  # Arsenal
            "away_club_id": 10,  # West Ham
            "match_date": "2024-08-17 15:00:00",
            "raw_score": "2 - 0",
            "status": "FINISHED",
        },
        {
            "match_id": 1003,
            "gameweek": 1,
            "home_club_id": 3,  # Chelsea
            "away_club_id": 5,  # Man City
            "match_date": "2024-08-18 16:30:00",
            "raw_score": "0 - 2",
            "status": "FINISHED",
        },
        {
            "match_id": 1004,
            "gameweek": 1,
            "home_club_id": 7,  # Newcastle
            "away_club_id": 2,  # Aston Villa
            "match_date": "2024-08-17 17:30:00",
            "raw_score": "1 - 0",
            "status": "FINISHED",
        },
        {
            "match_id": 1005,
            "gameweek": 1,
            "home_club_id": 8,  # Tottenham
            "away_club_id": 4,  # Liverpool
            "match_date": "2024-08-19 20:00:00",
            "raw_score": "1 - 1",
            "status": "FINISHED",
        },
        # Gameweek 2
        {
            "match_id": 1006,
            "gameweek": 2,
            "home_club_id": 5,  # Man City
            "away_club_id": 9,  # Brighton
            "match_date": "2024-08-24 15:00:00",
            "raw_score": "4 - 1",
            "status": "FINISHED",
        },
        {
            "match_id": 1007,
            "gameweek": 2,
            "home_club_id": 2,  # Aston Villa
            "away_club_id": 1,  # Arsenal
            "match_date": "2024-08-24 17:30:00",
            "raw_score": "0 - 2",
            "status": "FINISHED",
        },
        {
            "match_id": 1008,
            "gameweek": 2,
            "home_club_id": 4,  # Liverpool
            "away_club_id": 10,  # West Ham
            "match_date": "2024-08-25 16:30:00",
            "raw_score": "2 - 0",
            "status": "FINISHED",
        },
        {
            "match_id": 1009,
            "gameweek": 2,
            "home_club_id": 10,  # West Ham
            "away_club_id": 3,  # Chelsea
            "match_date": "2024-08-25 14:00:00",
            "raw_score": "2 - 6",
            "status": "FINISHED",
        },
        # Gameweek 3
        {
            "match_id": 1010,
            "gameweek": 3,
            "home_club_id": 1,  # Arsenal
            "away_club_id": 9,  # Brighton
            "match_date": "2024-08-31 12:30:00",
            "raw_score": "1 - 1",
            "status": "FINISHED",
        },
        {
            "match_id": 1011,
            "gameweek": 3,
            "home_club_id": 6,  # Man United
            "away_club_id": 4,  # Liverpool
            "match_date": "2024-09-01 16:00:00",
            "raw_score": "0 - 3",
            "status": "FINISHED",
        },
        {
            "match_id": 1012,
            "gameweek": 3,
            "home_club_id": 7,  # Newcastle
            "away_club_id": 8,  # Tottenham
            "match_date": "2024-09-01 13:30:00",
            "raw_score": "2 - 1",
            "status": "FINISHED",
        },
        # Gameweek 4
        {
            "match_id": 1013,
            "gameweek": 4,
            "home_club_id": 8,  # Tottenham
            "away_club_id": 1,  # Arsenal
            "match_date": "2024-09-15 14:00:00",
            "raw_score": "0 - 1",
            "status": "FINISHED",
        },
        {
            "match_id": 1014,
            "gameweek": 4,
            "home_club_id": 5,  # Man City
            "away_club_id": 10,  # West Ham
            "match_date": "2024-09-14 15:00:00",
            "raw_score": "3 - 1",
            "status": "FINISHED",
        },
        # Gameweek 5 (Blockbuster clash)
        {
            "match_id": 1015,
            "gameweek": 5,
            "home_club_id": 5,  # Man City
            "away_club_id": 1,  # Arsenal
            "match_date": "2024-09-22 16:30:00",
            "raw_score": "2 - 2",
            "status": "FINISHED",
        },
    ]

    now_utc = datetime.now(timezone.utc).isoformat()
    for match in raw_matches:
        match["_ingested_at"] = now_utc
        match["_source"] = source_url or "api.premierleague.com/v1/matches"

    logger.info("Successfully fetched %d raw match records.", len(raw_matches))
    return raw_matches
