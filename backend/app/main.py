import asyncio
import json
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, SessionLocal, engine, get_db
from .ingestion import backfill_wallet
from .models import WhaleActivity, WatchedWallet
from .redis_client import get_async_redis, ping_redis
from pathlib import Path

from .schemas import (
    ActiveTradersImport,
    ActivityItem,
    RiskExecutionPlanRequest,
    RiskExecutionPlanResponse,
    WhaleDiscoverImportRequest,
    WhaleDiscoverRequest,
    WatchlistBulkImport,
    WatchlistCreate,
    WatchlistCreateResponse,
)
from .whale_discovery import (
    cache_discovery_result,
    discover_active_whales,
    get_cached_discovery,
)
from .quant_analysis import (
    _effective_activity_type,
    analyze_wallet_quant,
    enrich_fills_with_pnl,
    fill_from_activity,
)
from .services import (
    alert_summary_from_row,
    build_execution_plan,
    build_live_alert_payload,
    classify_strategy,
    compute_conviction_score,
    generate_structured_summary,
    persist_summary,
    smart_alert_passes,
    validate_injective_address,
    watchlist_address_error,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Podium Finance API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/markets/summary")
def markets_summary():
    from .market_registry import load_market_registry

    registry = load_market_registry()
    assets = sorted({m["base_asset"] for m in registry.values()})
    return {
        "total_markets": len(registry),
        "unique_base_assets": len(assets),
        "sample_assets": assets[:40],
        "note": "Helix spot + perpetual markets on Injective mainnet",
    }


@app.get("/health")
def health(db: Session = Depends(get_db)):
    settings = get_settings()
    watched_count = db.scalar(select(func.count()).select_from(WatchedWallet)) or 0
    activity_count = db.scalar(select(func.count()).select_from(WhaleActivity)) or 0
    return {
        "status": "ok",
        "service": "podium-finance-backend",
        "redis": ping_redis(),
        "data_source": "injective_explorer_live",
        "explorer_url": settings.injective_explorer_base,
        "watched_wallets": watched_count,
        "stored_activities": activity_count,
    }


def _recent_smart_alert_messages(limit: int = 15) -> list[str]:
    """Serialize recent smart alerts for WebSocket bootstrap (sync, run in thread)."""
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(WhaleActivity)
            .where(WhaleActivity.alert_passed.is_(True))
            .order_by(desc(WhaleActivity.timestamp))
            .limit(limit)
        ).all()
        messages: list[str] = []
        for row in rows:
            wallet = db.get(WatchedWallet, row.wallet_address)
            summary = alert_summary_from_row(row)
            payload = build_live_alert_payload(row, wallet, summary)
            messages.append(json.dumps(payload, default=str))
        return messages
    finally:
        db.close()


@app.get("/api/v1/alerts/recent")
def recent_smart_alerts(
    limit: int = Query(default=15, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Recent smart alerts for UI fallback when WebSocket reconnects."""
    rows = db.scalars(
        select(WhaleActivity)
        .where(WhaleActivity.alert_passed.is_(True))
        .order_by(desc(WhaleActivity.timestamp))
        .limit(limit)
    ).all()
    out = []
    for row in rows:
        wallet = db.get(WatchedWallet, row.wallet_address)
        summary = alert_summary_from_row(row)
        out.append(build_live_alert_payload(row, wallet, summary))
    return out


@app.websocket("/api/v1/alerts/ws")
async def alerts_websocket(websocket: WebSocket):
    """Keep connection alive with periodic heartbeats; resilient Redis pub/sub loop."""
    await websocket.accept()
    settings = get_settings()
    stop = asyncio.Event()

    try:
        bootstrap = await asyncio.to_thread(_recent_smart_alert_messages, 15)
        for raw in bootstrap:
            await websocket.send_text(raw)
        if bootstrap:
            await websocket.send_text(
                json.dumps({"type": "bootstrap_complete", "count": len(bootstrap)})
            )
    except Exception:
        pass

    async def heartbeat_sender() -> None:
        while not stop.is_set():
            await asyncio.sleep(15)
            try:
                await websocket.send_text(json.dumps({"type": "heartbeat", "ts": datetime.now(timezone.utc).isoformat()}))
            except Exception:
                stop.set()
                break

    async def redis_forwarder() -> None:
        while not stop.is_set():
            pubsub = None
            try:
                redis = get_async_redis()
                pubsub = redis.pubsub()
                await pubsub.subscribe(settings.redis_alerts_channel)
                async for message in pubsub.listen():
                    if stop.is_set():
                        break
                    if message.get("type") != "message":
                        continue
                    data = message.get("data")
                    if isinstance(data, bytes):
                        data = data.decode()
                    await websocket.send_text(data if isinstance(data, str) else json.dumps(data))
            except WebSocketDisconnect:
                stop.set()
                break
            except Exception:
                # Redis blip: retry subscription without dropping the WebSocket.
                await asyncio.sleep(2)
            finally:
                if pubsub is not None:
                    try:
                        await pubsub.unsubscribe(settings.redis_alerts_channel)
                        await pubsub.close()
                    except Exception:
                        pass

    hb_task = asyncio.create_task(heartbeat_sender())
    try:
        await redis_forwarder()
    except WebSocketDisconnect:
        pass
    finally:
        stop.set()
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass


@app.get("/api/v1/watchlist")
def list_watchlist(db: Session = Depends(get_db)):
    rows = db.scalars(select(WatchedWallet).order_by(WatchedWallet.tracking_since.desc())).all()
    return [
        {
            "wallet_address": row.wallet_address,
            "alias": row.alias,
            "risk_category_override": row.risk_category_override,
            "tracking_since": row.tracking_since.isoformat(),
            "conviction_score": row.conviction_score,
        }
        for row in rows
    ]


def _backfill_task(address: str) -> None:
    import logging

    logger = logging.getLogger("podium.backfill")
    db = SessionLocal()
    try:
        count = backfill_wallet(db, address)
        logger.info("Backfill %s — ingested %s events", address[:16], count)
        publish_status = {"type": "backfill_complete", "wallet_address": address, "ingested": count}
        from .redis_client import publish_alert

        publish_alert(publish_status)
    except Exception:
        logger.exception("Backfill failed for %s", address)
    finally:
        db.close()


@app.post("/api/v1/watchlist", response_model=WatchlistCreateResponse)
def create_watchlist(
    payload: WatchlistCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    addr_err = watchlist_address_error(payload.wallet_address)
    if addr_err:
        raise HTTPException(status_code=400, detail=addr_err)

    existing = db.get(WatchedWallet, payload.wallet_address)
    if existing:
        background_tasks.add_task(_backfill_task, existing.wallet_address)
        return {
            "status": "success",
            "data": {
                "watchlist_id": f"wch_{existing.wallet_address[:8]}",
                "wallet_address": existing.wallet_address,
                "tracking_since": existing.tracking_since.isoformat() + "Z",
                "backfill": "queued",
            },
        }

    wallet = WatchedWallet(
        wallet_address=payload.wallet_address,
        alias=payload.alias,
        risk_category_override=payload.risk_category_override,
    )
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    background_tasks.add_task(_backfill_task, wallet.wallet_address)

    return {
        "status": "success",
        "data": {
            "watchlist_id": f"wch_{wallet.wallet_address[:8]}",
            "wallet_address": wallet.wallet_address,
            "tracking_since": wallet.tracking_since.isoformat() + "Z",
            "backfill": "queued",
        },
    }


@app.post("/api/v1/whales/discover")
def discover_whales(payload: WhaleDiscoverRequest, db: Session = Depends(get_db)):
    """
    Live scan for copy-worthy Helix traders (perp/spot only — no stakers or bank transfers).
    """
    exclude: set[str] = set()
    if payload.exclude_watchlist:
        exclude = set(db.scalars(select(WatchedWallet.wallet_address)).all())

    result = discover_active_whales(
        limit=payload.limit,
        scan_pages=payload.scan_pages,
        page_size=payload.page_size,
        min_notional_usd=payload.min_notional_usd,
        min_exchange_events=payload.min_exchange_events,
        min_exchange_volume_usd=payload.min_exchange_volume_usd,
        min_largest_clip_usd=payload.min_largest_clip_usd,
        prefer_multi_asset=payload.prefer_multi_asset,
        exclude_addresses=exclude,
    )
    search_id = cache_discovery_result(result)
    return {
        "status": "success",
        "search_id": search_id,
        "criteria": result["criteria"],
        "scanned_txs": result["scanned_txs"],
        "qualified_traders": result["qualified_traders"],
        "returned": result["returned"],
        "ecosystem_assets_seen": result["ecosystem_assets_seen"],
        "whales": result["whales"],
        "note": (
            "Only Helix perp/spot fills (SWAP, margin open/close). "
            "Tier A/B/C = highest copy signal. Cached ~1h — import via /whales/discover/import."
        ),
    }


@app.post("/api/v1/whales/discover/import")
def import_discovered_whales(
    payload: WhaleDiscoverImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Import whales from a prior discover search (by search_id)."""
    cached = get_cached_discovery(payload.search_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail="Search expired or not found. Run POST /api/v1/whales/discover again.",
        )

    whales = cached.get("whales", [])
    if payload.addresses:
        allow = set(payload.addresses)
        whales = [w for w in whales if w.get("address") in allow]
    whales = whales[: payload.limit]

    added: list[dict[str, str | None]] = []
    skipped = []
    for w in whales:
        address = str(w.get("address", "")).strip()
        if watchlist_address_error(address):
            skipped.append({"address": address, "reason": "invalid"})
            continue
        if db.get(WatchedWallet, address):
            skipped.append({"address": address, "reason": "already_tracked"})
            background_tasks.add_task(_backfill_task, address)
            continue
        label = w.get("label")
        wallet = WatchedWallet(
            wallet_address=address,
            alias=label,
            risk_category_override="aggressive",
        )
        db.add(wallet)
        db.commit()
        background_tasks.add_task(_backfill_task, address)
        added.append({"address": address, "alias": label})

    return {
        "status": "success",
        "data_source": "live_discovery",
        "imported": len(added),
        "rebackfill_queued": len([s for s in skipped if s.get("reason") == "already_tracked"]),
        "skipped": skipped,
        "addresses": [a["address"] for a in added],
        "wallets_added": added,
        "message": (
            f"Added {len(added)} wallet(s) to your watchlist. "
            "Live backfill from Injective explorer is queued for each."
        ),
    }


@app.post("/api/v1/watchlist/sync")
def sync_watchlist(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Queue backfill for every wallet on the watchlist (use after DB reset)."""
    rows = db.scalars(select(WatchedWallet.wallet_address)).all()
    for address in rows:
        background_tasks.add_task(_backfill_task, address)
    return {"status": "success", "queued": len(rows)}


@app.post("/api/v1/watchlist/import-active-traders")
def import_active_traders(
    payload: ActiveTradersImport,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Import Helix-active traders from data/injective_active_traders.json."""
    seed_path = Path(__file__).resolve().parents[2] / "data" / "injective_active_traders.json"
    if not seed_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Seed file not found. Run: python3 scripts/discover_active_traders.py",
        )

    with seed_path.open(encoding="utf-8") as f:
        seed = json.load(f)

    candidates = seed.get("traders", [])[: payload.limit]
    added = []
    skipped = []
    for w in candidates:
        address = str(w.get("address", "")).strip()
        if watchlist_address_error(address):
            skipped.append({"address": address, "reason": "invalid"})
            continue
        if db.get(WatchedWallet, address):
            skipped.append({"address": address, "reason": "already_tracked"})
            background_tasks.add_task(_backfill_task, address)
            continue
        wallet = WatchedWallet(
            wallet_address=address,
            alias=w.get("label"),
            risk_category_override="aggressive",
        )
        db.add(wallet)
        db.commit()
        background_tasks.add_task(_backfill_task, address)
        added.append(address)

    return {
        "status": "success",
        "data_source": "static_snapshot",
        "imported": len(added),
        "rebackfill_queued": len([s for s in skipped if s.get("reason") == "already_tracked"]),
        "skipped": skipped,
        "addresses": added,
        "warning": (
            "Imported from a static JSON snapshot, not a live scan. "
            "Prefer POST /api/v1/whales/discover for live Helix trader discovery."
        ),
    }


@app.post("/api/v1/watchlist/import-whales")
def import_whale_seed(
    payload: WatchlistBulkImport,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Import inj1-only whales from data/injective_whale_addresses_inj1_only.json."""
    seed_path = Path(__file__).resolve().parents[2] / "data" / "injective_whale_addresses_inj1_only.json"
    if not seed_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Seed file not found: data/injective_whale_addresses_inj1_only.json",
        )

    with seed_path.open(encoding="utf-8") as f:
        seed = json.load(f)

    candidates = [
        w
        for w in seed.get("whales", [])
        if str(w.get("address", "")).startswith("inj1")
        and float(w.get("inj_staked", w.get("inj_balance", 0)) or 0) >= payload.min_inj_staked
    ]
    candidates.sort(
        key=lambda w: float(w.get("inj_staked", w.get("inj_balance", 0)) or 0),
        reverse=True,
    )
    candidates = candidates[: payload.limit]

    added = []
    skipped = []
    for w in candidates:
        address = w["address"].strip()
        if watchlist_address_error(address):
            skipped.append({"address": address, "reason": "invalid"})
            continue
        if db.get(WatchedWallet, address):
            skipped.append({"address": address, "reason": "already_tracked"})
            continue
        wallet = WatchedWallet(
            wallet_address=address,
            alias=w.get("label"),
            risk_category_override="moderate",
        )
        db.add(wallet)
        db.commit()
        background_tasks.add_task(_backfill_task, address)
        added.append(address)

    return {
        "status": "success",
        "data_source": "static_snapshot",
        "imported": len(added),
        "skipped": len(skipped),
        "addresses": added,
        "warning": (
            "Imported from static staker list (low copy-trade signal). "
            "Use live discovery for active Helix traders."
        ),
    }


@app.get("/api/v1/whales/profile/{address}")
def whale_profile(address: str, db: Session = Depends(get_db)):
    wallet = db.get(WatchedWallet, address)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found in watchlist.")

    metrics = compute_conviction_score(db, address)
    strategy = classify_strategy(db, address)
    wallet.conviction_score = metrics["conviction_score"]
    wallet.strategy_fingerprint = strategy
    wallet.last_analyzed_at = datetime.now(timezone.utc)
    db.commit()

    activities = db.scalars(
        select(WhaleActivity)
        .where(WhaleActivity.wallet_address == address)
        .order_by(desc(WhaleActivity.timestamp))
        .limit(200)
    ).all()
    total = sum(a.notional_value_usd for a in activities) or 1.0
    by_asset = {}
    for act in activities:
        by_asset.setdefault(act.asset_symbol, 0.0)
        by_asset[act.asset_symbol] += act.notional_value_usd

    distribution = [
        {"asset": asset, "percentage": round(value / total, 2)} for asset, value in by_asset.items()
    ]

    quant = analyze_wallet_quant(db, address, days=30)

    return {
        "address": wallet.wallet_address,
        "alias": wallet.alias,
        "metrics": {
            "conviction_score": wallet.conviction_score,
            "win_rate_proxy": metrics["win_rate_proxy"],
            "win_rate_pct": metrics.get("win_rate_pct"),
            "realized_pnl_usd": metrics.get("realized_pnl_usd"),
            "unrealized_pnl_usd": metrics.get("unrealized_pnl_usd"),
            "combined_pnl_usd": metrics.get("combined_pnl_usd"),
            "profit_factor": metrics.get("profit_factor"),
            "recent_directional_bias": metrics.get("recent_directional_bias"),
            "total_value_locked_usd": round(total, 2),
            "average_holding_period_hours": round(metrics["holding_time"] * 3.36, 1),
            "dominant_strategy": wallet.strategy_fingerprint,
        },
        "quant_analysis": quant,
        "portfolio_distribution": distribution,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/whales/activity", response_model=list[ActivityItem])
def whale_activity(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    only_alerted: bool = Query(default=False),
    wallet_address: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = select(WhaleActivity)
    if wallet_address:
        query = query.where(WhaleActivity.wallet_address == wallet_address)
    if only_alerted:
        query = query.where(WhaleActivity.alert_passed.is_(True))
    query = query.order_by(desc(WhaleActivity.timestamp)).offset(offset).limit(limit)
    rows = db.scalars(query).all()
    fill_map = enrich_fills_with_pnl(db, rows)
    result = []
    for row in rows:
        fill = fill_map.get(row.event_id) or fill_from_activity(row)
        pnl_kind = None
        pnl_realized = None
        pnl_unrealized = None
        if fill:
            if fill.realized_pnl_usd is not None:
                pnl_kind = "realized"
                pnl_realized = fill.realized_pnl_usd
            elif fill.unrealized_pnl_usd is not None:
                pnl_kind = "unrealized"
                pnl_unrealized = fill.unrealized_pnl_usd
        effective_type = _effective_activity_type(row)
        result.append(
            ActivityItem(
                event_id=row.event_id,
                wallet_address=row.wallet_address,
                timestamp=row.timestamp,
                activity_type=effective_type.value,
                asset_affected=row.asset_symbol,
                notional_value_usd=row.notional_value_usd,
                notional_adjusted=bool((row.raw_log or {}).get("notional_adjusted")),
                raw_payload_summary=row.raw_log,
                ai_interpretation=row.ai_interpretation,
                fill_price_usd=fill.fill_price_usd if fill else None,
                execution_side=fill.side if fill else None,
                realized_pnl_usd=pnl_realized,
                unrealized_pnl_usd=pnl_unrealized,
                pnl_kind=pnl_kind,
            )
        )
    return result


@app.post("/api/v1/risk/execution-plan", response_model=RiskExecutionPlanResponse)
def risk_execution_plan(payload: RiskExecutionPlanRequest, db: Session = Depends(get_db)):
    event = db.get(WhaleActivity, payload.whale_event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Whale event not found.")

    metrics = compute_conviction_score(db, event.wallet_address)
    metrics["dominant_strategy"] = classify_strategy(db, event.wallet_address)
    return build_execution_plan(
        event,
        metrics,
        payload.user_portfolio_usd,
        payload.max_drawdown_tolerance_percent,
        payload.leverage_cap,
        db=db,
    )


@app.post("/api/v1/internal/simulate-summary/{event_id}")
def simulate_summary(event_id: str, db: Session = Depends(get_db)):
    event = db.get(WhaleActivity, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
    event.alert_passed = smart_alert_passes(db, event.wallet_address, event.notional_value_usd, event.asset_symbol)
    summary_payload = generate_structured_summary(event)
    event.ai_interpretation = summary_payload["structural_narrative"]
    db.commit()
    persist_summary(db, event.wallet_address, summary_payload)
    return {"status": "ok", "alert_passed": event.alert_passed, "summary": summary_payload}
