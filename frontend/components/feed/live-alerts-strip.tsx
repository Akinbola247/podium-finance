"use client";

import clsx from "clsx";
import { motion } from "framer-motion";
import type { LiveAlert, StreamStatus } from "../../lib/types";
import { SideBadge, AiChip } from "../ui/badges";
import {
  formatUsd,
  truncateAddress,
  relativeTime,
  copyToClipboard,
  parseSideKind,
} from "../../lib/format";

export function LiveAlertsStrip({
  alerts,
  streamStatus,
  onAlertClick,
}: {
  alerts: LiveAlert[];
  streamStatus: StreamStatus;
  onAlertClick?: (eventId: string) => void;
}) {
  if (streamStatus === "reconnecting") {
    return (
      <div className="mb-3 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 font-mono text-xs text-warning">
        WebSocket reconnecting — polling every 20s
      </div>
    );
  }

  if (streamStatus === "offline") {
    return (
      <div className="mb-3 rounded-md border border-short/40 bg-short/10 px-3 py-2 font-mono text-xs text-short">
        Stream offline — last data may be stale
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="mb-3 flex items-center gap-2 rounded-md border border-border bg-bg-panel px-3 py-3">
        <span className="h-2 w-2 animate-pulse rounded-full bg-accent-glow" />
        <span className="font-mono text-xs text-text-secondary">
          {streamStatus === "connecting"
            ? "Connecting to live stream…"
            : "Waiting for sized Helix clips to arrive…"}
        </span>
      </div>
    );
  }

  return (
    <div className="mb-3">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-mono text-[10px] font-semibold tracking-[0.15em] text-text-secondary">
          LIVE ALERTS
        </h3>
        <span className="font-mono text-[10px] text-text-muted">{alerts.length} recent</span>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin">
        {alerts.map((a) => (
          <AlertCard key={a.event_id} alert={a} onClick={() => onAlertClick?.(a.event_id)} />
        ))}
      </div>
    </div>
  );
}

function AlertCard({ alert, onClick }: { alert: LiveAlert; onClick?: () => void }) {
  const side = alert.activity_type || "ACTIVITY";
  const kind = parseSideKind(side);

  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, x: 16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2 }}
      onClick={onClick}
      className={clsx(
        "shrink-0 rounded-lg border border-border bg-bg-card p-3 text-left transition-all",
        "h-[100px] w-[200px] hover:border-accent-glow/50 hover:shadow-[0_0_20px_rgba(59,130,246,0.15)]"
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className={clsx(
            "flex h-7 w-7 items-center justify-center rounded-full font-mono text-xs font-bold",
            kind === "long" ? "bg-long-muted text-long" : kind === "short" ? "bg-short-muted text-short" : "bg-bg-card-hover text-text-secondary"
          )}
        >
          {alert.asset_affected?.slice(0, 2) || "?"}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-xs font-semibold text-text-primary">
            {alert.asset_affected}
          </p>
          <p className="font-mono text-[9px] text-text-muted">{relativeTime(alert.timestamp)} ago</p>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        <SideBadge side={side} />
      </div>
      <p className="mt-1 font-mono text-sm font-bold text-text-primary">
        {formatUsd(alert.notional_value_usd)}
      </p>
      <div className="mt-1 flex items-center gap-1">
        <button
          type="button"
          className="font-mono text-[9px] text-text-muted hover:text-accent-glow"
          onClick={(e) => {
            e.stopPropagation();
            copyToClipboard(alert.wallet_address);
          }}
        >
          {truncateAddress(alert.wallet_address)}
        </button>
        {alert.ai_interpretation && <AiChip />}
      </div>
      {alert.ai_interpretation && (
        <p className="mt-1 line-clamp-1 font-mono text-[9px] text-text-secondary">
          {alert.ai_interpretation}
        </p>
      )}
    </motion.button>
  );
}
