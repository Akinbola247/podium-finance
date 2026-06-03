import logging
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)


def _sqlite_filesystem_path(url: str) -> Path | None:
    """Return absolute path for sqlite:// URLs, or None for relative paths."""
    if not url.startswith("sqlite:"):
        return None
    # sqlite:////var/data/db.db → /var/data/db.db
    # sqlite:///./podium.db → relative
    remainder = url.split("sqlite://", 1)[-1]
    if remainder.startswith("/"):
        return Path(remainder)
    if remainder.startswith("./"):
        return Path(remainder[2:])
    return Path(remainder) if remainder and not remainder.startswith("?") else None


def _ensure_sqlite_directory(url: str) -> str:
    """
    Ensure SQLite parent dir exists and is writable.
    On Render, /var/data only exists when a persistent disk is mounted — do not mkdir it.
    """
    db_path = _sqlite_filesystem_path(url)
    if db_path is None or not db_path.is_absolute():
        return url

    parent = db_path.parent
    if parent.exists() and os.access(parent, os.W_OK):
        return url

    try:
        parent.mkdir(parents=True, exist_ok=True)
        if os.access(parent, os.W_OK):
            return url
    except OSError as exc:
        logger.warning("Cannot use SQLite path %s (%s)", parent, exc)

    fallback = os.getenv("SQLITE_FALLBACK_URL", "sqlite:///./podium.db")
    logger.warning("Using SQLite fallback %s", fallback)
    return fallback


def _resolve_database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./podium.db")
    if url.startswith("sqlite"):
        return _ensure_sqlite_directory(url)
    return url


DATABASE_URL = _resolve_database_url()


def _engine_connect_args(url: str) -> dict:
    """SQLite needs check_same_thread=False; PostgreSQL does not."""
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(DATABASE_URL, connect_args=_engine_connect_args(DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
