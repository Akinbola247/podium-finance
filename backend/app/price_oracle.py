from __future__ import annotations

import httpx

from .config import get_settings
from .redis_client import cache_price, get_cached_price

_memory_prices: dict[str, float] = {}

COINGECKO_IDS = {
    "INJ": "injective-protocol",
    "USDT": "tether",
    "USDC": "usd-coin",
    "ATOM": "cosmos",
    "WETH": "weth",
    "WBTC": "wrapped-bitcoin",
    "ETH": "ethereum",
    "BTC": "bitcoin",
    "SOL": "solana",
    "APT": "aptos",
    "ARB": "arbitrum",
    "OP": "optimism",
    "LINK": "chainlink",
    "AAVE": "aave",
    "LTC": "litecoin",
    "TON": "the-open-network",
    "ZEC": "zcash",
    "TAO": "bittensor",
}

INJ_DECIMALS = 18


def denom_to_symbol(denom: str) -> str:
    d = denom.lower()
    if d in ("inj", "microinj"):
        return "INJ"
    if "usdt" in d or "peggy0xdac17f958d2ee523a2206206994597c13d831ec7" in d:
        return "USDT"
    if "usdc" in d or "peggy0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48" in d:
        return "USDC"
    if "atom" in d:
        return "ATOM"
    if "weth" in d or "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2" in d:
        return "WETH"
    if "btc" in d or "wbtc" in d:
        return "WBTC"
    if d.startswith("factory/"):
        return denom.split("/")[-1].upper()[:12]
    if "peggy" in d or d.startswith("erc20:"):
        if "/" in denom:
            return denom.split("/")[-1].upper()[:12]
    return denom.upper()[:12]


def parse_chain_amount(amount_str: str, denom: str) -> float:
    try:
        raw = float(amount_str)
    except (TypeError, ValueError):
        return 0.0
    symbol = denom_to_symbol(denom)
    if symbol == "INJ":
        return raw / (10**INJ_DECIMALS)
    if symbol in ("USDT", "USDC"):
        return raw / 1e6
    return raw / (10**INJ_DECIMALS)


def _cache_price_safe(symbol: str, price: float) -> None:
    _memory_prices[symbol.upper()] = price
    try:
        cache_price(symbol, price)
    except Exception:
        pass


def fetch_usd_price(symbol: str) -> float:
    symbol = symbol.upper()
    if symbol in _memory_prices:
        return _memory_prices[symbol]

    try:
        cached = get_cached_price(symbol)
        if cached is not None:
            _memory_prices[symbol] = cached
            return cached
    except Exception:
        pass

    cg_id = COINGECKO_IDS.get(symbol)
    if not cg_id:
        fallback = 1.0 if symbol in ("USDT", "USDC") else 0.0
        _cache_price_safe(symbol, fallback)
        return fallback

    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": cg_id, "vs_currencies": "usd"},
            )
            res.raise_for_status()
            price = float(res.json()[cg_id]["usd"])
            _cache_price_safe(symbol, price)
            return price
    except Exception:
        fallback = 1.0 if symbol in ("USDT", "USDC") else 0.0
        _memory_prices[symbol] = fallback
        return fallback


def amount_to_usd(amount: float, symbol: str) -> float:
    price = fetch_usd_price(symbol)
    return round(amount * price, 2)
