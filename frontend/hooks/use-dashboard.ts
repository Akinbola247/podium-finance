"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE } from "../lib/api";
import type { Activity, WatchlistItem } from "../lib/types";
import { useStream } from "../context/stream-context";

export function useDashboard(selectedAddress: string) {
  const { streamStatus, onLiveMessage, refreshAlerts } = useStream();
  const [activities, setActivities] = useState<Activity[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [profile, setProfile] = useState<any>(null);
  const [loadError, setLoadError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [flashIds, setFlashIds] = useState<Set<string>>(new Set());

  const flashRow = useCallback((eventId: string) => {
    setFlashIds((prev) => new Set(prev).add(eventId));
    setTimeout(() => {
      setFlashIds((prev) => {
        const next = new Set(prev);
        next.delete(eventId);
        return next;
      });
    }, 320);
  }, []);

  const loadWatchlist = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/watchlist`);
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) setWatchlist(data);
    } catch {
      /* optional */
    }
  }, []);

  const loadActivities = useCallback(async () => {
    setLoadError("");
    try {
      const params = new URLSearchParams({ limit: "50" });
      if (selectedAddress) params.set("wallet_address", selectedAddress);
      const res = await fetch(`${API_BASE}/api/v1/whales/activity?${params.toString()}`);
      const data = await res.json();
      if (!res.ok) {
        setActivities([]);
        setLoadError(
          typeof data?.detail === "string"
            ? data.detail
            : `Failed to load activity feed (${res.status}). Is the backend running on ${API_BASE}?`
        );
        return;
      }
      const list: Activity[] = Array.isArray(data) ? data : [];
      setActivities(list);
      setLastUpdated(new Date());
      if (!list.length) {
        setLoadError(
          "No on-chain activity stored yet. Add a wallet to the watchlist and ensure the stream worker is running."
        );
      }
    } catch {
      setActivities([]);
      setLoadError(
        `Cannot reach API at ${API_BASE}. Start backend + Redis + worker (see README).`
      );
    }
  }, [selectedAddress]);

  useEffect(() => {
    loadWatchlist();
    loadActivities();
  }, [loadWatchlist, loadActivities]);

  useEffect(() => {
    return onLiveMessage((payload) => {
      if (payload.type === "backfill_complete") {
        loadActivities();
        refreshAlerts();
        return;
      }
      if (payload.type === "bootstrap_complete" || !payload.event_id) return;

      const row: Activity = {
        event_id: payload.event_id,
        wallet_address: payload.wallet_address,
        timestamp: payload.timestamp,
        activity_type: payload.activity_type,
        asset_affected: payload.asset_affected,
        notional_value_usd: payload.notional_value_usd,
        ai_interpretation: payload.ai_interpretation,
      };

      const matchesWallet = !selectedAddress || payload.wallet_address === selectedAddress;
      if (matchesWallet) {
        setActivities((prev) => {
          if (prev.some((p) => p.event_id === row.event_id)) return prev;
          flashRow(row.event_id);
          return [row, ...prev].slice(0, 100);
        });
        setLastUpdated(new Date());
      }
      setLoadError("");
    });
  }, [onLiveMessage, selectedAddress, loadActivities, refreshAlerts, flashRow]);

  useEffect(() => {
    const poll = setInterval(() => {
      loadActivities();
      if (streamStatus === "live" || streamStatus === "reconnecting") refreshAlerts();
    }, 20000);
    return () => clearInterval(poll);
  }, [loadActivities, refreshAlerts, streamStatus]);

  useEffect(() => {
    if (!selectedAddress) {
      setProfile(null);
      return;
    }
    (async () => {
      const res = await fetch(`${API_BASE}/api/v1/whales/profile/${selectedAddress}`);
      if (!res.ok) return;
      setProfile(await res.json());
    })();
  }, [selectedAddress, activities.length]);

  const wallets = useMemo(() => {
    const fromWatchlist = watchlist.map((w) => w.wallet_address);
    const fromActivity = activities.map((a) => a.wallet_address);
    return Array.from(new Set([...fromWatchlist, ...fromActivity]));
  }, [watchlist, activities]);

  return {
    activities,
    watchlist,
    profile,
    loadError,
    lastUpdated,
    flashIds,
    wallets,
    streamStatus,
    loadWatchlist,
    loadActivities,
  };
}
