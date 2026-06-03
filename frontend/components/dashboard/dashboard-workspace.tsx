"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useDashboard } from "../../hooks/use-dashboard";
import { useStream } from "../../context/stream-context";
import { WatchlistSidebar } from "../watchlist/watchlist-sidebar";
import { AddWalletForm } from "../watchlist/add-wallet-form";
import { DashboardMetricsRow } from "./dashboard-metrics-row";
import { LiveAlertsStrip } from "../feed/live-alerts-strip";
import { ActivityFeed } from "../feed/activity-feed";
import { BlueprintPanel } from "../blueprint/blueprint-panel";

export function DashboardWorkspace() {
  const searchParams = useSearchParams();
  const [selectedAddress, setSelectedAddress] = useState("");
  const [selectedEventId, setSelectedEventId] = useState("");
  const [blueprintOpen, setBlueprintOpen] = useState(false);

  const {
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
  } = useDashboard(selectedAddress);

  const { liveAlerts } = useStream();

  useEffect(() => {
    const wallet = searchParams.get("wallet");
    if (wallet) setSelectedAddress(wallet);
  }, [searchParams]);

  useEffect(() => {
    if (!selectedAddress && watchlist.length > 0) {
      setSelectedAddress(watchlist[0].wallet_address);
    }
  }, [watchlist, selectedAddress]);

  useEffect(() => {
    if (activities.length && !selectedEventId) {
      setSelectedEventId(activities[0].event_id);
    }
  }, [activities, selectedEventId]);

  function handleWhaleChange(addr: string) {
    setSelectedAddress(addr);
    setSelectedEventId("");
    setBlueprintOpen(false);
  }

  function handleEventSelect(id: string) {
    setSelectedEventId(id);
    setBlueprintOpen(true);
  }

  const selectedEvent = activities.find((a) => a.event_id === selectedEventId);

  return (
    <div className="dashboard-layout">
      <aside className="dashboard-sidebar hidden lg:flex lg:flex-col">
        <section className="dashboard-sidebar-panel panel p-3">
          <h3 className="mb-2 shrink-0 font-mono text-[10px] font-semibold tracking-[0.15em] text-text-secondary">
            WATCHED WALLETS ({watchlist.length})
          </h3>
          <div className="watchlist-scroll min-h-0 flex-1">
            <WatchlistSidebar
              watchlist={watchlist}
              selectedAddress={selectedAddress}
              onSelect={handleWhaleChange}
            />
          </div>
          <div className="mt-3 shrink-0 border-t border-border pt-3">
            <AddWalletForm
              compact
              onAdded={() => {
                loadWatchlist();
                loadActivities();
              }}
            />
          </div>
        </section>
      </aside>

      <main className="dashboard-main flex min-h-0 flex-1 flex-col">
        <LiveAlertsStrip
          alerts={liveAlerts}
          streamStatus={streamStatus}
          onAlertClick={(id) => {
            const row = activities.find((a) => a.event_id === id);
            if (row) {
              setSelectedAddress(row.wallet_address);
              handleEventSelect(id);
            } else {
              handleEventSelect(id);
            }
          }}
        />
        <DashboardMetricsRow
          profile={profile}
          selectedAddress={selectedAddress}
          watchlist={watchlist}
        />
        <ActivityFeed
          activities={activities}
          watchlist={watchlist}
          selectedEventId={selectedEventId}
          flashIds={flashIds}
          loadError={loadError}
          lastUpdated={lastUpdated}
          streamStatus={streamStatus}
          onSelectEvent={handleEventSelect}
          walletFilter={selectedAddress}
          onWalletFilterChange={handleWhaleChange}
          wallets={wallets}
        />
      </main>

      <BlueprintPanel
        open={blueprintOpen && !!selectedEventId}
        onClose={() => setBlueprintOpen(false)}
        selectedEvent={selectedEvent}
        selectedEventId={selectedEventId}
      />
    </div>
  );
}
