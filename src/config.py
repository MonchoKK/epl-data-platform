import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Base project paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Database Configuration
# Default is SQLite for out-of-the-box local development without requiring external server setups,
# while seamlessly allowing PostgreSQL via DATABASE_URL environment variable.
DEFAULT_DB_PATH = BASE_DIR / "epl_warehouse.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# Current Season and Source Settings
CURRENT_SEASON = os.getenv("EPL_SEASON", "2024-2025")
DATA_SOURCE_NAME = "PremierLeague_Official_Extract"


def ensure_directories() -> None:
    """Ensures raw and processed data lake directories exist on the filesystem."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_database_url() -> str:
    """Returns the configured database URL."""
    return DATABASE_URL
