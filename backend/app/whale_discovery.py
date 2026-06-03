"""Live discovery of copy-worthy Helix traders (perp/spot orders only)."""

from __future__ import annotations

import json
import math
import statistics
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from .config import get_settings
from .injective_client import InjectiveExplorerClient
from .market_registry import load_market_registry
from .models import ActivityType
from .redis_client import get_redis
from .tx_decoder import addresses_in_tx, decode_tx_for_wallet

_CACHE_PREFIX = "podium:discover:"
_CACHE_TTL = 3600

COPYABLE_TYPES = frozenset(
    {
        ActivityType.SWAP,
        ActivityType.MARGIN_POSITION_OPEN,
        ActivityType.MARGIN_POSITION_CLOSE,
    }
)


def _is_copyable_activity(activity_type: Any) -> bool:
    if isinstance(activity_type, ActivityType):
        return activity_type in COPYABLE_TYPES
    return str(activity_type) in {t.value for t in COPYABLE_TYPES}


def _trader_score(stats: dict[str, Any], *, prefer_multi_asset: bool) -> float:
    assets: Counter = stats["assets"]
    non_inj = sum(1 for a in assets if a != "INJ")
    exchange = stats["exchange_events"]
    volume = stats["volume_usd"]
    clips: list[float] = stats["clips"]

    median_clip = statistics.median(clips) if clips else 0.0
    max_clip = max(clips) if clips else 0.0

    score = (
        math.log1p(volume) * 5
        + exchange * 12
        + math.log1p(median_clip) * 8
        + math.log1p(max_clip) * 4
        + len(assets) * 4
        + non_inj * 10
    )
    if prefer_multi_asset and non_inj >= 2:
        score += 35
    elif non_inj >= 1:
        score += 20
    return round(score, 2)


def _copyability_tier(stats: dict[str, Any]) -> str:
    vol = stats["volume_usd"]
    ex = stats["exchange_events"]
    clips = stats["clips"]
    max_clip = max(clips) if clips else 0
    non_inj = sum(1 for a in stats["assets"] if a != "INJ")

    if ex >= 8 and vol >= 10_000 and max_clip >= 500:
        return "A"
    if ex >= 4 and vol >= 2_500 and (non_inj >= 1 or max_clip >= 300):
        return "B"
    if ex >= 2 and vol >= 500 and max_clip >= 100:
        return "C"
    return "D"


def _qualifies_as_copy_trader(
    stats: dict[str, Any],
    *,
    min_exchange_events: int,
    min_exchange_volume_usd: float,
    min_largest_clip_usd: float,
) -> bool:
    if stats["exchange_events"] < min_exchange_events:
        return False
    if stats["volume_usd"] < min_exchange_volume_usd:
        return False
    clips = stats["clips"]
    if not clips or max(clips) < min_largest_clip_usd:
        return False
    return True


def discover_active_whales(
    *,
    limit: int = 100,
    scan_pages: int = 30,
    page_size: int = 80,
    min_notional_usd: float = 50,
    max_notional_usd: float = 10_000_000,
    min_exchange_events: int = 2,
    min_exchange_volume_usd: float = 300,
    min_largest_clip_usd: float = 75,
    prefer_multi_asset: bool = True,
    exclude_addresses: set[str] | None = None,
) -> dict[str, Any]:
    """
    Scan recent global Injective txs; return only Helix perp/spot traders worth analyzing.
    Bank transfers, LP, and staking flows are excluded.
    """
    load_market_registry()
    settings = get_settings()
    client = InjectiveExplorerClient()
    exclude = exclude_addresses or set()

    scan_pages = min(scan_pages, 50)
    page_size = min(page_size, 80)

    txs = client.fetch_latest_txs_pages(pages=scan_pages, page_size=page_size)
    trader_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "assets": Counter(),
            "exchange_events": 0,
            "volume_usd": 0.0,
            "clips": [],
            "last_seen": None,
        }
    )
    ecosystem_assets: Counter = Counter()
    skipped_non_trade = 0

    for tx in txs:
        for addr in addresses_in_tx(tx):
            if not addr.startswith("inj1") or addr in exclude:
                continue
            decoded = decode_tx_for_wallet(tx, addr)
            if not decoded:
                continue

            activity_type = decoded.get("activity_type")
            if not _is_copyable_activity(activity_type):
                skipped_non_trade += 1
                continue

            notional = float(decoded.get("notional_value_usd", 0))
            if notional < min_notional_usd or notional > max_notional_usd:
                continue

            stats = trader_stats[addr]
            stats["exchange_events"] += 1
            stats["volume_usd"] += notional
            stats["clips"].append(notional)
            asset = decoded["asset_symbol"]
            stats["assets"][asset] += 1
            ecosystem_assets[asset] += 1

            ts = tx.get("block_timestamp")
            if ts:
                stats["last_seen"] = ts

    candidates: list[dict[str, Any]] = []
    for addr, stats in trader_stats.items():
        if not _qualifies_as_copy_trader(
            stats,
            min_exchange_events=min_exchange_events,
            min_exchange_volume_usd=min_exchange_volume_usd,
            min_largest_clip_usd=min_largest_clip_usd,
        ):
            continue

        non_inj = [s for s in stats["assets"] if s != "INJ"]
        top_assets = sorted(
            stats["assets"].keys(),
            key=lambda a: stats["assets"][a],
            reverse=True,
        )
        label_assets = [a for a in top_assets if a != "INJ"][:5] or top_assets[:4]
        tier = _copyability_tier(stats)
        median_clip = round(statistics.median(stats["clips"]), 2)
        max_clip = round(max(stats["clips"]), 2)

        candidates.append(
            {
                "address": addr,
                "label": f"Helix {tier} · {', '.join(label_assets)}",
                "category": "copyable_trader",
                "copyability_tier": tier,
                "score": _trader_score(stats, prefer_multi_asset=prefer_multi_asset),
                "exchange_events_sampled": stats["exchange_events"],
                "exchange_volume_usd": round(stats["volume_usd"], 2),
                "median_clip_usd": median_clip,
                "largest_clip_usd": max_clip,
                "volume_usd_sampled": round(stats["volume_usd"], 2),
                "assets_seen": dict(stats["assets"]),
                "asset_count": len(stats["assets"]),
                "non_inj_asset_count": len(non_inj),
                "top_assets": top_assets[:8],
                "last_seen": stats["last_seen"],
                "source": "live_explorer_scan",
            }
        )

    candidates.sort(
        key=lambda w: (
            {"A": 4, "B": 3, "C": 2, "D": 1}.get(w["copyability_tier"], 0),
            w["score"],
        ),
        reverse=True,
    )

    whales = candidates[:limit]
    if prefer_multi_asset and len(candidates) > limit:
        by_primary: dict[str, list[dict]] = defaultdict(list)
        for row in candidates:
            non_inj = [a for a in row["top_assets"] if a != "INJ"]
            key = non_inj[0] if non_inj else row["top_assets"][0]
            by_primary[key].append(row)

        diversified: list[dict] = []
        seen_addr: set[str] = set()
        buckets = sorted(by_primary.values(), key=len, reverse=True)
        max_rounds = max(len(b) for b in buckets) if buckets else 0
        for round_i in range(max_rounds):
            if len(diversified) >= limit:
                break
            for bucket in buckets:
                if round_i < len(bucket) and len(diversified) < limit:
                    row = bucket[round_i]
                    if row["address"] not in seen_addr:
                        diversified.append(row)
                        seen_addr.add(row["address"])
        for row in candidates:
            if len(diversified) >= limit:
                break
            if row["address"] not in seen_addr:
                diversified.append(row)
                seen_addr.add(row["address"])
        whales = diversified[:limit]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "network": "injective-1 mainnet",
        "explorer_url": settings.injective_explorer_base,
        "criteria": {
            "copyable_only": True,
            "min_per_trade_usd": min_notional_usd,
            "min_exchange_events": min_exchange_events,
            "min_exchange_volume_usd": min_exchange_volume_usd,
            "min_largest_clip_usd": min_largest_clip_usd,
            "excluded": ["LARGE_TRANSFER", "LIQUIDITY_PROVISION", "staking/delegation"],
        },
        "scanned_txs": len(txs),
        "scan_pages": scan_pages,
        "page_size": page_size,
        "skipped_non_trade_events": skipped_non_trade,
        "unique_traders_seen": len(trader_stats),
        "qualified_traders": len(candidates),
        "returned": len(whales),
        "ecosystem_assets_seen": dict(ecosystem_assets.most_common(40)),
        "whales": whales,
    }


def cache_discovery_result(payload: dict[str, Any]) -> str:
    search_id = str(uuid.uuid4())
    try:
        redis = get_redis()
        redis.setex(
            f"{_CACHE_PREFIX}{search_id}",
            _CACHE_TTL,
            json.dumps(payload, default=str),
        )
    except Exception:
        pass
    return search_id


def get_cached_discovery(search_id: str) -> dict[str, Any] | None:
    try:
        redis = get_redis()
        raw = redis.get(f"{_CACHE_PREFIX}{search_id}")
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None
