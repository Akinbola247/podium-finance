"""Whale wallet quantitative analysis: fills, P&L, win rate, trade conclusions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .market_registry import _human_price, resolve_market
from .models import ActivityType, WhaleActivity
from .price_oracle import amount_to_usd, fetch_usd_price


@dataclass
class FillRecord:
    event_id: str
    timestamp: datetime
    asset: str
    side: str
    fill_price_usd: float
    quantity: float
    notional_usd: float
    activity_type: str
    market_ticker: str | None = None
    realized_pnl_usd: float | None = None
    unrealized_pnl_usd: float | None = None
    entry_price_usd: float | None = None
    exit_price_usd: float | None = None


@dataclass
class AssetPositionBook:
    long_qty: float = 0.0
    long_cost: float = 0.0
    short_qty: float = 0.0
    short_cost: float = 0.0


def _parse_direction_side(activity_type: ActivityType, direction: str) -> str:
    d = (direction or "").upper()
    if activity_type == ActivityType.MARGIN_POSITION_OPEN:
        return "SHORT_OPEN" if "SELL" in d else "LONG_OPEN"
    if activity_type == ActivityType.MARGIN_POSITION_CLOSE:
        # SELL closes a long; BUY closes a short (Helix perp convention).
        if "SELL" in d:
            return "LONG_CLOSE"
        if "BUY" in d:
            return "SHORT_CLOSE"
        return "LONG_CLOSE"
    if activity_type == ActivityType.SWAP:
        return "SELL" if "SELL" in d else "BUY"
    if activity_type == ActivityType.LARGE_TRANSFER:
        return "TRANSFER_OUT" if "OUT" in d else "TRANSFER_IN"
    return "NEUTRAL"


def _sanity_cap_price(asset: str, price: float) -> float:
    oracle = fetch_usd_price(asset)
    if oracle <= 0:
        return price
    if price <= 0:
        return oracle
    if price > oracle * 25 or price < oracle / 25:
        return oracle
    return price


def _infer_fill_price(activity: WhaleActivity) -> tuple[float, float, str | None]:
    raw = activity.raw_log or {}
    ticker = raw.get("market_ticker")

    retro = _retrofill_price_from_messages(raw)
    if retro:
        price, qty = retro
        price = _sanity_cap_price(activity.asset_symbol, price)
        return _reconcile_price_qty(activity, price, qty, ticker)

    if raw.get("fill_price_usd"):
        qty = float(raw.get("fill_quantity") or activity.amount or 0)
        price = _sanity_cap_price(activity.asset_symbol, float(raw["fill_price_usd"]))
        return _reconcile_price_qty(activity, price, qty, ticker)

    qty = float(activity.amount or 0)
    if qty > 0 and activity.notional_value_usd > 0:
        price = _sanity_cap_price(
            activity.asset_symbol, round(activity.notional_value_usd / qty, 4)
        )
        return _reconcile_price_qty(activity, price, qty, ticker)

    return _reconcile_price_qty(
        activity,
        fetch_usd_price(activity.asset_symbol),
        max(qty, 0.0),
        ticker,
    )


def _reconcile_price_qty(
    activity: WhaleActivity,
    price: float,
    qty: float,
    ticker: str | None,
) -> tuple[float, float, str | None]:
    """Align price × qty with capped notional (fixes unscaled ticks / bad amounts)."""
    notional = float(activity.notional_value_usd or 0)
    amount = float(activity.amount or 0)
    if notional > 0 and amount > 0:
        amt_price = notional / amount
        if price <= 0 or (amt_price > 0 and (price / amt_price > 2 or price / amt_price < 0.5)):
            price = amt_price
            qty = amount
    if notional > 0 and price > 0:
        qty = notional / price
    price = _sanity_cap_price(activity.asset_symbol, price)
    return price, qty, ticker


def _iter_exchange_msg_values(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Yield exchange message bodies, including orders nested inside authz MsgExec."""
    values: list[dict[str, Any]] = []
    for msg in raw.get("messages", []) or []:
        msg_type = msg.get("type", "")
        value = msg.get("value") or {}
        if msg_type == "/cosmos.authz.v1beta1.MsgExec":
            for nested in value.get("msgs", []) or []:
                if not isinstance(nested, dict):
                    continue
                inner = nested.get("value")
                if not isinstance(inner, dict):
                    inner = nested
                values.append(inner)
            continue
        values.append(value)
    return values


def _batch_has_create_orders(raw: dict[str, Any]) -> bool:
    for value in _iter_exchange_msg_values(raw):
        if value.get("derivative_orders_to_create") or value.get("spot_orders_to_create"):
            return True
        if value.get("derivative_market_orders_to_create") or value.get("spot_market_orders_to_create"):
            return True
        order = value.get("order") or {}
        if order and value.get("market_id"):
            return True
    return False


def _batch_is_cancel_only(raw: dict[str, Any]) -> bool:
    """Cancel-all / cancel-list without new orders — not a position close for P&L."""
    has_cancel = False
    for value in _iter_exchange_msg_values(raw):
        if value.get("derivative_market_ids_to_cancel_all") or value.get("spot_market_ids_to_cancel_all"):
            has_cancel = True
        if value.get("derivative_orders_to_cancel") or value.get("spot_orders_to_cancel"):
            has_cancel = True
    return has_cancel and not _batch_has_create_orders(raw)


def _retrofill_price_from_messages(raw: dict[str, Any]) -> tuple[float, float] | None:
    """Best-effort price/qty from stored explorer messages."""
    for value in _iter_exchange_msg_values(raw):
        for key in (
            "derivative_orders_to_create",
            "spot_orders_to_create",
            "derivative_market_orders_to_create",
        ):
            for order in value.get(key, []) or []:
                market = resolve_market(str(order.get("market_id", "")))
                if not market:
                    continue
                order_info = order.get("order_info") or {}
                price_raw = float(order_info.get("price") or 0)
                qty = float(order_info.get("quantity") or 0)
                if price_raw <= 0 or qty <= 0:
                    continue
                price = _human_price(price_raw, market, market.get("ticker", ""))
                return price, qty
        order = value.get("order") or {}
        if order:
            market = resolve_market(str(order.get("market_id", "")))
            if market:
                order_info = order.get("order_info") or {}
                price_raw = float(order_info.get("price") or 0)
                qty = float(order_info.get("quantity") or 0)
                if price_raw > 0 and qty > 0:
                    price = _human_price(price_raw, market, market.get("ticker", ""))
                    return price, qty
    return None


def enrich_fills_with_pnl(
    db: Session,
    activities: list[WhaleActivity],
    *,
    history_limit: int = 400,
) -> dict[str, FillRecord]:
    """
    Run FIFO books per wallet so each activity gets realized/unrealized P&L.
    Must process prior history before the rows shown in the feed.
    """
    if not activities:
        return {}

    target_ids = {a.event_id for a in activities}
    by_wallet: dict[str, list[WhaleActivity]] = defaultdict(list)
    for act in activities:
        by_wallet[act.wallet_address].append(act)

    enriched: dict[str, FillRecord] = {}

    for wallet, batch in by_wallet.items():
        oldest_ts = min(a.timestamp for a in batch)
        prior = db.scalars(
            select(WhaleActivity)
            .where(
                WhaleActivity.wallet_address == wallet,
                WhaleActivity.timestamp < oldest_ts,
            )
            .order_by(WhaleActivity.timestamp.asc())
            .limit(history_limit)
        ).all()

        chain = list(prior) + sorted(batch, key=lambda a: a.timestamp)
        books: dict[str, AssetPositionBook] = defaultdict(AssetPositionBook)
        closed_trades: list[dict[str, Any]] = []

        for act in chain:
            fill = fill_from_activity(act)
            if not fill:
                continue
            book = books[fill.asset]
            fill = _apply_fill_to_book(book, fill, closed_trades)

            if act.event_id not in target_ids:
                continue

            if fill.realized_pnl_usd is None and fill.side in (
                "LONG_OPEN",
                "BUY",
                "SHORT_OPEN",
            ):
                # Feed column: mark-to-market on this clip (not cumulative book — avoids legacy mis-tags).
                mark = fetch_usd_price(fill.asset)
                if mark <= 0:
                    mark = fill.fill_price_usd
                clip_qty = fill.quantity if fill.quantity > 0 else (
                    fill.notional_usd / fill.fill_price_usd if fill.fill_price_usd > 0 else 0
                )
                fill.entry_price_usd = fill.fill_price_usd
                if fill.side in ("LONG_OPEN", "BUY"):
                    unrealized = (mark - fill.fill_price_usd) * clip_qty
                else:
                    unrealized = (fill.fill_price_usd - mark) * clip_qty
                cap = fill.notional_usd * 0.35 if fill.notional_usd > 0 else 25_000.0
                fill.unrealized_pnl_usd = round(max(-cap, min(cap, unrealized)), 2)

            enriched[act.event_id] = fill

    return enriched


def _effective_activity_type(activity: WhaleActivity) -> ActivityType:
    """Fix legacy rows: batch cancel_all + create_orders stored as CLOSE."""
    raw = activity.raw_log or {}
    if _batch_has_create_orders(raw):
        return ActivityType.MARGIN_POSITION_OPEN
    if activity.activity_type == ActivityType.MARGIN_POSITION_CLOSE and _batch_is_cancel_only(raw):
        return ActivityType.SWAP  # neutral for FIFO — order cancel, not a fill
    if activity.activity_type != ActivityType.MARGIN_POSITION_CLOSE:
        return activity.activity_type
    return activity.activity_type


def _sanity_cap_quantity(asset: str, qty: float, notional: float, price: float) -> float:
    if qty <= 0:
        return qty
    if notional > 0 and price > 0:
        implied = notional / price
        if implied > 0 and qty > implied * 50:
            return implied
    oracle = fetch_usd_price(asset)
    if oracle > 0 and price > 0:
        max_qty = max(notional / price if notional > 0 else 0, (notional or 1) / oracle) * 10
        if max_qty > 0 and qty > max_qty * 1000:
            return max_qty
    if qty > 1e9:
        return notional / price if price > 0 and notional > 0 else 0.0
    return qty


def fill_from_activity(activity: WhaleActivity) -> FillRecord | None:
    raw = activity.raw_log or {}
    if _batch_is_cancel_only(raw):
        return None
    effective_type = _effective_activity_type(activity)
    direction = str(raw.get("direction", ""))
    # Always derive side from effective type (raw_log execution_side may be stale).
    side = _parse_direction_side(effective_type, direction)

    fill_price, qty, ticker = _infer_fill_price(activity)
    if fill_price <= 0:
        retro = _retrofill_price_from_messages(raw)
        if retro:
            fill_price, qty = retro
    if fill_price <= 0:
        fill_price = fetch_usd_price(activity.asset_symbol)
    if qty <= 0 and activity.notional_value_usd > 0 and fill_price > 0:
        qty = activity.notional_value_usd / fill_price
    qty = _sanity_cap_quantity(
        activity.asset_symbol, qty, activity.notional_value_usd, fill_price
    )

    return FillRecord(
        event_id=activity.event_id,
        timestamp=activity.timestamp,
        asset=activity.asset_symbol,
        side=side,
        fill_price_usd=round(fill_price, 4),
        quantity=round(qty, 8),
        notional_usd=round(activity.notional_value_usd, 2),
        activity_type=effective_type.value,
        market_ticker=ticker or raw.get("market_ticker"),
    )


def _apply_fill_to_book(
    book: AssetPositionBook,
    fill: FillRecord,
    closed_trades: list[dict[str, Any]],
) -> FillRecord:
    side = fill.side
    price = fill.fill_price_usd
    qty = fill.quantity if fill.quantity > 0 else (fill.notional_usd / price if price > 0 else 0)
    if qty <= 0:
        return fill

    if side in ("LONG_OPEN", "BUY", "TRANSFER_IN"):
        book.long_cost += price * qty
        book.long_qty += qty
        fill.entry_price_usd = price
        return fill

    if side in ("SHORT_OPEN",):
        book.short_cost += price * qty
        book.short_qty += qty
        fill.entry_price_usd = price
        return fill

    if side in ("LONG_CLOSE", "SELL", "TRANSFER_OUT"):
        match_qty = min(qty, book.long_qty)
        if match_qty > 0 and book.long_qty > 0:
            avg_entry = book.long_cost / book.long_qty
            pnl = (price - avg_entry) * match_qty
            pnl = max(-fill.notional_usd * 3, min(fill.notional_usd * 3, pnl))
            fill.realized_pnl_usd = round(pnl, 2)
            fill.entry_price_usd = round(avg_entry, 4)
            fill.exit_price_usd = price
            closed_trades.append(
                {
                    "asset": fill.asset,
                    "side": "LONG",
                    "entry_price_usd": round(avg_entry, 4),
                    "exit_price_usd": price,
                    "quantity": round(match_qty, 8),
                    "realized_pnl_usd": fill.realized_pnl_usd,
                    "closed_at": fill.timestamp.isoformat(),
                }
            )
            book.long_cost -= avg_entry * match_qty
            book.long_qty -= match_qty
        return fill

    if side in ("SHORT_CLOSE",):
        match_qty = min(qty, book.short_qty)
        if match_qty > 0 and book.short_qty > 0:
            avg_entry = book.short_cost / book.short_qty
            pnl = (avg_entry - price) * match_qty
            pnl = max(-fill.notional_usd * 3, min(fill.notional_usd * 3, pnl))
            fill.realized_pnl_usd = round(pnl, 2)
            fill.entry_price_usd = round(avg_entry, 4)
            fill.exit_price_usd = price
            closed_trades.append(
                {
                    "asset": fill.asset,
                    "side": "SHORT",
                    "entry_price_usd": round(avg_entry, 4),
                    "exit_price_usd": price,
                    "quantity": round(match_qty, 8),
                    "realized_pnl_usd": fill.realized_pnl_usd,
                    "closed_at": fill.timestamp.isoformat(),
                }
            )
            book.short_cost -= avg_entry * match_qty
            book.short_qty -= match_qty
        return fill

    return fill


def analyze_wallet_quant(
    db: Session,
    wallet_address: str,
    *,
    days: int = 30,
    limit: int = 500,
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    activities = db.scalars(
        select(WhaleActivity)
        .where(
            WhaleActivity.wallet_address == wallet_address,
            WhaleActivity.timestamp >= cutoff,
        )
        .order_by(WhaleActivity.timestamp.asc())
        .limit(limit)
    ).all()

    books: dict[str, AssetPositionBook] = defaultdict(AssetPositionBook)
    fills: list[FillRecord] = []
    closed_trades: list[dict[str, Any]] = []
    realized_pnls: list[float] = []

    for act in activities:
        fill = fill_from_activity(act)
        if not fill:
            continue
        book = books[fill.asset]
        fill = _apply_fill_to_book(book, fill, closed_trades)
        fills.append(fill)
        if fill.realized_pnl_usd is not None:
            realized_pnls.append(fill.realized_pnl_usd)

    total_realized = round(sum(realized_pnls), 2)
    wins = sum(1 for p in realized_pnls if p > 0)
    losses = sum(1 for p in realized_pnls if p < 0)
    closed_count = len(realized_pnls)
    win_rate_pct = round((wins / closed_count) * 100, 1) if closed_count else 0.0
    avg_win = round(sum(p for p in realized_pnls if p > 0) / wins, 2) if wins else 0.0
    avg_loss = round(sum(p for p in realized_pnls if p < 0) / losses, 2) if losses else 0.0

    by_asset: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "realized_pnl_usd": 0.0,
            "closed_trades": 0,
            "wins": 0,
            "buys": 0,
            "sells": 0,
            "last_fill_price_usd": None,
            "open_long_qty": 0.0,
            "avg_entry_long_usd": None,
        }
    )

    for fill in fills:
        row = by_asset[fill.asset]
        row["last_fill_price_usd"] = fill.fill_price_usd
        if fill.side in ("LONG_OPEN", "BUY"):
            row["buys"] += 1
        if fill.side in ("SELL", "LONG_CLOSE", "SHORT_OPEN"):
            row["sells"] += 1
        if fill.realized_pnl_usd is not None:
            row["realized_pnl_usd"] += fill.realized_pnl_usd
            row["closed_trades"] += 1
            if fill.realized_pnl_usd > 0:
                row["wins"] += 1

    for asset, book in books.items():
        if book.long_qty > 0:
            by_asset[asset]["open_long_qty"] = round(book.long_qty, 8)
            by_asset[asset]["avg_entry_long_usd"] = round(book.long_cost / book.long_qty, 4)

    unrealized_total = 0.0
    for asset, book in books.items():
        if book.long_qty > 0:
            mark = fetch_usd_price(asset)
            avg = book.long_cost / book.long_qty
            unrealized_total += (mark - avg) * book.long_qty
        if book.short_qty > 0:
            mark = fetch_usd_price(asset)
            avg = book.short_cost / book.short_qty
            unrealized_total += (avg - mark) * book.short_qty

    asset_rows = []
    for asset, stats in sorted(by_asset.items(), key=lambda x: abs(x[1]["realized_pnl_usd"]), reverse=True):
        wr = (
            round((stats["wins"] / stats["closed_trades"]) * 100, 1)
            if stats["closed_trades"]
            else None
        )
        asset_rows.append(
            {
                "asset": asset,
                "realized_pnl_usd": round(stats["realized_pnl_usd"], 2),
                "closed_trades": stats["closed_trades"],
                "win_rate_pct": wr,
                "buy_fills": stats["buys"],
                "sell_fills": stats["sells"],
                "last_fill_price_usd": stats["last_fill_price_usd"],
                "open_long_qty": stats["open_long_qty"],
                "avg_entry_long_usd": stats["avg_entry_long_usd"],
            }
        )

    recent_fills = [
        {
            "event_id": f.event_id,
            "timestamp": f.timestamp.isoformat(),
            "asset": f.asset,
            "side": f.side,
            "fill_price_usd": f.fill_price_usd,
            "quantity": f.quantity,
            "notional_usd": f.notional_usd,
            "realized_pnl_usd": f.realized_pnl_usd,
            "entry_price_usd": f.entry_price_usd,
            "exit_price_usd": f.exit_price_usd,
            "market_ticker": f.market_ticker,
        }
        for f in fills[-25:]
    ]

    bias = "NEUTRAL"
    recent_buys = sum(1 for f in fills[-15:] if f.side in ("LONG_OPEN", "BUY"))
    recent_sells = sum(1 for f in fills[-15:] if f.side in ("SELL", "LONG_CLOSE", "SHORT_OPEN"))
    if recent_buys > recent_sells * 1.5:
        bias = "ACCUMULATING"
    elif recent_sells > recent_buys * 1.5:
        bias = "DISTRIBUTING"

    return {
        "wallet_address": wallet_address,
        "window_days": days,
        "fills_analyzed": len(fills),
        "total_realized_pnl_usd": total_realized,
        "unrealized_pnl_usd": round(unrealized_total, 2),
        "combined_pnl_usd": round(total_realized + unrealized_total, 2),
        "closed_trades_count": closed_count,
        "win_rate_pct": win_rate_pct,
        "avg_win_usd": avg_win,
        "avg_loss_usd": avg_loss,
        "profit_factor": round(abs(avg_win / avg_loss), 2) if avg_loss else None,
        "recent_directional_bias": bias,
        "by_asset": asset_rows[:12],
        "recent_fills": recent_fills,
        "closed_trade_log": closed_trades[-20:],
    }


def quant_context_for_event(db: Session, event: WhaleActivity) -> dict[str, Any]:
    wallet_quant = analyze_wallet_quant(db, event.wallet_address, days=30)
    fill = fill_from_activity(event)
    asset_stats = next(
        (a for a in wallet_quant["by_asset"] if a["asset"] == event.asset_symbol),
        None,
    )

    return {
        "event_fill": {
            "side": fill.side if fill else None,
            "fill_price_usd": fill.fill_price_usd if fill else None,
            "quantity": fill.quantity if fill else None,
            "entry_price_usd": fill.entry_price_usd if fill else None,
            "exit_price_usd": fill.exit_price_usd if fill else None,
            "realized_pnl_usd": fill.realized_pnl_usd if fill else None,
            "market_ticker": fill.market_ticker if fill else None,
        },
        "wallet_quant": wallet_quant,
        "asset_stats": asset_stats,
    }


def generate_trade_conclusion(
    event: WhaleActivity,
    quant_ctx: dict[str, Any],
    *,
    action: str,
    execution_mode: str,
    recommended_usd: float,
    conviction: float,
) -> str:
    fill = quant_ctx.get("event_fill") or {}
    wq = quant_ctx.get("wallet_quant") or {}
    asset = quant_ctx.get("asset_stats") or {}

    side = fill.get("side") or "ACTIVITY"
    price = fill.get("fill_price_usd")
    entry = fill.get("entry_price_usd")
    exit_p = fill.get("exit_price_usd")
    event_pnl = fill.get("realized_pnl_usd")
    ticker = fill.get("market_ticker") or event.asset_symbol

    lines: list[str] = []

    if price:
        if side in ("LONG_OPEN", "BUY"):
            lines.append(
                f"The whale **opened / added long exposure** in **{event.asset_symbol}** "
                f"({ticker}) at an estimated fill near **${price:,.2f}** "
                f"(${event.notional_value_usd:,.0f} notional)."
            )
        elif side in ("SELL", "LONG_CLOSE"):
            if entry and exit_p:
                lines.append(
                    f"The whale **reduced long / sold** **{event.asset_symbol}** — "
                    f"entry ~**${entry:,.2f}**, exit ~**${exit_p:,.2f}**."
                )
            else:
                lines.append(
                    f"The whale **sold / closed long** **{event.asset_symbol}** "
                    f"near **${price:,.2f}** (${event.notional_value_usd:,.0f} notional)."
                )
        elif side == "SHORT_OPEN":
            lines.append(
                f"The whale **opened short** **{event.asset_symbol}** near **${price:,.2f}**."
            )
        else:
            lines.append(
                f"On-chain activity: **{event.activity_type.value}** on **{event.asset_symbol}** "
                f"at ~**${price:,.2f}**."
            )
    else:
        lines.append(
            f"Observed **{event.activity_type.value}** on **{event.asset_symbol}** "
            f"(${event.notional_value_usd:,.0f} notional)."
        )

    if event_pnl is not None:
        sign = "profit" if event_pnl >= 0 else "loss"
        lines.append(f"This fill crystallized an estimated **${abs(event_pnl):,.2f} {sign}** on the matched lot.")

    wr = wq.get("win_rate_pct")
    realized = wq.get("total_realized_pnl_usd")
    bias = wq.get("recent_directional_bias", "NEUTRAL")
    if wr is not None and wq.get("closed_trades_count", 0) > 0:
        lines.append(
            f"Over the last {wq.get('window_days', 30)} days this wallet closed **{wq['closed_trades_count']}** "
            f"matched lots with **{wr}%** win rate and **${realized:,.2f}** realized P&L "
            f"(recent bias: **{bias}**)."
        )
    elif bias != "NEUTRAL":
        lines.append(f"Recent flow bias: **{bias}** (buy vs sell count in last 15 exchange fills).")

    if asset and asset.get("closed_trades", 0) > 0:
        lines.append(
            f"On **{event.asset_symbol}** specifically: **${asset['realized_pnl_usd']:,.2f}** realized across "
            f"**{asset['closed_trades']}** closes"
            + (f", **{asset['win_rate_pct']}%** win rate." if asset.get("win_rate_pct") is not None else ".")
        )
    if asset and asset.get("avg_entry_long_usd") and asset.get("open_long_qty"):
        mark = fetch_usd_price(event.asset_symbol)
        lines.append(
            f"Estimated open long: **{asset['open_long_qty']:.4f}** {event.asset_symbol} "
            f"@ avg **${asset['avg_entry_long_usd']:,.2f}** (mark ~${mark:,.2f})."
        )

    if execution_mode == "WATCH":
        lines.append(
            "**Conclusion:** Treat as a *capital-flow / liquidity signal* — monitor only; "
            "no mirrored execution size recommended."
        )
    elif recommended_usd <= 0:
        lines.append(
            "**Conclusion:** Quant profile does not support aggressive copy-trade sizing on this event; "
            "stay flat or paper-trade only."
        )
    else:
        edge = "favorable" if (wr or 0) >= 55 and (realized or 0) >= 0 else "mixed"
        if event_pnl is not None and event_pnl < 0:
            edge = "cautionary"
        lines.append(
            f"**Conclusion:** Whale track record looks **{edge}** (conviction **{conviction:.0f}/100**). "
            f"A risk-bounded educational mirror would be **{action}** ~**${recommended_usd:,.2f}** "
            f"— scale down if your drawdown budget is tighter than the whale's typical clip."
        )

    lines.append(
        "_Educational analytics only — not financial advice. P&L is estimated from public fills, not exchange statements._"
    )
    return "\n\n".join(lines)
