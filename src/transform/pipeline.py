import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
import pandas as pd

from src.config import PROCESSED_DATA_DIR, RAW_DATA_DIR, ensure_directories
from src.quality.checker import (
    audit_dataset,
    build_quality_report,
    get_club_validators,
    get_match_validators,
    get_player_validators,
    get_standings_validators,
    render_report_banner,
)
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
    """Orchestrates end-to-end data transformation pipeline with integrated data quality gating.

    1. Loads raw ingested datasets from bronze layer (data/raw/).
    2. Runs comprehensive Data Quality Audit (Completeness, Uniqueness, Invariants).
    3. Prints executive Data Quality Report banner and saves data/processed/quality_report.json.
    4. Cleans and normalizes valid records into silver data tier.
    5. Generates transformation manifest tracking lineage.

    Returns:
        Dict containing manifest, quality report, and processed DataFrames.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger.info("================================================")
    logger.info("STARTING EPL DATA PLATFORM TRANSFORMATION PIPELINE")
    logger.info("================================================")

    batch_time = datetime.now(timezone.utc).isoformat()

    # 1. Load raw datasets from bronze layer
    with open(RAW_DATA_DIR / "clubs_raw.json", "r", encoding="utf-8") as f:
        raw_clubs = json.load(f)

    with open(RAW_DATA_DIR / "players_raw.json", "r", encoding="utf-8") as f:
        raw_players = json.load(f)

    with open(RAW_DATA_DIR / "matches_raw.json", "r", encoding="utf-8") as f:
        raw_matches = json.load(f)

    with open(RAW_DATA_DIR / "standings_raw.json", "r", encoding="utf-8") as f:
        raw_standings = json.load(f)

    # 2. DATA QUALITY GATE: Audit raw datasets
    logger.info("\nExecuting Data Quality Audit across raw datasets...")
    clubs_audit = audit_dataset(
        records=raw_clubs,
        dataset_name="clubs",
        primary_key="club_id",
        required_fields=["club_id", "name", "short_name", "stadium", "capacity", "founded_year"],
        custom_validators=get_club_validators(),
    )

    players_audit = audit_dataset(
        records=raw_players,
        dataset_name="players",
        primary_key="player_id",
        required_fields=["player_id", "club_id", "name", "position", "jersey_number"],
        custom_validators=get_player_validators(),
    )

    matches_audit = audit_dataset(
        records=raw_matches,
        dataset_name="matches",
        primary_key="match_id",
        required_fields=["match_id", "gameweek", "home_club_id", "away_club_id", "raw_score"],
        custom_validators=get_match_validators(),
    )

    standings_audit = audit_dataset(
        records=raw_standings,
        dataset_name="standings",
        primary_key="club_id",
        required_fields=["club_id", "played", "won", "drawn", "lost", "goals_for", "goals_against", "points"],
        custom_validators=get_standings_validators(),
    )

    # 3. Consolidate & display quality report
    quality_report = build_quality_report([clubs_audit, players_audit, matches_audit, standings_audit])
    report_banner = render_report_banner(quality_report)
    print("\n" + report_banner + "\n")

    # Persist quality report artifact
    ensure_directories()
    quality_report_path = PROCESSED_DATA_DIR / "quality_report.json"
    with open(quality_report_path, "w", encoding="utf-8") as f:
        json.dump(quality_report.to_dict(), f, indent=2)
    logger.info("Saved data quality report to %s", quality_report_path)

    if quality_report.status == "FAIL":
        logger.error("Data Quality check FAILED. Pipeline aborted to prevent warehouse corruption.")
        raise ValueError(f"Pipeline halted: Data Quality check failed with {quality_report.rejected_records} rejections.")

    # 4. Execute cleaning and transformations on valid audited records
    clubs_df = clean_clubs_data(clubs_audit.valid_records)
    players_df = clean_players_data(players_audit.valid_records)
    matches_df = clean_matches_data(matches_audit.valid_records)
    standings_df = calculate_standings_and_form(standings_audit.valid_records, matches_df)

    # 5. Save processed datasets
    clubs_paths = save_processed_dataset(clubs_df, "clubs")
    players_paths = save_processed_dataset(players_df, "players")
    matches_paths = save_processed_dataset(matches_df, "matches")
    standings_paths = save_processed_dataset(standings_df, "standings")

    manifest = {
        "batch_timestamp": batch_time,
        "quality_status": quality_report.status,
        "quality_report_path": str(quality_report_path),
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
        "quality_report": quality_report.to_dict(),
        "dataframes": {
            "clubs": clubs_df,
            "players": players_df,
            "matches": matches_df,
            "standings": standings_df,
        },
    }


if __name__ == "__main__":
    run_transformations()
