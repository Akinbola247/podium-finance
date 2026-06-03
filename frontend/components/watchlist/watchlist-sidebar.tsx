"use client";

import Link from "next/link";
import clsx from "clsx";
import type { WatchlistItem } from "../../lib/types";
import { truncateAddress } from "../../lib/format";
import { RiskBadge } from "../ui/badges";

const RISK_BORDER: Record<string, string> = {
  conservative: "border-l-accent-primary",
  moderate: "border-l-warning",
  aggressive: "border-l-short",
};

export function WatchlistSidebar({
  watchlist,
  selectedAddress,
  onSelect,
}: {
  watchlist: WatchlistItem[];
  selectedAddress: string;
  onSelect: (addr: string) => void;
}) {
  if (watchlist.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border p-4 text-center">
        <p className="font-mono text-xs text-text-secondary">No wallets tracked</p>
        <Link
          href="/discover"
          className="mt-3 inline-block rounded-md bg-accent-primary px-3 py-2 font-mono text-xs text-white hover:bg-accent-glow"
        >
          Discover Active Whales
        </Link>
        <Link
          href="/watchlist"
          className="mt-2 block font-mono text-[10px] text-text-muted hover:text-accent-glow"
        >
          Add wallet manually →
        </Link>
      </div>
    );
  }

  return (
    <ul className="space-y-1">
      {watchlist.map((w) => {
        const active = w.wallet_address === selectedAddress;
        const risk = (w.risk_category_override || "moderate").toLowerCase();
        return (
          <li key={w.wallet_address}>
            <button
              type="button"
              onClick={() => onSelect(w.wallet_address)}
              className={clsx(
                "w-full rounded-r-md border-l-[3px] px-2 py-2 text-left transition-colors",
                RISK_BORDER[risk] ?? RISK_BORDER.moderate,
                active
                  ? "bg-accent-primary/15 text-text-primary"
                  : "border-l-transparent bg-transparent text-text-secondary hover:bg-bg-card-hover"
              )}
            >
              <div className="flex items-center justify-between gap-1">
                <span className="truncate font-mono text-xs font-semibold text-text-primary">
                  {w.alias || truncateAddress(w.wallet_address)}
                </span>
                {active && (
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-long animate-pulse" />
                )}
              </div>
              <span className="font-mono text-[10px] text-text-muted">
                {truncateAddress(w.wallet_address)}
              </span>
              <div className="mt-1">
                <RiskBadge risk={risk} />
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
