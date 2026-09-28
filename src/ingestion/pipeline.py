import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.config import RAW_DATA_DIR, ensure_directories
from src.ingestion.club_ingestion import fetch_raw_clubs
from src.ingestion.match_ingestion import fetch_raw_matches
from src.ingestion.player_ingestion import fetch_raw_players
from src.ingestion.standings_ingestion import fetch_raw_standings

logger = logging.getLogger(__name__)


def save_raw_dataset(data: List[Dict[str, Any]], dataset_name: str) -> Path:
    """Saves raw ingested records into the raw data storage layer as JSON.

    Demonstrates bronze/raw data lake tier storage before any mutation or transformation.

    Args:
        data: List of raw dictionaries.
        dataset_name: Identifier for dataset (e.g., 'clubs', 'players').

    Returns:
        Path to the saved raw file.
    """
    ensure_directories()
    file_path = RAW_DATA_DIR / f"{dataset_name}_raw.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info("Saved %d raw %s records to %s", len(data), dataset_name, file_path)
    return file_path


def run_raw_ingestion() -> Dict[str, Any]:
    """Orchestrates end-to-end raw data ingestion across all 4 EPL domains.

    Executes extraction for clubs, players, matches, and standings,
    persists datasets to raw storage, and generates an ingestion manifest.

    Returns:
        Dictionary summarizing paths, record counts, and execution timestamp.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger.info("==========================================")
    logger.info("STARTING EPL DATA PLATFORM RAW INGESTION")
    logger.info("==========================================")

    batch_time = datetime.now(timezone.utc).isoformat()

    # 1. Fetch raw datasets
    raw_clubs = fetch_raw_clubs()
    raw_players = fetch_raw_players()
    raw_matches = fetch_raw_matches()
    raw_standings = fetch_raw_standings()

    # 2. Persist to data/raw/
    clubs_path = save_raw_dataset(raw_clubs, "clubs")
    players_path = save_raw_dataset(raw_players, "players")
    matches_path = save_raw_dataset(raw_matches, "matches")
    standings_path = save_raw_dataset(raw_standings, "standings")

    # 3. Create ingestion manifest for data lineage tracking
    manifest = {
        "batch_timestamp": batch_time,
        "datasets": {
            "clubs": {"count": len(raw_clubs), "path": str(clubs_path)},
            "players": {"count": len(raw_players), "path": str(players_path)},
            "matches": {"count": len(raw_matches), "path": str(matches_path)},
            "standings": {"count": len(raw_standings), "path": str(standings_path)},
        },
        "total_records": len(raw_clubs) + len(raw_players) + len(raw_matches) + len(raw_standings),
    }

    manifest_path = RAW_DATA_DIR / "ingestion_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Raw ingestion complete. Manifest generated at %s", manifest_path)
    return manifest


if __name__ == "__main__":
    run_raw_ingestion()
