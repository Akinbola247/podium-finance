"use client";

import { useState } from "react";

import { API_BASE } from "../lib/api";

export type DiscoveredWhale = {
  address: string;
  label: string;
  score: number;
  copyability_tier: string;
  exchange_events_sampled: number;
  exchange_volume_usd: number;
  median_clip_usd: number;
  largest_clip_usd: number;
  volume_usd_sampled: number;
  asset_count: number;
  non_inj_asset_count: number;
  top_assets: string[];
  assets_seen: Record<string, number>;
};

type DiscoverResponse = {
  search_id: string;
  scanned_txs: number;
  qualified_traders: number;
  returned: number;
  criteria?: Record<string, unknown>;
  ecosystem_assets_seen: Record<string, number>;
  whales: DiscoveredWhale[];
  note?: string;
};

const TIER_COLOR: Record<string, string> = {
  A: "#5dffa0",
  B: "#7dd3fc",
  C: "#ffd166",
  D: "#a0a0a0",
};

export function WhaleDiscoveryPanel({ onImported }: { onImported: () => void }) {
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [searchId, setSearchId] = useState("");
  const [result, setResult] = useState<DiscoverResponse | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState("");
  const [limit, setLimit] = useState("100");
  const [minTier, setMinTier] = useState("C");

  async function runDiscover() {
    setLoading(true);
    setMessage(
      "Scanning Helix perp/spot activity only (no stakers or transfers)… ~1–2 min."
    );
    setResult(null);
    setSelected(new Set());
    try {
      const res = await fetch(`${API_BASE}/api/v1/whales/discover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          limit: Number(limit) || 100,
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
        setMessage(typeof data.detail === "string" ? data.detail : "Discovery failed.");
        return;
      }
      const tierRank: Record<string, number> = { A: 4, B: 3, C: 2, D: 1 };
      const minRank = tierRank[minTier] ?? 2;
      const filtered = (data.whales as DiscoveredWhale[]).filter(
        (w) => (tierRank[w.copyability_tier] ?? 0) >= minRank
      );
      setResult({ ...data, whales: filtered });
      setSearchId(data.search_id);
      setSelected(new Set(filtered.map((w) => w.address)));
      setMessage(
        `${filtered.length} copy-worthy traders (tier ≥ ${minTier}) from ${data.qualified_traders} qualified · ${data.scanned_txs} txs scanned.`
      );
    } catch {
      setMessage(`Cannot reach API at ${API_BASE}. Is the backend running?`);
    } finally {
      setLoading(false);
    }
  }

  function toggle(addr: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(addr)) next.delete(addr);
      else next.add(addr);
      return next;
    });
  }

  function selectAll() {
    if (result) setSelected(new Set(result.whales.map((w) => w.address)));
  }

  async function importAddresses(addresses: string[]) {
    if (!searchId || addresses.length === 0) return;
    setImporting(true);
    setMessage(`Importing ${addresses.length} traders…`);
    try {
      const res = await fetch(`${API_BASE}/api/v1/whales/discover/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          search_id: searchId,
          limit: addresses.length,
          addresses,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setMessage(typeof data.detail === "string" ? data.detail : "Import failed.");
        return;
      }
      setMessage(`Imported ${data.imported} traders. Backfill queued.`);
      onImported();
    } catch {
      setMessage("Import request failed.");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid rgba(255,255,255,0.1)" }}>
      <h3>Discover copy-worthy traders</h3>
      <p style={{ fontSize: 12, opacity: 0.75 }}>
        Finds wallets with real <strong>Helix perp/spot</strong> clips — not INJ stakers, bank
        transfers, or LP. Requires ≥2 Helix fills, ≥$300 volume, ≥$75 largest clip (per fill ≥$50).
      </p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <input
          type="number"
          min={10}
          max={150}
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
          style={{ width: 72 }}
          title="Max whales"
        />
        <select value={minTier} onChange={(e) => setMinTier(e.target.value)} title="Min tier">
          <option value="A">Tier A only</option>
          <option value="B">Tier B+</option>
          <option value="C">Tier C+ (default)</option>
          <option value="D">All qualified</option>
        </select>
        <button type="button" onClick={runDiscover} disabled={loading}>
          {loading ? "Scanning…" : "Search active traders"}
        </button>
      </div>

      {result && (
        <div style={{ marginTop: 12 }}>
          <p style={{ fontSize: 12 }}>
            Assets:{" "}
            {Object.keys(result.ecosystem_assets_seen || {})
              .slice(0, 18)
              .join(", ")}
          </p>
          <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
            <button type="button" onClick={selectAll} disabled={importing}>
              Select all
            </button>
            <button
              type="button"
              onClick={() => importAddresses(Array.from(selected))}
              disabled={importing || selected.size === 0}
            >
              Import selected ({selected.size})
            </button>
            <button
              type="button"
              onClick={() => importAddresses(result.whales.map((w) => w.address))}
              disabled={importing || result.whales.length === 0}
            >
              Import all shown ({result.whales.length})
            </button>
          </div>
          <div
            style={{
              maxHeight: 300,
              overflow: "auto",
              fontSize: 12,
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 6,
            }}
          >
            <table style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th></th>
                  <th>Tier</th>
                  <th>Address</th>
                  <th>Assets</th>
                  <th>Exch.</th>
                  <th>Vol $</th>
                  <th>Max clip</th>
                </tr>
              </thead>
              <tbody>
                {result.whales.map((w) => (
                  <tr key={w.address}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selected.has(w.address)}
                        onChange={() => toggle(w.address)}
                      />
                    </td>
                    <td style={{ color: TIER_COLOR[w.copyability_tier] || "#fff" }}>
                      <strong>{w.copyability_tier}</strong>
                    </td>
                    <td title={w.address}>{w.address.slice(0, 16)}…</td>
                    <td>{(w.top_assets || []).slice(0, 4).join(", ")}</td>
                    <td>{w.exchange_events_sampled}</td>
                    <td>{Math.round(w.exchange_volume_usd || w.volume_usd_sampled).toLocaleString()}</td>
                    <td>${Math.round(w.largest_clip_usd || 0).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ fontSize: 11, opacity: 0.65, marginTop: 6 }}>
            Tier A: heavy multi-fill flow · B: solid perp activity · C: meets minimum copy thresholds
          </p>
        </div>
      )}

      {message && <p style={{ fontSize: 12, marginTop: 8, opacity: 0.9 }}>{message}</p>}
    </div>
  );
}
