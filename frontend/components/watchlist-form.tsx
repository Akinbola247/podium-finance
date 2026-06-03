"use client";

import { FormEvent, useState } from "react";
import { WhaleDiscoveryPanel } from "./whale-discovery-panel";

import { API_BASE } from "../lib/api";

export function WatchlistForm({ onAdded }: { onAdded: () => void }) {
  const [wallet_address, setAddress] = useState("");
  const [alias, setAlias] = useState("");
  const [risk_category_override, setRisk] = useState("moderate");
  const [message, setMessage] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    const trimmed = wallet_address.trim();
    if (trimmed.startsWith("injvaloper") || trimmed.startsWith("0x")) {
      setMessage(
        "Use inj1... only. injvaloper and 0x from the whale JSON are not valid watchlist addresses."
      );
      return;
    }
    setMessage("Submitting...");
    const res = await fetch(`${API_BASE}/api/v1/watchlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        wallet_address: trimmed,
        alias,
        risk_category_override,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      setMessage(typeof data.detail === "string" ? data.detail : "Failed to add wallet.");
      return;
    }
    setMessage(`Tracking enabled for ${data.data.wallet_address}`);
    setAddress("");
    setAlias("");
    onAdded();
  }

  async function importWhales() {
    setMessage("Importing inj1 whales from seed file...");
    const res = await fetch(`${API_BASE}/api/v1/watchlist/import-whales`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit: 25, min_inj_staked: 500 }),
    });
    const data = await res.json();
    if (!res.ok) {
      setMessage(typeof data.detail === "string" ? data.detail : "Import failed.");
      return;
    }
    setMessage(`Imported ${data.imported} inj1 whales (${data.skipped} skipped).`);
    onAdded();
  }

  async function importActiveTraders() {
    setMessage("Importing active Helix traders (multi-asset perps)...");
    const res = await fetch(`${API_BASE}/api/v1/watchlist/import-active-traders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit: 30 }),
    });
    const data = await res.json();
    if (!res.ok) {
      setMessage(typeof data.detail === "string" ? data.detail : "Import failed.");
      return;
    }
    setMessage(
      `Imported ${data.imported} active traders. Backfill queued for new + existing.`
    );
    onAdded();
  }

  return (
    <form onSubmit={submit}>
      <h3>Add whale wallet</h3>
      <p style={{ fontSize: 12, opacity: 0.75 }}>
        Only <strong>inj1...</strong> addresses work. Do not paste injvaloper or 0x from the full JSON.
      </p>
      <input
        placeholder="inj1... (not injvaloper or 0x)"
        value={wallet_address}
        onChange={(e) => setAddress(e.target.value)}
        required
      />
      <input placeholder="Alias (optional)" value={alias} onChange={(e) => setAlias(e.target.value)} />
      <input
        placeholder="Risk category (conservative/moderate/aggressive)"
        value={risk_category_override}
        onChange={(e) => setRisk(e.target.value)}
      />
      <button type="submit">Add to watchlist</button>
      <details style={{ marginTop: 8, fontSize: 12, opacity: 0.8 }}>
        <summary>Legacy seed imports (stakers — low copy signal)</summary>
        <button type="button" onClick={importWhales} style={{ marginTop: 8, display: "block" }}>
          Import top 25 INJ stakers (delegators, not traders)
        </button>
        <button type="button" onClick={importActiveTraders} style={{ marginTop: 8, display: "block" }}>
          Import from static JSON snapshot
        </button>
      </details>
      <WhaleDiscoveryPanel onImported={onAdded} />
      <p>{message}</p>
    </form>
  );
}
