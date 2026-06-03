from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .market_registry import validate_notional_usd
from .models import ActivityType, AISummary, WhaleActivity

COPYABLE_ACTIVITY = frozenset(
    {
        ActivityType.SWAP,
        ActivityType.MARGIN_POSITION_OPEN,
        ActivityType.MARGIN_POSITION_CLOSE,
    }
)
from .quant_analysis import analyze_wallet_quant, generate_trade_conclusion, quant_context_for_event


def validate_injective_address(address: str) -> bool:
    addr = address.strip()
    return addr.startswith("inj1") and 39 <= len(addr) <= 45


def watchlist_address_error(address: str) -> str | None:
    """Return a user-facing error if address cannot be added to watchlist."""
    addr = address.strip()
    if not addr:
        return "Wallet address is required."
    if addr.startswith("injvaloper"):
        return (
            "Validator operator addresses (injvaloper...) cannot be tracked. "
            "Use inj1... accounts from data/injective_whale_addresses_inj1_only.json."
        )
    if addr.startswith("0x"):
        return (
            "Ethereum (0x...) addresses are not supported. "
            "Use native inj1... addresses only."
        )
    if addr.startswith("inj") and not addr.startswith("inj1"):
        return f"Unsupported address prefix ({addr[:16]}...). Only inj1... wallets are valid."
    if not validate_injective_address(addr):
        return "Invalid Injective wallet address. Must be a native inj1... account (39–45 characters)."
    return None


def alert_summary_from_row(row: WhaleActivity) -> dict[str, Any]:
    """Derive alert metadata from stored activity — never use fixed stub tiers."""
    raw = row.raw_log or {}
    notional = float(row.notional_value_usd or 0)
    if notional >= 250_000:
        tier = "HIGH"
    elif notional >= 75_000:
        tier = "MEDIUM"
    else:
        tier = "LOW"
    live = raw.get("source") == "injective_explorer_live"
    confidence = 0.9 if live and row.ai_interpretation else 0.75 if live else 0.55
    return {
        "structural_narrative": row.ai_interpretation or "",
        "execution_urgency_tier": tier,
        "confidence_metric": round(confidence, 2),
        "data_source": "injective_explorer_live" if live else "unknown",
    }


def build_live_alert_payload(
    row: WhaleActivity,
    wallet: Any,
    summary: dict,
) -> dict[str, Any]:
    """Redis/WebSocket payload for live feed (smart alert vs background activity)."""
    base = {
        "event_id": row.event_id,
        "wallet_address": row.wallet_address,
        "alias": getattr(wallet, "alias", None),
        "timestamp": row.timestamp.isoformat(),
        "activity_type": row.activity_type.value,
        "asset_affected": row.asset_symbol,
        "notional_value_usd": row.notional_value_usd,
        "ai_interpretation": row.ai_interpretation,
        "tx_hash": row.tx_hash,
        "alert_passed": row.alert_passed,
    }
    if row.alert_passed:
        return {
            **base,
            "type": "whale_alert",
            "execution_urgency_tier": summary.get("execution_urgency_tier"),
            "confidence_metric": summary.get("confidence_metric"),
            "data_source": summary.get("data_source", "injective_explorer_live"),
        }
    return {**base, "type": "activity", "data_source": (row.raw_log or {}).get("source")}


def smart_alert_passes(
    db: Session,
    wallet_address: str,
    tx_value_usd: float,
    asset: str,
    *,
    activity_type: ActivityType | None = None,
) -> bool:
    """
    Decide if an event should surface as a live smart alert.
    Uses capped notionals so one bad tick decode does not break future alerts.
    """
    settings = get_settings()
    tx_value_usd, _ = validate_notional_usd(tx_value_usd, asset)

    recent_values = db.scalars(
        select(WhaleActivity.notional_value_usd)
        .where(WhaleActivity.wallet_address == wallet_address)
        .order_by(desc(WhaleActivity.timestamp))
        .limit(50)
    ).all()
    sane_recent = [float(v) for v in recent_values if float(v) > 0]

    seen_asset = db.scalar(
        select(func.count())
        .select_from(WhaleActivity)
        .where(
            WhaleActivity.wallet_address == wallet_address,
            WhaleActivity.asset_symbol == asset,
        )
    )
    asset_is_new = (seen_asset or 0) == 0
    is_exchange = activity_type in COPYABLE_ACTIVITY if activity_type else False

    if asset_is_new and tx_value_usd >= settings.min_notional_usd:
        return True

    if is_exchange and tx_value_usd >= settings.large_transfer_usd:
        if len(sane_recent) < 3:
            return True
        historical_median = median(sane_recent) if sane_recent else tx_value_usd
        if tx_value_usd >= max(settings.large_transfer_usd, historical_median * 1.25):
            return True

    if sane_recent:
        historical_median = median(sane_recent)
        if tx_value_usd >= max(1000.0, historical_median * 2.0):
            return True

    return False


def compute_conviction_score(db: Session, wallet_address: str) -> dict:
    quant = analyze_wallet_quant(db, wallet_address, days=30)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    acts = db.scalars(
        select(WhaleActivity).where(
            WhaleActivity.wallet_address == wallet_address, WhaleActivity.timestamp >= cutoff
        )
    ).all()
    if not acts:
        return {
            "conviction_score": 0.0,
            "win_rate_proxy": 0.0,
            "size_discipline": 0.0,
            "holding_time": 0.0,
            "realized_pnl_usd": 0.0,
            "win_rate_pct": 0.0,
        }

    win_rate = float(quant.get("win_rate_pct") or 0.0)
    closes = [a for a in acts if a.activity_type == ActivityType.MARGIN_POSITION_CLOSE]
    if quant.get("closed_trades_count", 0) == 0:
        wins = sum(1 for c in closes if c.raw_log.get("pnl_usd", 0) > 0)
        win_rate = (wins / len(closes)) * 100 if closes else 50.0

    sizes = [a.notional_value_usd for a in acts]
    avg = sum(sizes) / len(sizes)
    variance = sum((s - avg) ** 2 for s in sizes) / len(sizes) if sizes else 0
    variance_pct = (variance**0.5 / avg) * 100 if avg else 100
    size_discipline = max(0.0, 100 - min(100.0, variance_pct))

    holding_windows = []
    for close in closes:
        opened_at = close.raw_log.get("opened_at")
        if opened_at:
            try:
                start = datetime.fromisoformat(opened_at)
                holding_windows.append((close.timestamp - start).total_seconds() / 3600)
            except ValueError:
                continue
    avg_holding_h = sum(holding_windows) / len(holding_windows) if holding_windows else 24.0
    holding_time = min(100.0, (avg_holding_h / (24 * 14)) * 100)

    pnl_score = 50.0
    combined_pnl = float(quant.get("combined_pnl_usd") or 0)
    if combined_pnl > 50_000:
        pnl_score = 85.0
    elif combined_pnl > 0:
        pnl_score = 65.0
    elif combined_pnl < -10_000:
        pnl_score = 25.0

    conviction = (
        (0.30 * win_rate)
        + (0.25 * size_discipline)
        + (0.15 * holding_time)
        + (0.30 * pnl_score)
    )
    return {
        "conviction_score": round(conviction, 2),
        "win_rate_proxy": round(win_rate / 100, 3),
        "size_discipline": round(size_discipline, 2),
        "holding_time": round(holding_time, 2),
        "realized_pnl_usd": quant.get("total_realized_pnl_usd", 0),
        "unrealized_pnl_usd": quant.get("unrealized_pnl_usd", 0),
        "combined_pnl_usd": quant.get("combined_pnl_usd", 0),
        "win_rate_pct": quant.get("win_rate_pct", 0),
        "profit_factor": quant.get("profit_factor"),
        "recent_directional_bias": quant.get("recent_directional_bias"),
    }


def classify_strategy(db: Session, wallet_address: str) -> str:
    last = db.scalars(
        select(WhaleActivity)
        .where(WhaleActivity.wallet_address == wallet_address)
        .order_by(desc(WhaleActivity.timestamp))
        .limit(20)
    ).all()
    if not last:
        return "UNCLASSIFIED"
    leverage_count = sum(1 for a in last if a.activity_type == ActivityType.MARGIN_POSITION_OPEN)
    lp_count = sum(1 for a in last if a.activity_type == ActivityType.LIQUIDITY_PROVISION)
    if leverage_count > 8:
        return "MOMENTUM"
    if lp_count > 6:
        return "YIELD_FARMING"
    return "MEAN_REVERSION"


def generate_structured_summary(activity: WhaleActivity) -> dict:
    raw = activity.raw_log or {}
    block = raw.get("block_number", "unknown")
    msg_types = raw.get("tx_msg_types") or []
    intent = "portfolio rotation"
    if activity.activity_type == ActivityType.MARGIN_POSITION_OPEN:
        intent = "directional expansion into leveraged exposure"
    elif activity.activity_type == ActivityType.MARGIN_POSITION_CLOSE:
        intent = "risk reduction or profit-taking on derivative exposure"
    elif activity.activity_type == ActivityType.SWAP:
        intent = "spot or orderbook execution on Helix/Injective exchange modules"
    elif activity.activity_type == ActivityType.LARGE_TRANSFER:
        intent = "capital relocation between venues or counterparties"

    base = {
        "structural_narrative": (
            f"Wallet {activity.wallet_address[:12]}... executed {activity.activity_type.value} "
            f"on {activity.asset_symbol} ({activity.amount:,.4f} units, "
            f"${activity.notional_value_usd:,.2f} notional) in block {block}. "
            f"On-chain message types: {', '.join(msg_types[:3]) or 'n/a'}."
        ),
        "strategic_intent_hypothesis": f"Observed behavior suggests {intent}.",
        "execution_urgency_tier": "HIGH" if activity.notional_value_usd > 250000 else "MEDIUM",
        "confidence_metric": 0.82 if raw.get("source") == "injective_explorer_live" else 0.65,
    }
    return maybe_enhance_with_llm(activity, base)


def maybe_enhance_with_llm(activity: WhaleActivity, base: dict) -> dict:
    from .config import get_settings

    settings = get_settings()
    if not settings.openai_api_key:
        return base

    try:
        import httpx

        prompt = (
            "You are Podium Finance on-chain analyst. Return JSON only with keys: "
            "structural_narrative, strategic_intent_hypothesis, execution_urgency_tier, confidence_metric. "
            "Educational analytics only, never financial advice.\n"
            f"Activity: {activity.activity_type.value}, asset={activity.asset_symbol}, "
            f"usd={activity.notional_value_usd}, raw={activity.raw_log}"
        )
        with httpx.Client(timeout=20.0) as client:
            res = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": settings.openai_model,
                    "messages": [
                        {"role": "system", "content": "Respond with valid JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
            )
            res.raise_for_status()
            content = res.json()["choices"][0]["message"]["content"]
            import json

            parsed = json.loads(content.strip().strip("`").replace("json\n", ""))
            return {**base, **parsed}
    except Exception:
        return base


def build_execution_plan(
    event: WhaleActivity,
    metrics: dict,
    user_portfolio_usd: float,
    max_drawdown_tolerance_percent: float,
    leverage_cap: float,
    db: Session | None = None,
) -> dict:
    """Deterministic, event-specific risk-aware execution blueprint."""
    from .price_oracle import fetch_usd_price

    conviction = float(metrics.get("conviction_score", 0.0))
    conviction_factor = max(0.15, min(1.0, conviction / 100))
    win_rate = float(metrics.get("win_rate_proxy", 0.5))

    rf = 1.8
    dampener = 0.20
    kelly = max(0.05, min(0.35, ((win_rate * rf) - (1 - win_rate)) / rf * dampener))

    risk_budget_usd = user_portfolio_usd * (max_drawdown_tolerance_percent / 100)
    whale_notional = max(float(event.notional_value_usd), 1.0)

    # Scale copy size with conviction; larger whale trades allow slightly higher copy %.
    notional_tier = min(1.0, whale_notional / 50_000)
    copy_ratio = 0.01 + (0.08 * conviction_factor) + (0.03 * notional_tier)

    whale_scaled = whale_notional * copy_ratio
    kelly_scaled = user_portfolio_usd * kelly * conviction_factor
    hypothetical_allocation = min(whale_scaled, kelly_scaled, risk_budget_usd)
    hypothetical_allocation = round(max(50.0, hypothetical_allocation), 2)

    asset = event.asset_symbol or "INJ"
    spot_price = fetch_usd_price(asset) if asset != "UNKNOWN" else fetch_usd_price("INJ")
    if spot_price <= 0:
        spot_price = float((event.raw_log or {}).get("reference_price", 7.0))

    raw = event.raw_log or {}
    direction = str(raw.get("direction", "LONG")).upper()
    atr_14 = float(raw.get("atr_14", spot_price * 0.04))

    activity = event.activity_type
    watch_only = activity in (ActivityType.LARGE_TRANSFER, ActivityType.LIQUIDITY_PROVISION)

    if activity == ActivityType.MARGIN_POSITION_OPEN:
        action = "EXECUTE_SPOT_BUY" if leverage_cap <= 1.0 else "EXECUTE_MARGIN_BUY"
        execution_routing = "Helix Derivatives Orderbook"
        if direction == "SHORT":
            action = "EXECUTE_SPOT_SELL" if leverage_cap <= 1.0 else "EXECUTE_MARGIN_SELL"
    elif activity == ActivityType.MARGIN_POSITION_CLOSE:
        action = "REDUCE_EXPOSURE"
        execution_routing = "Helix Derivatives Orderbook"
    elif activity == ActivityType.SWAP:
        action = "EXECUTE_SPOT_BUY" if direction != "SHORT" else "EXECUTE_SPOT_SELL"
        execution_routing = "Helix Spot Orderbook"
    elif activity == ActivityType.LIQUIDITY_PROVISION:
        action = "LIQUIDITY_PROVISION_WATCH"
        execution_routing = "Monitor only — LP event, no direct trade blueprint"
    else:
        action = "OBSERVE_CAPITAL_ROTATION"
        execution_routing = "Monitor only — transfer event, no direct trade blueprint"

    recommended_allocation = 0.0 if watch_only else hypothetical_allocation

    quant_ctx: dict = {}
    if db is not None:
        quant_ctx = quant_context_for_event(db, event)
        event_fill = quant_ctx.get("event_fill") or {}
        if event_fill.get("fill_price_usd"):
            spot_price = float(event_fill["fill_price_usd"])
            atr_14 = spot_price * 0.04
        if event_fill.get("realized_pnl_usd") is not None:
            pnl = float(event_fill["realized_pnl_usd"])
            if pnl < 0 and not watch_only:
                hypothetical_allocation = round(hypothetical_allocation * 0.65, 2)
            elif pnl > 0 and not watch_only:
                hypothetical_allocation = round(min(hypothetical_allocation * 1.1, risk_budget_usd), 2)
            recommended_allocation = 0.0 if watch_only else hypothetical_allocation

    if direction == "SHORT":
        hard_stop_loss = round(spot_price + (1.5 * atr_14), 2)
        take_profit = round(spot_price - (2.0 * atr_14), 2)
    else:
        hard_stop_loss = round(spot_price - (1.5 * atr_14), 2)
        take_profit = round(spot_price + (2.0 * atr_14), 2)

    urgency = "HIGH" if whale_notional >= 100_000 else "MEDIUM" if whale_notional >= 10_000 else "LOW"

    if watch_only:
        sizing_rationale = (
            f"Whale moved ${whale_notional:,.2f} ({activity.value}). "
            f"This is a watch-only signal — no execution recommended. "
            f"Hypothetical risk-bounded follow size would be ${hypothetical_allocation:,.2f} "
            f"at conviction {conviction:.1f}/100."
        )
    else:
        sizing_rationale = (
            f"Allocation uses conviction ({conviction:.1f}/100), whale notional "
            f"(${whale_notional:,.2f}), and your {max_drawdown_tolerance_percent}% "
            f"drawdown budget (${risk_budget_usd:,.2f}). Copy ratio applied: {copy_ratio*100:.2f}%."
        )

    trade_conclusion = ""
    if db is not None and quant_ctx:
        trade_conclusion = generate_trade_conclusion(
            event,
            quant_ctx,
            action=action,
            execution_mode="WATCH" if watch_only else "EXECUTE",
            recommended_usd=recommended_allocation,
            conviction=conviction,
        )

    event_fill = quant_ctx.get("event_fill") or {}
    return {
        "execution_blueprint": {
            "action": action,
            "execution_mode": "WATCH" if watch_only else "EXECUTE",
            "target_asset": asset,
            "recommended_allocation_usd": recommended_allocation,
            "percentage_of_user_portfolio": round(
                (recommended_allocation / user_portfolio_usd) * 100, 2
            ),
            "hypothetical_allocation_usd": hypothetical_allocation if watch_only else None,
            "execution_routing": execution_routing,
            "safety_parameters": None if watch_only else {
                "hard_stop_loss_price": hard_stop_loss,
                "take_profit_target_one": take_profit,
                "max_allowable_slippage_percent": 0.5,
            },
            "quant_metrics": {
                "whale_fill_price_usd": event_fill.get("fill_price_usd"),
                "whale_entry_price_usd": event_fill.get("entry_price_usd"),
                "whale_exit_price_usd": event_fill.get("exit_price_usd"),
                "event_realized_pnl_usd": event_fill.get("realized_pnl_usd"),
                "execution_side": event_fill.get("side"),
                "wallet_realized_pnl_30d_usd": quant_ctx.get("wallet_quant", {}).get(
                    "total_realized_pnl_usd"
                ),
                "wallet_win_rate_30d_pct": quant_ctx.get("wallet_quant", {}).get("win_rate_pct"),
                "wallet_combined_pnl_30d_usd": quant_ctx.get("wallet_quant", {}).get(
                    "combined_pnl_usd"
                ),
                "asset_realized_pnl_usd": (quant_ctx.get("asset_stats") or {}).get(
                    "realized_pnl_usd"
                ),
            },
            "event_context": {
                "whale_event_id": event.event_id,
                "whale_wallet": event.wallet_address,
                "activity_type": event.activity_type.value,
                "whale_notional_usd": round(whale_notional, 2),
                "conviction_score": conviction,
                "dominant_strategy": metrics.get("dominant_strategy", "UNCLASSIFIED"),
                "urgency_tier": urgency,
            },
            "sizing_rationale": sizing_rationale,
            "trade_conclusion": trade_conclusion,
            "disclaimer": (
                "Educational strategy blueprint only. Not financial advice. "
                "Validate liquidity, fees, and execution constraints before acting."
            ),
        }
    }


def persist_summary(db: Session, wallet_address: str, summary_payload: dict) -> AISummary:
    now = datetime.now(timezone.utc)
    row = AISummary(
        wallet_address=wallet_address,
        window_start=now - timedelta(hours=6),
        window_end=now,
        narrative_text=summary_payload["structural_narrative"],
        confidence_rating=summary_payload["confidence_metric"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
