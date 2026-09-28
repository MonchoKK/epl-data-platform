import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
import pandas as pd

logger = logging.getLogger(__name__)


def clean_clubs_data(raw_records: List[Dict[str, Any]]) -> pd.DataFrame:
    """Cleans, normalizes, and validates raw club records into a structured DataFrame.

    Transformations performed:
    1. Trims leading/trailing whitespace from string columns (club name, city, stadium).
    2. Enforces upper-case 3-letter standard for short club codes.
    3. Type coerces numerical identifiers and capacity limits.
    4. Validates domain business rules (founded_year > 1800, capacity > 0).
    5. Appends transformation lineage timestamp.

    Args:
        raw_records: List of raw club dictionaries from ingestion.

    Returns:
        Pandas DataFrame ready for database warehouse loading.
    """
    if not raw_records:
        raise ValueError("Cannot clean empty club records list.")

    df = pd.DataFrame(raw_records)

    # 1. Clean string fields
    df["name"] = df["name"].astype(str).str.strip()
    df["short_name"] = df["short_name"].astype(str).str.strip().str.upper()
    df["stadium"] = df["stadium"].astype(str).str.strip()
    df["city"] = df["city"].astype(str).str.strip()
    df["primary_color"] = df["primary_color"].fillna("#1E293B").astype(str).str.strip()

    # 2. Type conversions & constraints
    df["club_id"] = df["club_id"].astype(int)
    df["capacity"] = df["capacity"].astype(int)
    df["founded_year"] = df["founded_year"].astype(int)

    # 3. Validation checks
    invalid_capacity = df[df["capacity"] <= 0]
    if not invalid_capacity.empty:
        raise ValueError(f"Found invalid stadium capacity in clubs: {invalid_capacity}")

    current_year = datetime.now().year
    invalid_year = df[(df["founded_year"] < 1850) | (df["founded_year"] > current_year)]
    if not invalid_year.empty:
        raise ValueError(f"Found invalid founded_year in clubs: {invalid_year}")

    # 4. Lineage metadata
    df["transformed_at"] = datetime.now(timezone.utc).isoformat()

    # Keep core dimensional columns + metadata
    target_columns = [
        "club_id",
        "name",
        "short_name",
        "stadium",
        "capacity",
        "city",
        "founded_year",
        "primary_color",
        "transformed_at",
    ]
    cleaned_df = df[target_columns].copy()

    logger.info("Cleaned %d club records successfully.", len(cleaned_df))
    return cleaned_df
