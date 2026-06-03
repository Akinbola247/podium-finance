"""Resolve Injective market IDs and denoms to human tickers / base assets."""

from __future__ import annotations

import httpx

from .price_oracle import amount_to_usd, denom_to_symbol, fetch_usd_price

_LCD = "https://lcd.injective.network"
_cache: dict[str, dict] | None = None
# Legacy flat cap left many real whale clips at exactly this value — kept for backfill detection only.
LEGACY_FLAT_CAP_USD = 250_000.0
MAX_SANE_NOTIONAL_USD = LEGACY_FLAT_CAP_USD  # backwards-compat import name
ORACLE_PRICE_BAND = 25
MAX_ABSOLUTE_NOTIONAL_USD = 10_000_000.0


def validate_notional_usd(
    notional: float,
    base_asset: str,
    *,
    fill_price: float = 0,
    qty: float = 0,
) -> tuple[float, bool]:
    """
    Keep plausible Helix fills at true size; only shrink when implied price is far from oracle.
    Returns (usd_notional, was_adjusted).
    """
    if notional <= 0:
        return 0.0, False

    oracle = fetch_usd_price(base_asset)
    implied = fill_price
    if implied <= 0 and qty > 0:
        implied = notional / qty

    adjusted = False
    if oracle > 0 and implied > 0:
        if implied > oracle * ORACLE_PRICE_BAND or implied < oracle / ORACLE_PRICE_BAND:
            if qty > 0:
                notional = round(oracle * qty, 2)
            else:
                notional = round(min(notional, oracle * 50_000), 2)
            adjusted = True

    if notional > MAX_ABSOLUTE_NOTIONAL_USD:
        return MAX_ABSOLUTE_NOTIONAL_USD, True
    return round(notional, 2), adjusted


def cap_notional_usd(
    notional: float,
    base_asset: str = "INJ",
    *,
    fill_price: float = 0,
    qty: float = 0,
) -> float:
    """Validate notional against oracle — do not flatten real whale size to a fixed ceiling."""
    return validate_notional_usd(
        notional, base_asset, fill_price=fill_price, qty=qty
    )[0]


def _ticker_to_base(ticker: str) -> str:
    # Examples: "ETH/USDT PERP", "ATOM/USDT", "nINJ/INJ"
    base = ticker.split("/")[0].strip()
    return base.replace(" PERP", "").upper()[:16]


def load_market_registry(force: bool = False) -> dict[str, dict]:
    global _cache
    if _cache is not None and not force:
        return _cache

    registry: dict[str, dict] = {}
    with httpx.Client(timeout=45.0) as client:
        spot = client.get(f"{_LCD}/injective/exchange/v1beta1/spot/markets").json()
        for row in spot.get("markets", []):
            market_id = row.get("market_id")
            ticker = row.get("ticker", "")
            if not market_id or not ticker:
                continue
            registry[market_id.lower()] = {
                "ticker": ticker,
                "base_asset": _ticker_to_base(ticker),
                "market_type": "spot",
                "min_price_tick_size": float(row.get("min_price_tick_size") or 1),
                "min_quantity_tick_size": float(row.get("min_quantity_tick_size") or 1),
            }

        deriv = client.get(f"{_LCD}/injective/exchange/v1beta1/derivative/markets").json()
        for row in deriv.get("markets", []):
            market = row.get("market") or {}
            market_id = market.get("market_id")
            ticker = market.get("ticker", "")
            if not market_id or not ticker:
                continue
            registry[market_id.lower()] = {
                "ticker": ticker,
                "base_asset": _ticker_to_base(ticker),
                "market_type": "derivative",
                "min_price_tick_size": float(market.get("min_price_tick_size") or 1e6),
                "min_quantity_tick_size": float(market.get("min_quantity_tick_size") or 1),
            }

    _cache = registry
    return registry


def resolve_market(market_id: str) -> dict | None:
    if not market_id:
        return None
    return load_market_registry().get(market_id.lower())


def _human_price(raw_price: float, market: dict | None, ticker: str) -> float:
    quote = ticker.upper()
    if raw_price <= 0:
        return 0.0
    if raw_price < 1_000_000:
        return raw_price

    tick = float((market or {}).get("min_price_tick_size") or 0)
    if tick >= 1:
        return raw_price / tick
    if "USDC" in quote or "USDT" in quote or "PERP" in quote:
        return raw_price / 1e6
    return raw_price


def notional_from_order(
    price: str,
    quantity: str,
    base_asset: str,
    *,
    ticker: str = "",
    margin: str = "0",
    market: dict | None = None,
) -> float:
    try:
        p = float(price)
        q = float(quantity)
        m = float(margin or 0)
    except (TypeError, ValueError):
        return 0.0

    quote = ticker.upper()
    p_human = _human_price(p, market, ticker)

    if ("USDC" in quote or "USDT" in quote or "PERP" in quote) and p_human > 0 and q > 0:
        raw = round(p_human * q, 2)
        return validate_notional_usd(raw, base_asset, fill_price=p_human, qty=q)[0]

    if m >= 100_000:
        for divisor in (1e6, 1e3):
            candidate = round(m / divisor, 2)
            if 25 <= candidate <= MAX_ABSOLUTE_NOTIONAL_USD:
                return validate_notional_usd(candidate, base_asset, qty=q)[0]

    if p_human > 0 and q > 0:
        raw = round(amount_to_usd(p_human * q, base_asset), 2)
        return validate_notional_usd(raw, base_asset, fill_price=p_human, qty=q)[0]
    if 0 < m < 1_000_000:
        raw = round(amount_to_usd(m, base_asset), 2)
        return validate_notional_usd(raw, base_asset, qty=q)[0]
    return 0.0
