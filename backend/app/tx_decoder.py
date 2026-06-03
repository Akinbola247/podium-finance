from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from .market_registry import _human_price, notional_from_order, resolve_market
from .models import ActivityType
from .price_oracle import amount_to_usd, denom_to_symbol, parse_chain_amount

EXCHANGE_MSG_PREFIX = "/injective.exchange"
DERIVATIVE_MSG_HINTS = ("Derivative", "derivative")
SPOT_MSG_HINTS = ("Spot", "spot")
ORDER_MSG_HINTS = ("Order", "BatchUpdate")
DERIVATIVE_CLOSE_HINTS = ("CancelDerivative", "derivative_orders_to_cancel", "derivative_market_ids_to_cancel")
DERIVATIVE_OPEN_HINTS = ("CreateDerivative", "derivative_orders_to_create", "derivative_market_orders_to_create")
SPOT_OPEN_HINTS = ("CreateSpot", "spot_orders_to_create", "spot_market_orders_to_create")
LP_HINTS = ("MsgDeposit", "MsgWithdraw", "MsgIncreaseLiquidity", "MsgDecreaseLiquidity")
BATCH_ORDER_KEYS = (
    "derivative_orders_to_create",
    "spot_orders_to_create",
    "derivative_market_orders_to_create",
    "spot_market_orders_to_create",
)


def _parse_timestamp(raw: str) -> datetime:
    cleaned = raw.replace(" +0000 UTC", "").replace(" UTC", "")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def addresses_in_tx(tx: dict[str, Any]) -> set[str]:
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key.endswith("address") and isinstance(value, str) and value.startswith("inj1"):
                    found.add(value)
                elif key in ("sender", "grantee") and isinstance(value, str) and value.startswith("inj1"):
                    found.add(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(tx.get("messages", []))
    walk(tx.get("logs", []))
    return found


def _extract_amount_string(raw: str) -> tuple[str, str] | None:
    m = re.match(r"^([0-9]+)([A-Za-z0-9/_-]+)$", raw.strip())
    if not m:
        return None
    return m.group(1), m.group(2)


def _amount_from_logs(tx: dict[str, Any]) -> tuple[str, float, float, str | None]:
    """Returns symbol, qty, usd, market_id."""
    for log in tx.get("logs", []) or []:
        for event in log.get("events", []) or []:
            if event.get("type") not in ("coin_spent", "coin_received", "transfer"):
                continue
            for attr in event.get("attributes", []) or []:
                if attr.get("key") != "amount":
                    continue
                parsed = _extract_amount_string(str(attr.get("value", "")))
                if not parsed:
                    continue
                amount_raw, denom = parsed
                symbol = denom_to_symbol(denom)
                qty = parse_chain_amount(amount_raw, denom)
                usd = amount_to_usd(qty, symbol)
                if qty > 0:
                    return symbol, qty, usd, None
    return "", 0.0, 0.0, None


def _flatten_messages(tx: dict[str, Any]) -> list[dict[str, Any]]:
    """Include nested exchange messages from authz MsgExec."""
    flat: list[dict[str, Any]] = []
    for msg in tx.get("messages", []) or []:
        msg_type = msg.get("type", "")
        value = msg.get("value", {}) or {}
        flat.append(msg)
        if msg_type == "/cosmos.authz.v1beta1.MsgExec":
            for nested in value.get("msgs", []) or []:
                nested_type = nested.get("@type") or nested.get("type", "")
                if nested_type:
                    flat.append({"type": nested_type, "value": nested})
    return flat


def _classify_order(order: dict[str, Any], msg_type: str) -> ActivityType:
    """Classify a single order — do not use parent batch cancel_all flags."""
    ot = str(order.get("order_type", "")).upper()
    if "CancelDerivative" in msg_type or "CancelSpot" in msg_type:
        return ActivityType.MARGIN_POSITION_CLOSE
    if "CreateDerivative" in msg_type:
        return ActivityType.MARGIN_POSITION_OPEN
    if "CreateSpot" in msg_type:
        return ActivityType.SWAP
    if "BatchUpdate" in msg_type:
        if ot in ("BUY", "SELL", "BUY_PO", "SELL_PO"):
            return ActivityType.MARGIN_POSITION_OPEN
        return ActivityType.MARGIN_POSITION_OPEN
    if any(x in msg_type for x in DERIVATIVE_MSG_HINTS):
        return ActivityType.MARGIN_POSITION_OPEN
    if any(x in msg_type for x in SPOT_MSG_HINTS):
        return ActivityType.SWAP
    return ActivityType.SWAP


def _classify_from_msg_type(msg_type: str, value: dict[str, Any]) -> ActivityType:
    if value.get("derivative_orders_to_create") or value.get("spot_orders_to_create"):
        return ActivityType.MARGIN_POSITION_OPEN
    if value.get("derivative_orders_to_cancel") or value.get("spot_orders_to_cancel"):
        return ActivityType.MARGIN_POSITION_CLOSE
    blob = f"{msg_type} {value}".lower()
    if any(h.lower() in blob for h in DERIVATIVE_CLOSE_HINTS) and not value.get(
        "derivative_orders_to_create"
    ):
        return ActivityType.MARGIN_POSITION_CLOSE
    if any(x in msg_type for x in DERIVATIVE_MSG_HINTS) and "cancel" not in msg_type.lower():
        if "create" in msg_type.lower() or "order" in msg_type.lower():
            return ActivityType.MARGIN_POSITION_OPEN
    if any(x in msg_type for x in SPOT_MSG_HINTS) and "cancel" not in msg_type.lower():
        if "create" in msg_type.lower() or "order" in msg_type.lower():
            return ActivityType.SWAP
    if any(h.lower() in blob for h in LP_HINTS):
        return ActivityType.LIQUIDITY_PROVISION
    if EXCHANGE_MSG_PREFIX in msg_type:
        return ActivityType.SWAP
    return ActivityType.LARGE_TRANSFER


def _decode_single_order(
    order: dict[str, Any],
    msg_type: str,
    value: dict[str, Any],
) -> dict[str, Any] | None:
    market_id = order.get("market_id") or value.get("market_id")
    market = resolve_market(str(market_id or ""))
    if not market:
        return None

    base = market["base_asset"]
    ticker = market["ticker"]
    order_info = order.get("order_info") or {}
    price = str(order_info.get("price", "0"))
    quantity = str(order_info.get("quantity", "0"))
    margin = str(order.get("margin") or value.get("margin") or "0")
    notional = notional_from_order(
        price, quantity, base, ticker=ticker, margin=margin, market=market
    )
    direction = str(order.get("order_type") or value.get("order_type") or "LONG")
    activity_type = _classify_order(order, msg_type)
    qty_f = float(quantity) if quantity else 0.0
    fill_price = _human_price(float(price), market, ticker) if price else 0.0
    if fill_price <= 0 and qty_f > 0 and notional > 0:
        fill_price = notional / qty_f
    from .quant_analysis import _parse_direction_side

    execution_side = _parse_direction_side(activity_type, direction)
    return {
        "asset_symbol": base,
        "amount": qty_f,
        "notional_value_usd": notional,
        "activity_type": activity_type,
        "direction": direction,
        "market_ticker": ticker,
        "market_id": market_id,
        "fill_price_usd": round(fill_price, 4) if fill_price > 0 else None,
        "fill_quantity": qty_f,
        "execution_side": execution_side,
    }


def _decode_exchange_message(msg_type: str, value: dict[str, Any]) -> dict[str, Any] | None:
    """Extract asset + notional from Helix spot/derivative order messages."""
    candidates: list[dict[str, Any]] = []

    order = value.get("order") or {}
    if order:
        decoded = _decode_single_order(order, msg_type, value)
        if decoded:
            candidates.append(decoded)

    for key in BATCH_ORDER_KEYS:
        for batch_order in value.get(key, []) or []:
            decoded = _decode_single_order(batch_order, msg_type, value)
            if decoded:
                candidates.append(decoded)

    if not candidates and value.get("market_id"):
        decoded = _decode_single_order(value, msg_type, value)
        if decoded:
            candidates.append(decoded)

    if not candidates:
        return None
    return max(candidates, key=lambda c: c.get("notional_value_usd", 0))


def _decode_bank_send(value: dict[str, Any]) -> dict[str, Any] | None:
    amounts = value.get("amount", [])
    if not isinstance(amounts, list) or not amounts:
        return None
    entry = amounts[0]
    denom = entry.get("denom", "inj")
    symbol = denom_to_symbol(denom)
    qty = parse_chain_amount(str(entry.get("amount", "0")), denom)
    usd = amount_to_usd(qty, symbol)
    if qty <= 0:
        return None
    fill_price = usd / qty if qty > 0 else 0.0
    return {
        "asset_symbol": symbol,
        "amount": qty,
        "notional_value_usd": usd,
        "activity_type": ActivityType.LARGE_TRANSFER,
        "direction": "TRANSFER",
        "fill_price_usd": round(fill_price, 4) if fill_price > 0 else None,
        "fill_quantity": qty,
        "execution_side": "TRANSFER_IN",
    }


def _best_signal_from_tx(tx: dict[str, Any]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []

    for msg in _flatten_messages(tx):
        msg_type = msg.get("type", "")
        value = msg.get("value", {}) or {}

        if "MsgSend" in msg_type:
            decoded = _decode_bank_send(value)
            if decoded:
                candidates.append(decoded)

        if EXCHANGE_MSG_PREFIX in msg_type or "exchange" in msg_type.lower():
            decoded = _decode_exchange_message(msg_type, value)
            if decoded:
                candidates.append(decoded)

    symbol, qty, usd, _ = _amount_from_logs(tx)
    if qty > 0 and symbol:
        candidates.append(
            {
                "asset_symbol": symbol,
                "amount": qty,
                "notional_value_usd": usd,
                "activity_type": ActivityType.LARGE_TRANSFER,
                "direction": "TRANSFER",
            }
        )

    if not candidates:
        return None

    return max(candidates, key=lambda c: c.get("notional_value_usd", 0))


def decode_tx_for_wallet(tx: dict[str, Any], wallet_address: str) -> dict[str, Any] | None:
    if tx.get("code", 0) not in (0, "0", None):
        return None

    if wallet_address not in addresses_in_tx(tx):
        return None

    messages = tx.get("messages") or []
    if not messages:
        return None

    signal = _best_signal_from_tx(tx)
    if not signal:
        return None

    asset_symbol = signal.get("asset_symbol") or "UNKNOWN"
    if asset_symbol == "UNKNOWN":
        return None

    return {
        "wallet_address": wallet_address,
        "timestamp": _parse_timestamp(tx.get("block_timestamp", "")),
        "activity_type": signal["activity_type"],
        "asset_symbol": asset_symbol,
        "amount": signal.get("amount", 0.0),
        "notional_value_usd": round(float(signal.get("notional_value_usd", 0)), 2),
        "tx_hash": tx.get("hash", ""),
        "raw_log": {
            "block_number": tx.get("block_number"),
            "messages": messages,
            "tx_msg_types": tx.get("tx_msg_types", []),
            "gas_used": tx.get("gas_used"),
            "reference_price": amount_to_usd(1, asset_symbol),
            "direction": signal.get("direction"),
            "execution_side": signal.get("execution_side"),
            "fill_price_usd": signal.get("fill_price_usd"),
            "fill_quantity": signal.get("fill_quantity"),
            "market_ticker": signal.get("market_ticker"),
            "market_id": signal.get("market_id"),
            "source": "injective_explorer_live",
        },
    }
