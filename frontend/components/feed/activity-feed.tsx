"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import type { Activity } from "../../lib/types";
import { SideBadge, AiChip } from "../ui/badges";
import {
  formatUsd,
  formatPrice,
  truncateAddress,
  relativeTime,
  absoluteTime,
  parseSideKind,
} from "../../lib/format";
import Link from "next/link";

type SideFilter = "all" | "long" | "short" | "swap";

export function ActivityFeed({
  activities,
  watchlist,
  selectedEventId,
  flashIds,
  loadError,
  lastUpdated,
  streamStatus,
  onSelectEvent,
  walletFilter,
  onWalletFilterChange,
  wallets,
}: {
  activities: Activity[];
  watchlist: { wallet_address: string; alias: string | null }[];
  selectedEventId: string;
  flashIds: Set<string>;
  loadError: string;
  lastUpdated: Date | null;
  streamStatus: string;
  onSelectEvent: (id: string) => void;
  walletFilter: string;
  onWalletFilterChange: (addr: string) => void;
  wallets: string[];
}) {
  const [sideFilter, setSideFilter] = useState<SideFilter>("all");
  const [assetFilter, setAssetFilter] = useState("all");

  const assets = useMemo(() => {
    const set = new Set(activities.map((a) => a.asset_affected));
    return ["all", ...Array.from(set).sort()];
  }, [activities]);

  const filtered = useMemo(() => {
    return activities.filter((row) => {
      if (sideFilter !== "all") {
        const k = parseSideKind(row.execution_side || row.activity_type);
        if (sideFilter === "long" && k !== "long") return false;
        if (sideFilter === "short" && k !== "short") return false;
        if (sideFilter === "swap" && k !== "swap") return false;
      }
      if (assetFilter !== "all" && row.asset_affected !== assetFilter) return false;
      return true;
    });
  }, [activities, sideFilter, assetFilter]);

  return (
    <div className="panel flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3 py-2">
        <div>
          <h2 className="font-mono text-xs font-semibold tracking-[0.12em] text-text-primary">
            WHALE TAPE — LIVE HELIX ACTIVITY
          </h2>
          <p className="font-mono text-[9px] text-text-muted">
            ¹ ~ = oracle-adjusted estimate when tick decode was ambiguous
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {streamStatus === "live" && (
            <span className="flex items-center gap-1 font-mono text-[10px] text-long">
              <span className="h-1.5 w-1.5 rounded-full bg-long animate-pulse" /> LIVE
            </span>
          )}
          {lastUpdated && (
            <span className="font-mono text-[10px] text-text-muted">
              Updated {relativeTime(lastUpdated.toISOString())} ago
            </span>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-border-subtle px-3 py-2">
        <select
          className="input-field !mt-0 max-w-[180px] py-1 text-[10px]"
          value={walletFilter}
          onChange={(e) => onWalletFilterChange(e.target.value)}
        >
          <option value="">All watched</option>
          {wallets.map((w) => (
            <option key={w} value={w}>
              {watchlist.find((x) => x.wallet_address === w)?.alias || truncateAddress(w)}
            </option>
          ))}
        </select>
        <select
          className="input-field !mt-0 max-w-[100px] py-1 text-[10px]"
          value={sideFilter}
          onChange={(e) => setSideFilter(e.target.value as SideFilter)}
        >
          <option value="all">All sides</option>
          <option value="long">Long</option>
          <option value="short">Short</option>
          <option value="swap">Swap</option>
        </select>
        <select
          className="input-field !mt-0 max-w-[90px] py-1 text-[10px]"
          value={assetFilter}
          onChange={(e) => setAssetFilter(e.target.value)}
        >
          {assets.map((a) => (
            <option key={a} value={a}>
              {a === "all" ? "All assets" : a}
            </option>
          ))}
        </select>
      </div>

      {loadError && activities.length === 0 && (
        <div className="m-3 rounded-md border border-short/40 bg-short/10 p-3">
          <p className="font-mono text-xs text-short">⚠ {loadError}</p>
          <pre className="mt-2 overflow-x-auto rounded bg-bg-base p-2 font-mono text-[10px] text-text-muted">
            cd backend && uvicorn app.main:app --reload{"\n"}
            python -m worker.stream_worker
          </pre>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-auto">
        <table className="data-table w-full">
          <thead className="sticky top-0 z-10 bg-bg-card">
            <tr>
              <th className="w-[72px]">Time</th>
              <th className="w-[100px]">Side</th>
              <th className="w-[72px]">Asset</th>
              <th className="w-[96px]">Fill $</th>
              <th className="w-[100px]">Notional</th>
              <th className="w-[88px]">P&L</th>
              <th className="w-[120px]">Wallet</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => {
              const pnl = row.realized_pnl_usd ?? row.unrealized_pnl_usd ?? null;
              const isUnrealized = row.realized_pnl_usd == null && row.unrealized_pnl_usd != null;
              const selected = row.event_id === selectedEventId;
              const flash = flashIds.has(row.event_id);
              const alias = watchlist.find((w) => w.wallet_address === row.wallet_address)?.alias;

              return (
                <tr
                  key={row.event_id}
                  onClick={() => onSelectEvent(row.event_id)}
                  className={clsx(
                    "feed-row cursor-pointer transition-colors",
                    selected && "feed-row-selected",
                    flash && "feed-row-flash"
                  )}
                  title={absoluteTime(row.timestamp)}
                >
                  <td className="font-mono text-[11px] text-text-secondary">
                    {relativeTime(row.timestamp)}
                  </td>
                  <td>
                    <SideBadge side={row.execution_side || row.activity_type} />
                  </td>
                  <td>
                    <span className="font-mono text-xs font-semibold">{row.asset_affected}</span>
                    {row.activity_type?.includes("MARGIN") && (
                      <span className="ml-1 rounded bg-accent-primary/20 px-1 font-mono text-[8px] text-accent-glow">
                        PERP
                      </span>
                    )}
                  </td>
                  <td className="font-mono text-[11px] text-text-secondary">
                    {formatPrice(row.fill_price_usd)}
                  </td>
                  <td className="font-mono text-xs font-bold text-text-primary">
                    {formatUsd(row.notional_value_usd, {
                      adjusted: row.notional_adjusted,
                    })}
                  </td>
                  <td
                    className={clsx(
                      "font-mono text-xs",
                      pnl == null
                        ? "text-text-muted"
                        : pnl >= 0
                          ? "text-long"
                          : "text-short"
                    )}
                    title={
                      pnl == null
                        ? "Estimated P&L unavailable for this event type"
                        : isUnrealized
                          ? "Unrealized mark-to-market estimate — not exchange-confirmed"
                          : "Realized — matched closed lot"
                    }
                  >
                    {row.realized_pnl_usd != null
                      ? formatUsd(row.realized_pnl_usd)
                      : row.unrealized_pnl_usd != null
                        ? `~${formatUsd(row.unrealized_pnl_usd)}`
                        : "—"}
                  </td>
                  <td>
                    <Link
                      href={`/profile/${row.wallet_address}`}
                      onClick={(e) => e.stopPropagation()}
                      className="font-mono text-[10px] text-accent-glow hover:underline"
                    >
                      {alias || truncateAddress(row.wallet_address)}
                    </Link>
                  </td>
                  <td className="max-w-[200px]">
                    <span className="line-clamp-1 font-mono text-[10px] text-text-secondary">
                      {row.ai_interpretation || "—"}
                    </span>
                    {row.ai_interpretation && <AiChip />}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && !loadError && (
          <p className="p-6 text-center font-mono text-xs text-text-muted">
            No rows match filters
          </p>
        )}
      </div>
    </div>
  );
}
