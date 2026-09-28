import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def fetch_raw_players(source_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches raw Premier League player records from external API/data provider.

    Simulates extraction of squad members, positions, shirt numbers, and performance stats.
    Includes data engineering edge cases (case differences in positions, extra whitespace,
    missing values) for downstream validation and transformation.

    Args:
        source_url: Optional URL to external REST endpoint or mock source.

    Returns:
        List of raw dictionaries representing EPL players.
    """
    logger.info("Starting raw ingestion for EPL players...")

    raw_players: List[Dict[str, Any]] = [
        # Arsenal (club_id: 1)
        {
            "player_id": 101,
            "club_id": 1,
            "name": " Bukayo Saka ",
            "position": "FORWARD",
            "nationality": "England",
            "jersey_number": 7,
            "goals": 14,
            "assists": 9,
            "appearances": 32,
        },
        {
            "player_id": 102,
            "club_id": 1,
            "name": "Martin Ødegaard",
            "position": "midfielder",
            "nationality": "Norway",
            "jersey_number": 8,
            "goals": 8,
            "assists": 10,
            "appearances": 31,
        },
        {
            "player_id": 103,
            "club_id": 1,
            "name": "William Saliba",
            "position": "Defender",
            "nationality": "France",
            "jersey_number": 2,
            "goals": 2,
            "assists": 1,
            "appearances": 35,
        },
        {
            "player_id": 104,
            "club_id": 1,
            "name": "David Raya",
            "position": "Goalkeeper",
            "nationality": "Spain",
            "jersey_number": 22,
            "goals": 0,
            "assists": 0,
            "appearances": 32,
        },
        # Chelsea (club_id: 3)
        {
            "player_id": 105,
            "club_id": 3,
            "name": "Cole Palmer",
            "position": "MIDFIELDER",
            "nationality": "England",
            "jersey_number": 20,
            "goals": 22,
            "assists": 11,
            "appearances": 33,
        },
        {
            "player_id": 106,
            "club_id": 3,
            "name": "Nicolas Jackson",
            "position": "Forward",
            "nationality": "Senegal",
            "jersey_number": 15,
            "goals": 14,
            "assists": 5,
            "appearances": 35,
        },
        {
            "player_id": 107,
            "club_id": 3,
            "name": "Moisés Caicedo",
            "position": "midfielder",
            "nationality": "Ecuador",
            "jersey_number": 25,
            "goals": 1,
            "assists": 3,
            "appearances": 34,
        },
        # Liverpool (club_id: 4)
        {
            "player_id": 108,
            "club_id": 4,
            "name": "Mohamed Salah",
            "position": "forward",
            "nationality": "Egypt",
            "jersey_number": 11,
            "goals": 18,
            "assists": 10,
            "appearances": 32,
        },
        {
            "player_id": 109,
            "club_id": 4,
            "name": "Virgil van Dijk",
            "position": "Defender",
            "nationality": "Netherlands",
            "jersey_number": 4,
            "goals": 2,
            "assists": 2,
            "appearances": 36,
        },
        {
            "player_id": 110,
            "club_id": 4,
            "name": "Alexis Mac Allister",
            "position": "Midfielder",
            "nationality": "Argentina",
            "jersey_number": 10,
            "goals": 5,
            "assists": 5,
            "appearances": 33,
        },
        # Manchester City (club_id: 5)
        {
            "player_id": 111,
            "club_id": 5,
            "name": " Erling Haaland ",
            "position": "Forward",
            "nationality": "Norway",
            "jersey_number": 9,
            "goals": 27,
            "assists": 5,
            "appearances": 31,
        },
        {
            "player_id": 112,
            "club_id": 5,
            "name": "Kevin De Bruyne",
            "position": "Midfielder",
            "nationality": "Belgium",
            "jersey_number": 17,
            "goals": 4,
            "assists": 10,
            "appearances": 18,
        },
        {
            "player_id": 113,
            "club_id": 5,
            "name": "Phil Foden",
            "position": "Forward",
            "nationality": "England",
            "jersey_number": 47,
            "goals": 19,
            "assists": 8,
            "appearances": 35,
        },
        {
            "player_id": 114,
            "club_id": 5,
            "name": "Rodri",
            "position": "Midfielder",
            "nationality": "Spain",
            "jersey_number": 16,
            "goals": 8,
            "assists": 9,
            "appearances": 34,
        },
        # Manchester United (club_id: 6)
        {
            "player_id": 115,
            "club_id": 6,
            "name": "Bruno Fernandes",
            "position": "Midfielder",
            "nationality": "Portugal",
            "jersey_number": 8,
            "goals": 10,
            "assists": 8,
            "appearances": 35,
        },
        {
            "player_id": 116,
            "club_id": 6,
            "name": "Alejandro Garnacho",
            "position": "Forward",
            "nationality": "Argentina",
            "jersey_number": 17,
            "goals": 7,
            "assists": 4,
            "appearances": 36,
        },
        {
            "player_id": 117,
            "club_id": 6,
            "name": "Kobbie Mainoo",
            "position": "Midfielder",
            "nationality": "England",
            "jersey_number": 37,
            "goals": 3,
            "assists": 1,
            "appearances": 24,
        },
        # Aston Villa (club_id: 2)
        {
            "player_id": 118,
            "club_id": 2,
            "name": "Ollie Watkins",
            "position": "Forward",
            "nationality": "England",
            "jersey_number": 11,
            "goals": 19,
            "assists": 13,
            "appearances": 37,
        },
        # Newcastle United (club_id: 7)
        {
            "player_id": 119,
            "club_id": 7,
            "name": "Alexander Isak",
            "position": "Forward",
            "nationality": "Sweden",
            "jersey_number": 14,
            "goals": 21,
            "assists": 2,
            "appearances": 30,
        },
        # Tottenham Hotspur (club_id: 8)
        {
            "player_id": 120,
            "club_id": 8,
            "name": "Son Heung-min",
            "position": "Forward",
            "nationality": "South Korea",
            "jersey_number": 7,
            "goals": 17,
            "assists": 10,
            "appearances": 35,
        },
    ]

    now_utc = datetime.now(timezone.utc).isoformat()
    for player in raw_players:
        player["_ingested_at"] = now_utc
        player["_source"] = source_url or "api.premierleague.com/v1/players"

    logger.info("Successfully fetched %d raw player records.", len(raw_players))
    return raw_players
