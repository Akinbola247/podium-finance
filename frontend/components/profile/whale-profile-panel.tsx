"use client";

import Link from "next/link";
import { ConvictionGauge } from "../ui/conviction-gauge";
import { PortfolioDonut } from "../ui/portfolio-donut";
import { BiasBadge, RiskBadge } from "../ui/badges";
import {
  truncateAddress,
  formatUsd,
  copyToClipboard,
  absoluteTime,
} from "../../lib/format";
import { EXPLORER_ACCOUNT_URL } from "../../lib/api";
import type { WatchlistItem } from "../../lib/types";

export function WhaleProfilePanel({
  profile,
  selectedAddress,
  watchlist,
}: {
  profile: any;
  selectedAddress: string;
  watchlist: WatchlistItem[];
}) {
  if (!selectedAddress) {
    return (
      <p className="py-8 text-center font-mono text-xs text-text-muted">
        Select a watched wallet
      </p>
    );
  }

  if (!profile) {
    return (
      <div className="flex justify-center py-8">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-accent-glow" />
      </div>
    );
  }

  const wl = watchlist.find((w) => w.wallet_address === selectedAddress);
  const m = profile.metrics || {};
  const q = profile.quant_analysis || {};
  const pnl = m.combined_pnl_usd ?? q.combined_pnl_usd;
  const pnlPositive = (pnl ?? 0) >= 0;

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="font-display text-sm font-semibold text-text-primary">
              {profile.alias || wl?.alias || "Whale"}
            </h3>
            <button
              type="button"
              className="font-mono text-[10px] text-accent-glow hover:underline"
              onClick={() => copyToClipboard(selectedAddress)}
              title={selectedAddress}
            >
              {truncateAddress(selectedAddress)} ⎘
            </button>
          </div>
          <div className="flex gap-1">
            <a
              href={EXPLORER_ACCOUNT_URL(selectedAddress)}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded border border-border px-1.5 py-0.5 font-mono text-[9px] text-text-secondary hover:text-accent-glow"
            >
              Explorer ↗
            </a>
            <Link
              href={`/profile/${selectedAddress}`}
              className="rounded border border-border px-1.5 py-0.5 font-mono text-[9px] text-text-secondary hover:text-accent-glow"
            >
              Deep dive
            </Link>
          </div>
        </div>
        <div className="mt-2 flex gap-2">
          <RiskBadge risk={wl?.risk_category_override} />
          <BiasBadge bias={m.recent_directional_bias} />
        </div>
        {profile.updated_at && (
          <p className="mt-1 font-mono text-[9px] text-text-muted">
            Updated {absoluteTime(profile.updated_at)}
          </p>
        )}
      </div>

      <ConvictionGauge score={m.conviction_score ?? 0} />
      <p className="-mt-2 text-center font-mono text-[9px] text-text-muted">
        CONVICTION SCORE — 30D COMPOSITE
      </p>

      <div className="grid grid-cols-2 gap-2">
        <StatChip
          label="30d P&L"
          value={formatUsd(pnl)}
          positive={pnlPositive}
          large
        />
        <StatChip label="Win rate" value={`${m.win_rate_pct ?? q.win_rate_pct ?? "—"}%`} />
        <StatChip label="Closed lots" value={String(q.closed_trades_count ?? 0)} />
        <StatChip
          label="Profit factor"
          value={m.profit_factor != null ? String(m.profit_factor) : "—"}
        />
      </div>

      <p className="font-mono text-[10px] text-text-secondary">
        <span className="text-text-muted">Strategy:</span> {m.dominant_strategy || "—"}
      </p>

      {profile.portfolio_distribution?.length > 0 && (
        <PortfolioDonut distribution={profile.portfolio_distribution} />
      )}

      {q.by_asset?.length > 0 && (
        <details className="rounded border border-border">
          <summary className="cursor-pointer px-2 py-1.5 font-mono text-[10px] text-text-secondary">
            Per-asset quant ({q.by_asset.length})
          </summary>
          <div className="max-h-40 overflow-auto">
            <table className="data-table text-[10px]">
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>P&L</th>
                  <th>Win%</th>
                </tr>
              </thead>
              <tbody>
                {q.by_asset.slice(0, 6).map((a: any) => (
                  <tr key={a.asset}>
                    <td>{a.asset}</td>
                    <td className={a.realized_pnl_usd >= 0 ? "text-long" : "text-short"}>
                      {formatUsd(a.realized_pnl_usd)}
                    </td>
                    <td>{a.win_rate_pct ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  );
}

function StatChip({
  label,
  value,
  positive,
  large,
}: {
  label: string;
  value: string;
  positive?: boolean;
  large?: boolean;
}) {
  return (
    <div className="rounded-md border border-border bg-bg-panel px-2 py-2">
      <p className="font-mono text-[9px] uppercase tracking-wider text-text-muted">{label}</p>
      <p
        className={`font-mono font-semibold ${large ? "text-base" : "text-sm"} ${
          positive === true ? "text-long" : positive === false ? "text-short" : "text-text-primary"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
