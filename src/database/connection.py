import logging
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from src.config import get_database_url

logger = logging.getLogger(__name__)

Base = declarative_base()

_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def get_db_engine(db_url: str | None = None) -> Engine:
    """Creates and returns the SQLAlchemy Engine singleton.

    Configures connection pooling and dialect-specific optimizations.
    Enforces SQLite foreign key constraints if running in SQLite mode.

    Args:
        db_url: Optional connection string override.

    Returns:
        SQLAlchemy Engine instance.
    """
    global _engine, _SessionFactory
    if _engine is None or db_url is not None:
        target_url = db_url or get_database_url()

        connect_args = {}
        if target_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        _engine = create_engine(
            target_url,
            connect_args=connect_args,
            echo=False,
            future=True,
        )

        # Enforce foreign key constraints in SQLite
        if target_url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        _SessionFactory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
        logger.info("Initialized database engine with URL: %s", target_url.split("@")[-1])

    return _engine


@contextmanager
def get_db_session(engine: Engine | None = None) -> Generator[Session, None, None]:
    """Context manager for transactional database sessions.

    Automatically commits on success or rolls back on exception.

    Yields:
        Active SQLAlchemy Session.
    """
    global _SessionFactory
    if _SessionFactory is None or engine is not None:
        eng = engine or get_db_engine()
        _SessionFactory = sessionmaker(bind=eng, autoflush=False, autocommit=False)

    session: Session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error("Session transaction rolled back due to error: %s", exc)
        raise
    finally:
        session.close()


def check_connection(engine: Engine | None = None) -> bool:
    """Verifies active connectivity to the relational data warehouse.

    Returns:
        True if connection is healthy, False otherwise.
    """
    eng = engine or get_db_engine()
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as err:
        logger.error("Database connection check failed: %s", err)
        return False
