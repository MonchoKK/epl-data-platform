import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import api_router
from src.config import BASE_DIR
from src.database.connection import get_db_engine
from src.database.models import create_all_tables
from src.database.views import create_analytical_views

logger = logging.getLogger(__name__)

app = FastAPI(
    title="EPL Data Engineering Platform API",
    description=(
        "Production-grade REST API exposing ingested, transformed, and modeled "
        "English Premier League clubs, squads, fixtures, and analytical warehouse views."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for local development and web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router)

# Mount frontend directory if it exists
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


@app.on_event("startup")
def on_startup():
    """Initializes tables and analytical views on server startup."""
    engine = get_db_engine()
    create_all_tables(engine)
    create_analytical_views(engine)
    logger.info("FastAPI application started and data warehouse views verified.")


@app.get("/")
def root():
    """Redirects to documentation or frontend dashboard."""
    return {
        "message": "Welcome to the EPL Club Data Platform API",
        "docs": "/docs",
        "frontend": "/app/index.html",
        "endpoints": {
            "clubs": "/api/clubs",
            "players": "/api/players",
            "matches": "/api/matches",
            "standings": "/api/standings",
            "top_scorers": "/api/analytics/top-scorers",
            "club_summary": "/api/analytics/club-summary",
            "pipeline_trigger": "POST /api/pipeline/trigger",
        },
    }
