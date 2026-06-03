#!/usr/bin/env python3
"""CLI: live-discover active traders and optionally write JSON snapshot."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.whale_discovery import discover_active_whales


def main() -> None:
    result = discover_active_whales(limit=100, scan_pages=20, page_size=80)
    out_path = Path(__file__).resolve().parents[2] / "data" / "injective_active_traders.json"
    payload = {
        "metadata": {
            "title": "Injective active Helix traders (inj1)",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "network": "injective-1 mainnet",
            "notes": ["Snapshot from live explorer scan."],
            "counts": {"total": result["returned"]},
        },
        "traders": result["whales"],
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {result['returned']} traders to {out_path}")


if __name__ == "__main__":
    main()
