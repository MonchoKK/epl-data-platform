import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
import pandas as pd

from src.config import PROCESSED_DATA_DIR, RAW_DATA_DIR, ensure_directories
from src.transform.calculate_standings import calculate_standings_and_form
from src.transform.clean_clubs import clean_clubs_data
from src.transform.clean_matches import clean_matches_data
from src.transform.clean_players import clean_players_data

logger = logging.getLogger(__name__)


def save_processed_dataset(df: pd.DataFrame, dataset_name: str) -> Dict[str, str]:
    """Persists cleaned DataFrame into processed data layer in both CSV and JSON formats.

    Demonstrates silver-tier storage accessible for downstream analytical workloads or SQL loaders.

    Args:
        df: Processed DataFrame.
        dataset_name: Identifier for the entity.

    Returns:
        Dict containing file paths for CSV and JSON outputs.
    """
    ensure_directories()
    csv_path = PROCESSED_DATA_DIR / f"{dataset_name}_clean.csv"
    json_path = PROCESSED_DATA_DIR / f"{dataset_name}_clean.json"

    df.to_csv(csv_path, index=False)
    df.to_json(json_path, orient="records", indent=2)

    logger.info("Saved %d processed %s records to %s and %s", len(df), dataset_name, csv_path, json_path)
    return {"csv": str(csv_path), "json": str(json_path)}


def run_transformations() -> Dict[str, Any]:
    """Orchestrates end-to-end data transformation pipeline.

    Loads raw ingested datasets, cleans/normalizes schemas, derives business metrics,
    and persists datasets into data/processed/.

    Returns:
        Transformation manifest dictionary.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger.info("================================================")
    logger.info("STARTING EPL DATA PLATFORM TRANSFORMATION PIPELINE")
    logger.info("================================================")

    batch_time = datetime.now(timezone.utc).isoformat()

    # 1. Load raw datasets
    with open(RAW_DATA_DIR / "clubs_raw.json", "r", encoding="utf-8") as f:
        raw_clubs = json.load(f)

    with open(RAW_DATA_DIR / "players_raw.json", "r", encoding="utf-8") as f:
        raw_players = json.load(f)

    with open(RAW_DATA_DIR / "matches_raw.json", "r", encoding="utf-8") as f:
        raw_matches = json.load(f)

    with open(RAW_DATA_DIR / "standings_raw.json", "r", encoding="utf-8") as f:
        raw_standings = json.load(f)

    # 2. Execute cleaning and derivations
    clubs_df = clean_clubs_data(raw_clubs)
    players_df = clean_players_data(raw_players)
    matches_df = clean_matches_data(raw_matches)
    standings_df = calculate_standings_and_form(raw_standings, matches_df)

    # 3. Save processed datasets
    clubs_paths = save_processed_dataset(clubs_df, "clubs")
    players_paths = save_processed_dataset(players_df, "players")
    matches_paths = save_processed_dataset(matches_df, "matches")
    standings_paths = save_processed_dataset(standings_df, "standings")

    manifest = {
        "batch_timestamp": batch_time,
        "datasets": {
            "clubs": {"rows": len(clubs_df), "paths": clubs_paths},
            "players": {"rows": len(players_df), "paths": players_paths},
            "matches": {"rows": len(matches_df), "paths": matches_paths},
            "standings": {"rows": len(standings_df), "paths": standings_paths},
        },
        "total_processed_rows": len(clubs_df) + len(players_df) + len(matches_df) + len(standings_df),
    }

    manifest_path = PROCESSED_DATA_DIR / "transformation_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Transformation pipeline finished successfully. Manifest: %s", manifest_path)
    return {
        "manifest": manifest,
        "dataframes": {
            "clubs": clubs_df,
            "players": players_df,
            "matches": matches_df,
            "standings": standings_df,
        },
    }


if __name__ == "__main__":
    run_transformations()
