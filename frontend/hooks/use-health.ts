"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";

export type HealthInfo = {
  data_source?: string;
  stored_activities?: number;
  watched_wallets?: number;
  redis?: boolean;
};

export function useHealth(pollMs = 60_000) {
  const [health, setHealth] = useState<HealthInfo | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/health`);
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) setHealth(data);
      } catch {
        if (!cancelled) setHealth(null);
      }
    }
    load();
    const id = setInterval(load, pollMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [pollMs]);

  return health;
}
