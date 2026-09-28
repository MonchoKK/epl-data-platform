import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Valid EPL positions for normalization
VALID_POSITIONS_MAP = {
    "goalkeeper": "Goalkeeper",
    "gk": "Goalkeeper",
    "defender": "Defender",
    "def": "Defender",
    "midfielder": "Midfielder",
    "mid": "Midfielder",
    "forward": "Forward",
    "fwd": "Forward",
    "striker": "Forward",
}


def clean_players_data(raw_records: List[Dict[str, Any]]) -> pd.DataFrame:
    """Cleans, normalizes, and enriches raw EPL player records.

    Transformations performed:
    1. Trims player name whitespace and removes superfluous character patterns.
    2. Maps messy position strings (e.g., 'midfielder', 'FORWARD', 'fwd') to canonical standards.
    3. Enforces non-negative numerical invariants for goals, assists, and appearances.
    4. Computes derived engineering metrics:
       - goal_contributions (goals + assists)
       - goals_per_game (goals / appearances, safely handling zero appearances)
    5. Appends transformation lineage timestamp.

    Args:
        raw_records: List of raw player dictionaries from ingestion.

    Returns:
        Pandas DataFrame of clean player entities.
    """
    if not raw_records:
        raise ValueError("Cannot clean empty player records list.")

    df = pd.DataFrame(raw_records)

    # 1. Clean and normalize text fields
    df["name"] = df["name"].astype(str).str.strip()
    df["nationality"] = df["nationality"].astype(str).str.strip()

    # Normalize position via mapping lookup
    def normalize_position(pos_str: str) -> str:
        clean_key = str(pos_str).strip().lower()
        if clean_key in VALID_POSITIONS_MAP:
            return VALID_POSITIONS_MAP[clean_key]
        return pos_str.strip().capitalize()

    df["position"] = df["position"].apply(normalize_position)

    # 2. Enforce numerical constraints
    df["player_id"] = df["player_id"].astype(int)
    df["club_id"] = df["club_id"].astype(int)
    df["jersey_number"] = df["jersey_number"].astype(int)
    df["goals"] = df["goals"].fillna(0).astype(int)
    df["assists"] = df["assists"].fillna(0).astype(int)
    df["appearances"] = df["appearances"].fillna(0).astype(int)

    # Validation: no negative values permitted
    for col in ["goals", "assists", "appearances", "jersey_number"]:
        if (df[col] < 0).any():
            raise ValueError(f"Negative values detected in player column: {col}")

    # 3. Compute derived metrics
    df["goal_contributions"] = df["goals"] + df["assists"]
    df["goals_per_game"] = np.where(
        df["appearances"] > 0,
        (df["goals"] / df["appearances"]).round(2),
        0.0,
    )

    # 4. Lineage metadata
    df["transformed_at"] = datetime.now(timezone.utc).isoformat()

    target_columns = [
        "player_id",
        "club_id",
        "name",
        "position",
        "nationality",
        "jersey_number",
        "appearances",
        "goals",
        "assists",
        "goal_contributions",
        "goals_per_game",
        "transformed_at",
    ]
    cleaned_df = df[target_columns].copy()

    logger.info("Cleaned %d player records successfully.", len(cleaned_df))
    return cleaned_df
