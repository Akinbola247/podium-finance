"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import Link from "next/link";
import { API_BASE } from "../../lib/api";
import { TierBadge } from "../ui/badges";
import { truncateAddress, formatUsd } from "../../lib/format";
import type { DiscoveredWhale } from "../../lib/types";
import {
  ImportErrorBanner,
  ImportSuccessBanner,
  type ImportResult,
} from "./import-success-banner";

type DiscoverResponse = {
  search_id: string;
  scanned_txs: number;
  qualified_traders: number;
  returned: number;
  ecosystem_assets_seen: Record<string, number>;
  whales: DiscoveredWhale[];
};

type SortKey = "score" | "volume" | "clip";

export function DiscoverPage() {
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [searchId, setSearchId] = useState("");
  const [result, setResult] = useState<DiscoverResponse | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [scanMessage, setScanMessage] = useState("");
  const [importFeedback, setImportFeedback] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState("");
  const [onWatchlist, setOnWatchlist] = useState<Set<string>>(new Set());
  const [tierFilter, setTierFilter] = useState("all");
  const [sortBy, setSortBy] = useState<SortKey>("score");

  async function runDiscover() {
    setLoading(true);
    setScanMessage("");
    setImportFeedback(null);
    setImportError("");
    setResult(null);
    setSelected(new Set());
    try {
      const res = await fetch(`${API_BASE}/api/v1/whales/discover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          limit: 100,
          scan_pages: 40,
          page_size: 80,
          min_notional_usd: 50,
          min_exchange_events: 2,
          min_exchange_volume_usd: 300,
          min_largest_clip_usd: 75,
          prefer_multi_asset: true,
          exclude_watchlist: true,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setScanMessage(typeof data.detail === "string" ? data.detail : "Discovery failed.");
        return;
      }
      setResult(data);
      setSearchId(data.search_id);
      setSelected(new Set(data.whales.map((w: DiscoveredWhale) => w.address)));
      setScanMessage(
        `Live scan complete — ${data.returned} traders · ${data.qualified_traders} qualified · ${data.scanned_txs} txs from Injective explorer`
      );
    } catch {
      setScanMessage(`Cannot reach API at ${API_BASE}`);
    } finally {
      setLoading(false);
    }
  }

  const whales = useMemo(() => {
    if (!result) return [];
    let list = [...result.whales];
    if (tierFilter !== "all") {
      list = list.filter((w) => w.copyability_tier === tierFilter);
    }
    list.sort((a, b) => {
      if (sortBy === "volume")
        return (b.exchange_volume_usd || 0) - (a.exchange_volume_usd || 0);
      if (sortBy === "clip") return (b.largest_clip_usd || 0) - (a.largest_clip_usd || 0);
      return (b.score || 0) - (a.score || 0);
    });
    return list;
  }, [result, tierFilter, sortBy]);

  function toggle(addr: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(addr)) next.delete(addr);
      else next.add(addr);
      return next;
    });
  }

  async function importSelected(addresses?: string[]) {
    const toImport = addresses ?? Array.from(selected);
    if (!searchId || toImport.length === 0) return;
    setImporting(true);
    setImportError("");
    setImportFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/whales/discover/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          search_id: searchId,
          limit: toImport.length,
          addresses: toImport,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setImportError(typeof data.detail === "string" ? data.detail : "Import failed.");
        return;
      }
      setImportFeedback({
        imported: data.imported ?? 0,
        rebackfill_queued: data.rebackfill_queued,
        skipped: data.skipped,
        wallets_added: data.wallets_added,
        message: data.message,
      });
      if (data.imported > 0) {
        const addedAddrs = (data.wallets_added ?? []).map((w: { address: string }) => w.address);
        setOnWatchlist((prev) => {
          const next = new Set(prev);
          for (const a of addedAddrs) next.add(a);
          return next;
        });
        setSelected((prev) => {
          const next = new Set(prev);
          for (const a of addedAddrs) next.delete(a);
          return next;
        });
      }
    } catch {
      setImportError("Import request failed. Is the backend running?");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="mx-auto max-w-[1400px] p-4 lg:p-6">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-bold tracking-tight text-text-primary">
          DISCOVER COPY-WORTHY TRADERS
        </h1>
        <p className="mt-2 max-w-2xl font-mono text-sm text-text-secondary">
          Scans recent Helix activity and ranks active traders by copyability — not stakers.
        </p>
        <button
          type="button"
          className="btn-primary mt-4 max-w-xs"
          onClick={runDiscover}
          disabled={loading}
        >
          {loading ? "Scanning…" : "Scan Now"}
        </button>
      </header>

      {loading && (
        <div className="panel relative mb-6 overflow-hidden p-8">
          <div className="scan-beam absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-accent-glow/30 to-transparent" />
          <p className="relative text-center font-mono text-sm text-text-primary">
            Scanning Injective Helix… this takes ~1–2 minutes
          </p>
          <p className="relative mt-2 text-center font-mono text-xs text-text-muted">
            Filtering exchange fills from staking/governance activity
          </p>
        </div>
      )}

      {scanMessage && !importFeedback && (
        <p className="mb-4 font-mono text-xs text-text-secondary">{scanMessage}</p>
      )}

      {importFeedback && (
        <ImportSuccessBanner
          result={importFeedback}
          onDismiss={() => setImportFeedback(null)}
        />
      )}
      {importError && (
        <ImportErrorBanner message={importError} onDismiss={() => setImportError("")} />
      )}

      {result && !loading && (
        <>
          <div className="mb-3 flex flex-wrap gap-2">
            <select
              className="input-field max-w-[120px]"
              value={tierFilter}
              onChange={(e) => setTierFilter(e.target.value)}
            >
              <option value="all">All tiers</option>
              <option value="A">Tier A</option>
              <option value="B">Tier B</option>
              <option value="C">Tier C</option>
              <option value="D">Tier D</option>
            </select>
            <select
              className="input-field max-w-[140px]"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortKey)}
            >
              <option value="score">Sort: Score</option>
              <option value="volume">Sort: Volume</option>
              <option value="clip">Sort: Largest clip</option>
            </select>
            <button type="button" className="btn-ghost" onClick={() => setSelected(new Set(whales.map((w) => w.address)))}>
              Select all
            </button>
          </div>

          {selected.size > 0 && (
            <div className="sticky top-14 z-30 mb-3 flex items-center justify-between rounded-lg border border-accent-glow/40 bg-bg-card px-4 py-2 shadow-lg">
              <span className="font-mono text-xs text-text-secondary">
                {selected.size} selected
              </span>
              <button
                type="button"
                className="btn-primary !w-auto"
                disabled={importing || selected.size === 0}
                onClick={() => importSelected()}
              >
                {importing ? "Adding to watchlist…" : `Add ${selected.size} to watchlist`}
              </button>
            </div>
          )}

          <div className="panel overflow-hidden">
            <div className="overflow-x-auto">
              <table className="data-table w-full">
                <thead className="sticky top-0 bg-bg-card">
                  <tr>
                    <th className="w-8" />
                    <th>Tier</th>
                    <th>Address</th>
                    <th>Label</th>
                    <th>Score</th>
                    <th>Events</th>
                    <th>Volume</th>
                    <th>Median</th>
                    <th>Max clip</th>
                    <th title="Repeat Helix fills with meaningful clip size — not stakers">
                      Top assets ⓘ
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {whales.map((w) => (
                    <tr
                      key={w.address}
                      className={clsx(selected.has(w.address) && "bg-accent-primary/10")}
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={selected.has(w.address)}
                          onChange={() => toggle(w.address)}
                        />
                      </td>
                      <td>
                        <TierBadge tier={w.copyability_tier} />
                      </td>
                      <td className="font-mono text-[11px]" title={w.address}>
                        <Link href={`/profile/${w.address}`} className="text-accent-glow hover:underline">
                          {truncateAddress(w.address)}
                        </Link>
                        {onWatchlist.has(w.address) && (
                          <span className="ml-1 rounded bg-long/15 px-1 font-mono text-[8px] text-long">
                            ON WATCHLIST
                          </span>
                        )}
                      </td>
                      <td className="text-[11px] text-text-secondary">{w.label}</td>
                      <td className="font-mono text-xs">{Math.round(w.score)}</td>
                      <td className="font-mono text-xs">{w.exchange_events_sampled}</td>
                      <td className="font-mono text-xs">
                        {formatUsd(w.exchange_volume_usd || w.volume_usd_sampled, { compact: true })}
                      </td>
                      <td className="font-mono text-xs">{formatUsd(w.median_clip_usd, { compact: true })}</td>
                      <td className="font-mono text-xs font-semibold text-text-primary">
                        {formatUsd(w.largest_clip_usd, { compact: true })}
                      </td>
                      <td className="text-[10px] text-text-muted">
                        {(w.top_assets || []).slice(0, 4).join(", ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <p className="mt-4 font-mono text-[10px] text-text-muted">
            Tier A: heavy multi-fill flow · B: solid perp activity · C: minimum copy thresholds
          </p>
          <Link href="/" className="mt-4 inline-block font-mono text-xs text-accent-glow hover:underline">
            ← Back to dashboard
          </Link>
        </>
      )}
    </div>
  );
}
