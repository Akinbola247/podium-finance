"""
Injective live stream worker.

Polls the Injective Explorer API for new on-chain transactions involving
watched wallets, persists structured activity, runs alert logic, and
publishes events to Redis for the API WebSocket layer.
"""

from __future__ import annotations

import logging
import sys
import time

from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.ingestion import backfill_wallet, poll_global_stream, poll_watched_wallets
from app.models import WatchedWallet, WhaleActivity
from app.redis_client import ping_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("podium.worker")


def load_watched_addresses(db) -> list[str]:
    rows = db.scalars(select(WatchedWallet.wallet_address)).all()
    return list(rows)


def startup_backfill_empty_wallets(db, watched: list[str]) -> int:
    """Backfill wallets that have no stored activity yet (e.g. after DB reset)."""
    total = 0
    for address in watched:
        count = (
            db.scalar(
                select(func.count())
                .select_from(WhaleActivity)
                .where(WhaleActivity.wallet_address == address)
            )
            or 0
        )
        if count > 0:
            continue
        ingested = backfill_wallet(db, address)
        if ingested:
            logger.info("Startup backfill %s — ingested %s events", address[:16], ingested)
        total += ingested
    return total


def run_cycle() -> None:
    db = SessionLocal()
    try:
        watched = load_watched_addresses(db)
        if not watched:
            logger.info("No wallets on watchlist. Add addresses via POST /api/v1/watchlist")
            return

        global_ingested = poll_global_stream(db, watched)
        wallet_ingested = poll_watched_wallets(db, watched)
        logger.info(
            "Cycle complete — watched=%s global_ingested=%s wallet_ingested=%s",
            len(watched),
            global_ingested,
            wallet_ingested,
        )
    finally:
        db.close()


def main() -> None:
    settings = get_settings()
    if not ping_redis():
        logger.error("Redis unavailable at %s — start Redis before the worker.", settings.redis_url)
        sys.exit(1)

    from app.market_registry import load_market_registry

    registry = load_market_registry()
    logger.info(
        "Podium stream worker started (explorer=%s, poll=%ss, helix_markets=%s)",
        settings.injective_explorer_base,
        settings.poll_interval_seconds,
        len(registry),
    )

    db = SessionLocal()
    try:
        watched = load_watched_addresses(db)
        if watched:
            backfilled = startup_backfill_empty_wallets(db, watched)
            logger.info("Startup backfill finished — wallets=%s ingested=%s", len(watched), backfilled)
    finally:
        db.close()

    while True:
        try:
            run_cycle()
        except Exception:
            logger.exception("Worker cycle failed")
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
