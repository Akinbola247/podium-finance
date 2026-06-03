"use client";

import { FormEvent, useState } from "react";
import clsx from "clsx";
import { API_BASE } from "../../lib/api";
import { validateWalletAddress } from "../../lib/format";
import type { RiskCategory } from "../../lib/types";

export function AddWalletForm({
  onAdded,
  compact,
}: {
  onAdded: () => void;
  compact?: boolean;
}) {
  const [wallet_address, setAddress] = useState("");
  const [alias, setAlias] = useState("");
  const [risk, setRisk] = useState<RiskCategory>("moderate");
  const [expanded, setExpanded] = useState(!compact);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const validationError = wallet_address.trim()
    ? validateWalletAddress(wallet_address)
    : null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    const err = validateWalletAddress(wallet_address);
    if (err) {
      setError(err);
      return;
    }
    setLoading(true);
    setError("");
    setMessage("Submitting…");
    try {
      const res = await fetch(`${API_BASE}/api/v1/watchlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          wallet_address: wallet_address.trim(),
          alias: alias.trim() || null,
          risk_category_override: risk,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(typeof data.detail === "string" ? data.detail : "Failed to add wallet.");
        setMessage("");
        return;
      }
      setMessage(
        `Added to watchlist — live backfill from Injective explorer queued for ${data.data?.wallet_address?.slice(0, 12) ?? "wallet"}…`
      );
      setAddress("");
      setAlias("");
      onAdded();
    } catch {
      setError("Cannot reach API.");
      setMessage("");
    } finally {
      setLoading(false);
    }
  }

  if (compact && !expanded) {
    return (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        className="w-full rounded-md border border-dashed border-border py-2 font-mono text-[10px] text-text-secondary hover:border-accent-glow hover:text-accent-glow"
      >
        + Track wallet
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      <div>
        <input
          className={clsx("input-field", validationError && wallet_address && "border-short")}
          placeholder="inj1…"
          value={wallet_address}
          onChange={(e) => {
            setAddress(e.target.value);
            setError("");
          }}
          required
        />
        {validationError && wallet_address.trim() && (
          <p className="mt-1 font-mono text-[10px] text-short">{validationError}</p>
        )}
      </div>
      <input
        className="input-field"
        placeholder="Alias (optional)"
        value={alias}
        onChange={(e) => setAlias(e.target.value)}
      />
      <select
        className="input-field"
        value={risk}
        onChange={(e) => setRisk(e.target.value as RiskCategory)}
      >
        <option value="conservative">Conservative</option>
        <option value="moderate">Moderate</option>
        <option value="aggressive">Aggressive</option>
      </select>
      <button type="submit" className="btn-primary w-full" disabled={loading || !!validationError}>
        {loading ? "…" : "Track Wallet"}
      </button>
      {message && !error && (
        <p className="font-mono text-[10px] text-long">{message}</p>
      )}
      {error && <p className="font-mono text-[10px] text-short">{error}</p>}
    </form>
  );
}
