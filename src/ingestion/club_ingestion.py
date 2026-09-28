import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def fetch_raw_clubs(source_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches raw Premier League club records from external API/data provider.

    Simulates an external extraction step or HTTP response from the EPL API feed.
    Captures raw club metadata, stadium name, city, founded year, and club colors.
    Includes realistic raw ingestion issues (varying cases, trailing spaces)
    to demonstrate downstream data engineering transformations.

    Args:
        source_url: Optional URL to external REST endpoint or local mock file.

    Returns:
        List of raw dictionaries representing EPL clubs.
    """
    logger.info("Starting raw ingestion for EPL clubs...")

    # Realistic raw extract simulating EPL club registry data
    raw_clubs: List[Dict[str, Any]] = [
        {
            "club_id": 1,
            "name": " Arsenal FC ",
            "short_name": "ARS",
            "stadium": "Emirates Stadium",
            "capacity": 60704,
            "city": "London",
            "founded_year": 1886,
            "primary_color": "#EF0107",
        },
        {
            "club_id": 2,
            "name": "Aston Villa",
            "short_name": "AVL",
            "stadium": "Villa Park",
            "capacity": 42640,
            "city": "Birmingham",
            "founded_year": 1874,
            "primary_color": "#95BFE5",
        },
        {
            "club_id": 3,
            "name": "Chelsea FC",
            "short_name": "CHE",
            "stadium": "Stamford Bridge",
            "capacity": 40343,
            "city": "London",
            "founded_year": 1905,
            "primary_color": "#034694",
        },
        {
            "club_id": 4,
            "name": "Liverpool FC",
            "short_name": "LIV",
            "stadium": "Anfield",
            "capacity": 61276,
            "city": "Liverpool",
            "founded_year": 1892,
            "primary_color": "#C8102E",
        },
        {
            "club_id": 5,
            "name": "Manchester City",
            "short_name": "MCI",
            "stadium": "Etihad Stadium",
            "capacity": 53400,
            "city": "Manchester",
            "founded_year": 1880,
            "primary_color": "#6CABDD",
        },
        {
            "club_id": 6,
            "name": "Manchester United",
            "short_name": "MUN",
            "stadium": "Old Trafford",
            "capacity": 74310,
            "city": "Manchester",
            "founded_year": 1878,
            "primary_color": "#DA291C",
        },
        {
            "club_id": 7,
            "name": "Newcastle United",
            "short_name": "NEW",
            "stadium": "St. James' Park",
            "capacity": 52305,
            "city": "Newcastle upon Tyne",
            "founded_year": 1892,
            "primary_color": "#241F20",
        },
        {
            "club_id": 8,
            "name": "Tottenham Hotspur",
            "short_name": "TOT",
            "stadium": "Tottenham Hotspur Stadium",
            "capacity": 62850,
            "city": "London",
            "founded_year": 1882,
            "primary_color": "#132257",
        },
        {
            "club_id": 9,
            "name": "Brighton & Hove Albion",
            "short_name": "BHA",
            "stadium": "Amex Stadium",
            "capacity": 31876,
            "city": "Brighton",
            "founded_year": 1901,
            "primary_color": "#0057B8",
        },
        {
            "club_id": 10,
            "name": "West Ham United",
            "short_name": "WHU",
            "stadium": "London Stadium",
            "capacity": 62500,
            "city": "London",
            "founded_year": 1895,
            "primary_color": "#7A263A",
        },
    ]

    now_utc = datetime.now(timezone.utc).isoformat()
    for club in raw_clubs:
        club["_ingested_at"] = now_utc
        club["_source"] = source_url or "api.premierleague.com/v1/clubs"

    logger.info("Successfully fetched %d raw club records.", len(raw_clubs))
    return raw_clubs
