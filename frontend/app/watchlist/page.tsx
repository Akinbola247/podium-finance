"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE } from "../../lib/api";
import type { WatchlistItem } from "../../lib/types";
import { AddWalletForm } from "../../components/watchlist/add-wallet-form";
import { WatchlistSidebar } from "../../components/watchlist/watchlist-sidebar";
import { truncateAddress } from "../../lib/format";
import { RiskBadge } from "../../components/ui/badges";

export default function WatchlistPage() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const load = useCallback(async () => {
    const res = await fetch(`${API_BASE}/api/v1/watchlist`);
    if (res.ok) setWatchlist(await res.json());
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="mx-auto max-w-3xl p-4 lg:p-6">
      <h1 className="font-display text-2xl font-bold text-text-primary">Watchlist</h1>
      <p className="mt-2 font-mono text-sm text-text-secondary">
        Track inj1 wallets for live Helix activity and risk-bounded blueprints.
      </p>

      <div className="panel mt-6 p-4">
        <h2 className="font-mono text-xs font-semibold tracking-wider text-text-secondary">
          ADD WALLET
        </h2>
        <div className="mt-3">
          <AddWalletForm onAdded={load} />
        </div>
      </div>

      <div className="panel mt-4 p-4">
        <div className="flex items-center justify-between">
          <h2 className="font-mono text-xs font-semibold tracking-wider text-text-secondary">
            TRACKED ({watchlist.length})
          </h2>
          <Link href="/discover" className="font-mono text-[10px] text-accent-glow hover:underline">
            Discover traders →
          </Link>
        </div>
        <div className="watchlist-scroll mt-3 max-h-[min(480px,calc(100vh-280px))]">
          <WatchlistSidebar
            watchlist={watchlist}
            selectedAddress=""
            onSelect={() => {}}
          />
        </div>
        <ul className="mt-4 space-y-2">
          {watchlist.map((w) => (
            <li
              key={w.wallet_address}
              className="flex items-center justify-between rounded border border-border px-3 py-2"
            >
              <div>
                <p className="font-mono text-sm">{w.alias || truncateAddress(w.wallet_address)}</p>
                <p className="font-mono text-[10px] text-text-muted">{w.wallet_address}</p>
              </div>
              <div className="flex items-center gap-2">
                <RiskBadge risk={w.risk_category_override} />
                <Link
                  href={`/?wallet=${w.wallet_address}`}
                  className="font-mono text-[10px] text-accent-glow"
                >
                  Dashboard
                </Link>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="panel mt-4 border border-accent-glow/20 p-4">
        <p className="font-mono text-xs text-text-secondary">
          For live Helix trader discovery (recommended), use{" "}
          <Link href="/discover" className="text-accent-glow hover:underline">
            Discover
          </Link>{" "}
          — scans mainnet explorer in real time. Static JSON bulk imports are disabled in the UI
          to avoid stale or staker-only lists.
        </p>
      </div>

    </div>
  );
}
