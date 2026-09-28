import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)


def compute_club_form(club_id: int, matches_df: Optional[pd.DataFrame], limit: int = 5) -> str:
    """Computes the recent match form string (e.g., 'W-D-W-W-L') for a club.

    Demonstrates analytical window aggregation on historical fixtures.

    Args:
        club_id: Identifier of the club.
        matches_df: DataFrame of cleaned matches with dates and scores.
        limit: Number of recent games to consider.

    Returns:
        Hyphen-separated string representing outcomes ('W', 'D', 'L').
    """
    if matches_df is None or matches_df.empty:
        return "N/A"

    # Filter all matches involving this club
    club_matches = matches_df[
        (matches_df["home_club_id"] == club_id) | (matches_df["away_club_id"] == club_id)
    ].copy()

    if club_matches.empty:
        return "N/A"

    club_matches["match_date"] = pd.to_datetime(club_matches["match_date"])
    club_matches = club_matches.sort_values(by="match_date", ascending=True)

    form_letters: List[str] = []
    for _, match in club_matches.tail(limit).iterrows():
        is_home = match["home_club_id"] == club_id
        if match["home_score"] == match["away_score"]:
            form_letters.append("D")
        elif (is_home and match["home_score"] > match["away_score"]) or (
            not is_home and match["away_score"] > match["home_score"]
        ):
            form_letters.append("W")
        else:
            form_letters.append("L")

    return "-".join(form_letters) if form_letters else "N/A"


def calculate_standings_and_form(
    raw_records: List[Dict[str, Any]], matches_df: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """Cleans raw standings, validates mathematical invariants, and derives league ranking.

    Transformations performed:
    1. Validates invariant: played == won + drawn + lost.
    2. Validates invariant: points == (won * 3) + drawn.
    3. Derives goal_difference = goals_for - goals_against.
    4. Computes points_per_game = round(points / played, 2).
    5. Computes win_percentage = round((won / played) * 100, 1).
    6. Computes recent form string by joining with match fixture history.
    7. Applies league sorting criteria and computes league_position rank:
       (points DESC, goal_difference DESC, goals_for DESC).

    Args:
        raw_records: List of raw standings dictionaries.
        matches_df: Optional DataFrame of cleaned matches for form calculation.

    Returns:
        Cleaned, ranked league standings DataFrame.
    """
    if not raw_records:
        raise ValueError("Cannot clean empty standings records list.")

    df = pd.DataFrame(raw_records)

    # 1. Type casting
    for col in ["club_id", "played", "won", "drawn", "lost", "goals_for", "goals_against", "points"]:
        df[col] = df[col].astype(int)

    # 2. Invariant validations
    games_check = df["played"] != (df["won"] + df["drawn"] + df["lost"])
    if games_check.any():
        raise ValueError(f"Inconsistent games played detected in records: {df[games_check]}")

    points_check = df["points"] != ((df["won"] * 3) + df["drawn"])
    if points_check.any():
        raise ValueError(f"Inconsistent points calculation detected in records: {df[points_check]}")

    # 3. Derived metrics
    df["goal_difference"] = df["goals_for"] - df["goals_against"]
    df["points_per_game"] = (df["points"] / df["played"]).round(2)
    df["win_percentage"] = ((df["won"] / df["played"]) * 100).round(1)

    # 4. Form computation
    df["form"] = df["club_id"].apply(lambda cid: compute_club_form(cid, matches_df))

    # 5. League Ranking
    df = df.sort_values(
        by=["points", "goal_difference", "goals_for", "goals_against"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

    df["position"] = df.index + 1

    # 6. Lineage metadata
    df["transformed_at"] = datetime.now(timezone.utc).isoformat()

    target_columns = [
        "position",
        "club_id",
        "played",
        "won",
        "drawn",
        "lost",
        "goals_for",
        "goals_against",
        "goal_difference",
        "points",
        "points_per_game",
        "win_percentage",
        "form",
        "transformed_at",
    ]
    cleaned_df = df[target_columns].copy()

    logger.info("Cleaned and ranked %d standings records successfully.", len(cleaned_df))
    return cleaned_df
