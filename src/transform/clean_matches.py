import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


def parse_score_string(raw_score: Any) -> Tuple[int, int]:
    """Parses raw match score string (e.g. '2 - 1', '3-0') into integer tuple (home, away).

    Args:
        raw_score: Raw string or object representing the score.

    Returns:
        Tuple of (home_score, away_score).
    """
    if pd.isna(raw_score) or not str(raw_score).strip():
        return 0, 0

    clean_str = str(raw_score).strip()
    match = re.search(r"(\d+)\s*[-:]\s*(\d+)", clean_str)
    if not match:
        raise ValueError(f"Unable to parse score format: '{raw_score}'")

    return int(match.group(1)), int(match.group(2))


def clean_matches_data(raw_records: List[Dict[str, Any]]) -> pd.DataFrame:
    """Cleans, parses, and derives analytical fields from raw EPL match fixtures.

    Transformations performed:
    1. Parses score string into explicit home_score and away_score integer metrics.
    2. Validates relational integrity constraint: home_club_id != away_club_id.
    3. Derives match result category: 'HOME_WIN', 'AWAY_WIN', 'DRAW'.
    4. Computes total_goals = home_score + away_score.
    5. Formats match_date into standard ISO 8601 string.
    6. Appends transformation lineage timestamp.

    Args:
        raw_records: List of raw match fixture dictionaries.

    Returns:
        Cleaned Pandas DataFrame of match fixtures and results.
    """
    if not raw_records:
        raise ValueError("Cannot clean empty match records list.")

    df = pd.DataFrame(raw_records)

    # 1. Type casting IDs & gameweek
    df["match_id"] = df["match_id"].astype(int)
    df["gameweek"] = df["gameweek"].astype(int)
    df["home_club_id"] = df["home_club_id"].astype(int)
    df["away_club_id"] = df["away_club_id"].astype(int)

    # 2. Relational sanity check: a club cannot play against itself
    self_match = df[df["home_club_id"] == df["away_club_id"]]
    if not self_match.empty:
        raise ValueError(f"Invalid match fixture found where home club matches away club: {self_match}")

    # 3. Parse score strings
    scores = df["raw_score"].apply(parse_score_string)
    df["home_score"] = [s[0] for s in scores]
    df["away_score"] = [s[1] for s in scores]

    # 4. Derive match outcome
    def determine_result(row: pd.Series) -> str:
        if row["home_score"] > row["away_score"]:
            return "HOME_WIN"
        elif row["home_score"] < row["away_score"]:
            return "AWAY_WIN"
        else:
            return "DRAW"

    df["result"] = df.apply(determine_result, axis=1)
    df["total_goals"] = df["home_score"] + df["away_score"]
    df["status"] = df["status"].fillna("FINISHED").astype(str).str.strip().str.upper()

    # 5. Normalize match_date to ISO
    df["match_date"] = pd.to_datetime(df["match_date"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    # 6. Lineage metadata
    df["transformed_at"] = datetime.now(timezone.utc).isoformat()

    target_columns = [
        "match_id",
        "gameweek",
        "home_club_id",
        "away_club_id",
        "match_date",
        "home_score",
        "away_score",
        "total_goals",
        "result",
        "status",
        "transformed_at",
    ]
    cleaned_df = df[target_columns].copy()

    logger.info("Cleaned %d match records successfully.", len(cleaned_df))
    return cleaned_df
