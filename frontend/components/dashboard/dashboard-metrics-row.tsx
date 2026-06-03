"use client";

import Link from "next/link";
import { ConvictionGauge } from "../ui/conviction-gauge";
import { PortfolioDonut } from "../ui/portfolio-donut";
import { BiasBadge, RiskBadge } from "../ui/badges";
import { PnlSparkline } from "../charts/pnl-sparkline";
import { truncateAddress, formatUsd, copyToClipboard } from "../../lib/format";
import { EXPLORER_ACCOUNT_URL } from "../../lib/api";
import type { WatchlistItem } from "../../lib/types";

export function DashboardMetricsRow({
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
      <div className="panel mb-3 shrink-0 px-4 py-6 text-center font-mono text-xs text-text-muted">
        Select a watched wallet to view conviction, allocation, and P&L charts
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="panel mb-3 flex h-[140px] shrink-0 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-accent-glow" />
      </div>
    );
  }

  const wl = watchlist.find((w) => w.wallet_address === selectedAddress);
  const m = profile.metrics || {};
  const q = profile.quant_analysis || {};
  const pnl = m.combined_pnl_usd ?? q.combined_pnl_usd;
  const pnlPositive = (pnl ?? 0) >= 0;
  const recentFills = (q.recent_fills as { timestamp: string; realized_pnl_usd?: number | null; notional_usd?: number }[]) ?? [];

  return (
    <section className="panel dashboard-metrics-panel mb-3 shrink-0 overflow-hidden p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle pb-2">
        <div>
          <h2 className="font-display text-sm font-semibold text-text-primary">
            {profile.alias || wl?.alias || "Whale metrics"}
          </h2>
          <button
            type="button"
            className="font-mono text-[10px] text-accent-glow hover:underline"
            onClick={() => copyToClipboard(selectedAddress)}
            title={selectedAddress}
          >
            {truncateAddress(selectedAddress)} ⎘
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <RiskBadge risk={wl?.risk_category_override} />
          <BiasBadge bias={m.recent_directional_bias} />
          <span className="font-mono text-[10px] text-text-muted">
            {m.dominant_strategy || "—"}
          </span>
          <a
            href={EXPLORER_ACCOUNT_URL(selectedAddress)}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-[9px] text-text-secondary hover:text-accent-glow"
          >
            Explorer ↗
          </a>
          <Link
            href={`/profile/${selectedAddress}`}
            className="font-mono text-[9px] text-text-secondary hover:text-accent-glow"
          >
            Deep dive
          </Link>
        </div>
      </div>

      <div className="dashboard-metrics-grid">
        <div className="metrics-chart-cell metrics-chart-cell--gauge">
          <ConvictionGauge score={m.conviction_score ?? 0} size="sm" />
          <p className="mt-0.5 font-mono text-[8px] tracking-[0.12em] text-text-muted">
            CONVICTION — 30D
          </p>
        </div>

        <div className="metrics-chart-cell metrics-chart-cell--stats grid grid-cols-2 gap-2">
          <MetricCell
            label="30d P&L"
            value={formatUsd(pnl)}
            positive={pnlPositive}
            large
          />
          <MetricCell
            label="Win rate"
            value={`${m.win_rate_pct ?? q.win_rate_pct ?? "—"}%`}
          />
          <MetricCell label="Closed lots" value={String(q.closed_trades_count ?? 0)} />
          <MetricCell
            label="Profit factor"
            value={m.profit_factor != null ? String(m.profit_factor) : "—"}
          />
        </div>

        <div className="metrics-chart-cell metrics-chart-cell--donut">
          <p className="mb-1 font-mono text-[8px] uppercase tracking-wider text-text-muted">
            Allocation
          </p>
          {profile.portfolio_distribution?.length > 0 ? (
            <PortfolioDonut distribution={profile.portfolio_distribution} compact />
          ) : (
            <div className="flex flex-1 items-center justify-center font-mono text-[10px] text-text-muted">
              No allocation data yet
            </div>
          )}
        </div>

        <div className="metrics-chart-cell metrics-chart-cell--pnl">
          <PnlSparkline fills={recentFills} />
        </div>
      </div>
    </section>
  );
}

function MetricCell({
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
    <div className="rounded-md border border-border bg-bg-panel px-2.5 py-2">
      <p className="font-mono text-[8px] uppercase tracking-wider text-text-muted">{label}</p>
      <p
        className={`font-mono font-semibold ${large ? "text-lg" : "text-sm"} ${
          positive === true ? "text-long" : positive === false ? "text-short" : "text-text-primary"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
