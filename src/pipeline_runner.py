import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict

from src.database.connection import check_connection, get_db_engine
from src.database.loader import load_all_processed_data
from src.ingestion.pipeline import run_raw_ingestion
from src.transform.pipeline import run_transformations

logger = logging.getLogger("epl_pipeline")


def run_full_pipeline() -> Dict[str, Any]:
    """Executes the complete End-to-End EPL Data Engineering Pipeline.

    Sequence of stages:
    1. EXTRACT: Fetches raw clubs, players, matches, and standings into bronze storage (data/raw/).
    2. TRANSFORM: Validates, cleans, types, and enriches datasets into silver storage (data/processed/).
    3. LOAD: Creates relational DDL models and analytical views, then idempotently populates tables.

    Returns:
        Summary dictionary containing execution metrics, counts, and timing.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    )

    start_time = time.time()
    logger.info("=================================================================")
    logger.info("  🚀 STARTING EPL CLUB DATA PLATFORM - END-TO-END DATA PIPELINE  ")
    logger.info("=================================================================")

    # Stage 0: Health check
    engine = get_db_engine()
    if not check_connection(engine):
        logger.error("Database connection failure. Halting pipeline.")
        sys.exit(1)

    # Stage 1: Ingestion (Bronze)
    logger.info("\n--- [STAGE 1/3] INGESTION (BRONZE LAYER) ---")
    ingestion_result = run_raw_ingestion()

    # Stage 2: Transformation (Silver)
    logger.info("\n--- [STAGE 2/3] TRANSFORMATION (SILVER LAYER) ---")
    transform_result = run_transformations()

    # Stage 3: Loading (Gold / Relational Data Warehouse)
    logger.info("\n--- [STAGE 3/3] WAREHOUSE LOADING (GOLD LAYER) ---")
    loader_result = load_all_processed_data(
        engine=engine,
        dataframes=transform_result["dataframes"],
    )

    elapsed_time = round(time.time() - start_time, 2)
    logger.info("=================================================================")
    logger.info("  ✅ EPL DATA PIPELINE COMPLETED SUCCESSFULLY IN %s SECONDS  ", elapsed_time)
    logger.info("  Records ingested: %d", ingestion_result["total_records"])
    logger.info("  Records transformed: %d", transform_result["manifest"]["total_processed_rows"])
    logger.info("  Records loaded to warehouse: %d", loader_result["total_loaded"])
    logger.info("=================================================================")

    return {
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed_time,
        "ingestion": ingestion_result,
        "transformation": transform_result["manifest"],
        "loader": loader_result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EPL Data Platform Pipeline Orchestrator")
    parser.parse_args()
    run_full_pipeline()
