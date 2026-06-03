"use client";

import Link from "next/link";
import clsx from "clsx";
import { truncateAddress } from "../../lib/format";

export type ImportResult = {
  imported: number;
  rebackfill_queued?: number;
  skipped?: { address: string; reason: string }[];
  wallets_added?: { address: string; alias?: string | null }[];
  message?: string;
};

export function ImportSuccessBanner({
  result,
  onDismiss,
}: {
  result: ImportResult;
  onDismiss: () => void;
}) {
  const skipped = result.skipped ?? [];
  const wallets = result.wallets_added ?? [];

  return (
    <div
      className="mb-4 rounded-lg border border-long/40 bg-long-muted p-4"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-long/20 text-long">
          ✓
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="font-display text-sm font-semibold text-long">
            {result.imported > 0
              ? `${result.imported} wallet${result.imported === 1 ? "" : "s"} added to watchlist`
              : "No new wallets added"}
          </h3>
          <p className="mt-1 font-mono text-xs text-text-secondary">
            {result.message ||
              "Live backfill from Injective mainnet is queued. Activity will appear on the dashboard once ingested."}
          </p>
          {(result.rebackfill_queued ?? 0) > 0 && (
            <p className="mt-1 font-mono text-[10px] text-text-muted">
              {result.rebackfill_queued} already tracked — backfill re-queued.
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 font-mono text-lg text-text-muted hover:text-text-primary"
          aria-label="Dismiss"
        >
          ×
        </button>
      </div>

      {wallets.length > 0 && (
        <ul className="mt-3 max-h-32 space-y-1 overflow-y-auto rounded border border-border bg-bg-base/50 px-2 py-2">
          {wallets.map((w) => (
            <li
              key={w.address}
              className="flex items-center justify-between gap-2 font-mono text-[11px]"
            >
              <span className="text-text-primary">
                {w.alias ? (
                  <>
                    <strong>{w.alias}</strong>
                    <span className="ml-2 text-text-muted">{truncateAddress(w.address)}</span>
                  </>
                ) : (
                  truncateAddress(w.address)
                )}
              </span>
              <span className="text-long">Tracking</span>
            </li>
          ))}
        </ul>
      )}

      {skipped.length > 0 && (
        <p className="mt-2 font-mono text-[10px] text-text-muted">
          Skipped: {skipped.length} ({skipped.map((s) => s.reason).join(", ")})
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <Link href="/watchlist" className="btn-primary !w-auto px-4 py-2 text-xs">
          View watchlist
        </Link>
        <Link href="/" className="btn-ghost !w-auto px-4 py-2 text-xs">
          Open dashboard tape
        </Link>
      </div>
    </div>
  );
}

export function ImportErrorBanner({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss: () => void;
}) {
  return (
    <div
      className={clsx(
        "mb-4 rounded-lg border border-short/40 bg-short-muted p-4 font-mono text-xs text-short"
      )}
      role="alert"
    >
      <div className="flex justify-between gap-2">
        <span>⚠ {message}</span>
        <button type="button" onClick={onDismiss} className="text-text-muted hover:text-text-primary">
          ×
        </button>
      </div>
    </div>
  );
}
