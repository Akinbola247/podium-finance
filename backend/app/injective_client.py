from __future__ import annotations

from typing import Any

import httpx

from .config import get_settings


class InjectiveExplorerClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.injective_explorer_base
        self.timeout = 20.0

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, params=params or {})
            response.raise_for_status()
            return response.json()

    def fetch_latest_txs(self, limit: int = 40, skip: int = 0) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if skip > 0:
            params["skip"] = skip
        payload = self._get("txs", params=params)
        return payload.get("data", [])

    def fetch_latest_txs_pages(
        self, *, pages: int = 20, page_size: int = 80
    ) -> list[dict[str, Any]]:
        """Paginated global tx feed (skip avoids duplicate batches)."""
        seen_hashes: set[str] = set()
        merged: list[dict[str, Any]] = []
        for page in range(pages):
            batch = self.fetch_latest_txs(limit=page_size, skip=page * page_size)
            if not batch:
                break
            for tx in batch:
                h = tx.get("hash")
                if h and h in seen_hashes:
                    continue
                if h:
                    seen_hashes.add(h)
                merged.append(tx)
        return merged

    def fetch_account_txs(self, address: str, limit: int = 80) -> list[dict[str, Any]]:
        payload = self._get(f"accountTxs/{address}", params={"limit": limit})
        return payload.get("data", [])
