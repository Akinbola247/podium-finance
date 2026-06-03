from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .injective_client import InjectiveExplorerClient
from .models import WhaleActivity, WatchedWallet
from .redis_client import mark_tx_seen, publish_alert
from .services import (
    build_live_alert_payload,
    generate_structured_summary,
    persist_summary,
    smart_alert_passes,
)
from .market_registry import validate_notional_usd
from .tx_decoder import addresses_in_tx, decode_tx_for_wallet


def ingest_tx_dict(db: Session, decoded: dict[str, Any]) -> WhaleActivity | None:
    tx_hash = decoded.get("tx_hash")
    if not tx_hash:
        return None

    settings = get_settings()
    raw_log = decoded.setdefault("raw_log", {})
    fill_price = float(raw_log.get("fill_price_usd") or 0)
    qty = float(decoded.get("amount") or raw_log.get("fill_quantity") or 0)
    notional, adjusted = validate_notional_usd(
        float(decoded.get("notional_value_usd", 0.0)),
        decoded.get("asset_symbol", "INJ"),
        fill_price=fill_price,
        qty=qty,
    )
    decoded["notional_value_usd"] = notional
    if adjusted:
        raw_log["notional_adjusted"] = True
    if decoded["notional_value_usd"] < settings.min_notional_usd:
        return None

    existing = db.scalar(select(WhaleActivity).where(WhaleActivity.tx_hash == tx_hash))
    if existing:
        return None

    wallet = db.get(WatchedWallet, decoded["wallet_address"])
    if not wallet:
        return None

    row = WhaleActivity(
        event_id=str(uuid.uuid4()),
        wallet_address=decoded["wallet_address"],
        timestamp=decoded["timestamp"],
        activity_type=decoded["activity_type"],
        asset_symbol=decoded["asset_symbol"],
        amount=decoded["amount"],
        notional_value_usd=decoded["notional_value_usd"],
        tx_hash=tx_hash,
        raw_log=decoded["raw_log"],
    )

    row.alert_passed = smart_alert_passes(
        db,
        row.wallet_address,
        row.notional_value_usd,
        row.asset_symbol,
        activity_type=row.activity_type,
    )
    summary = generate_structured_summary(row)
    row.ai_interpretation = summary["structural_narrative"]
    db.add(row)
    db.commit()
    db.refresh(row)
    mark_tx_seen(tx_hash)
    persist_summary(db, row.wallet_address, summary)

    publish_alert(build_live_alert_payload(row, wallet, summary))

    return row


def backfill_wallet(db: Session, address: str, limit: int | None = None) -> int:
    settings = get_settings()
    client = InjectiveExplorerClient()
    txs = client.fetch_account_txs(address, limit=limit or settings.account_tx_backfill_limit)
    ingested = 0
    for tx in txs:
        decoded = decode_tx_for_wallet(tx, address)
        if decoded and ingest_tx_dict(db, decoded):
            ingested += 1
    return ingested


def poll_global_stream(db: Session, watched: set[str] | list[str]) -> int:
    if not watched:
        return 0

    watched_set = set(watched)
    settings = get_settings()
    client = InjectiveExplorerClient()
    txs = client.fetch_latest_txs(limit=settings.global_tx_batch_size)
    ingested = 0

    for tx in txs:
        involved = addresses_in_tx(tx) & watched_set
        for address in involved:
            decoded = decode_tx_for_wallet(tx, address)
            if decoded and ingest_tx_dict(db, decoded):
                ingested += 1
    return ingested


def poll_watched_wallets(
    db: Session,
    watched: list[str],
    *,
    batch_size: int | None = None,
    tx_limit: int | None = None,
) -> int:
    """Poll recent account txs for a rotating subset of the watchlist."""
    if not watched:
        return 0

    settings = get_settings()
    batch_size = batch_size or settings.wallet_poll_batch_size
    tx_limit = tx_limit or settings.wallet_poll_tx_limit

    poll_watched_wallets._cursor = getattr(poll_watched_wallets, "_cursor", 0)  # type: ignore[attr-defined]
    start = poll_watched_wallets._cursor % len(watched)  # type: ignore[attr-defined]
    batch = []
    for i in range(min(batch_size, len(watched))):
        batch.append(watched[(start + i) % len(watched)])
    poll_watched_wallets._cursor = start + len(batch)  # type: ignore[attr-defined]

    client = InjectiveExplorerClient()
    ingested = 0
    for address in batch:
        txs = client.fetch_account_txs(address, limit=tx_limit)
        for tx in txs:
            decoded = decode_tx_for_wallet(tx, address)
            if decoded and ingest_tx_dict(db, decoded):
                ingested += 1
    return ingested
