#!/usr/bin/env python3
"""Recompute notionals for rows stuck at the legacy $250k flat cap."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import SessionLocal
from app.market_registry import LEGACY_FLAT_CAP_USD, validate_notional_usd
from app.models import WhaleActivity
from app.quant_analysis import _retrofill_price_from_messages


def recompute_row(row: WhaleActivity) -> tuple[float, bool] | None:
    raw = row.raw_log or {}
    retro = _retrofill_price_from_messages(raw)
    if retro:
        price, qty = retro
        return validate_notional_usd(
            round(price * qty, 2),
            row.asset_symbol,
            fill_price=price,
            qty=qty,
        )

    return None


def main() -> None:
    # sqlite:///./podium.db is relative to backend/
    backend_dir = Path(__file__).resolve().parents[1]
    import os

    os.chdir(backend_dir)
    db = SessionLocal()
    rows = db.scalars(
        select(WhaleActivity).where(WhaleActivity.notional_value_usd == LEGACY_FLAT_CAP_USD)
    ).all()
    updated = 0
    for row in rows:
        result = recompute_row(row)
        if not result:
            continue
        new_notional, adjusted = result
        if new_notional <= 0 or abs(new_notional - row.notional_value_usd) < 0.01:
            continue
        row.notional_value_usd = new_notional
        raw = dict(row.raw_log or {})
        if adjusted:
            raw["notional_adjusted"] = True
        else:
            raw.pop("notional_adjusted", None)
        row.raw_log = raw
        updated += 1
    db.commit()
    print(f"Recomputed {updated} / {len(rows)} legacy-capped rows")
    db.close()


if __name__ == "__main__":
    main()
