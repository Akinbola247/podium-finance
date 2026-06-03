"use client";

import clsx from "clsx";
import { parseSideKind, formatSideLabel } from "../../lib/format";

const STREAM_CONFIG = {
  live: { label: "LIVE", dot: "bg-long shadow-[0_0_8px_var(--long)]", text: "text-long" },
  connecting: { label: "CONNECTING", dot: "bg-warning animate-pulse", text: "text-warning" },
  reconnecting: { label: "RECONNECTING", dot: "bg-warning animate-pulse", text: "text-warning" },
  offline: { label: "OFFLINE", dot: "bg-short", text: "text-short" },
} as const;

export function StreamStatusPill({ status }: { status: string }) {
  const config =
    STREAM_CONFIG[status as keyof typeof STREAM_CONFIG] ?? STREAM_CONFIG.offline;

  return (
    <span
      className={clsx(
        "inline-flex h-6 items-center gap-1.5 rounded-full border border-border px-2.5 font-mono text-[10px] font-semibold tracking-wider",
        config.text
      )}
    >
      <span className={clsx("h-2 w-2 rounded-full", config.dot, status === "live" && "animate-pulse-ring")} />
      {config.label}
    </span>
  );
}

export function SideBadge({ side }: { side: string }) {
  const kind = parseSideKind(side);
  const label = formatSideLabel(side);
  const styles = {
    long: "bg-long-muted text-long border-long/30",
    short: "bg-short-muted text-short border-short/30",
    swap: "bg-accent-glow/10 text-accent-glow border-accent-glow/30",
    transfer: "bg-neutral/20 text-text-secondary border-border",
    neutral: "bg-bg-card-hover text-text-secondary border-border",
  }[kind];

  return (
    <span
      className={clsx(
        "inline-flex h-6 max-w-[120px] items-center truncate rounded-full border px-2 font-mono text-[10px] font-semibold tracking-wide",
        styles
      )}
      title={label}
    >
      {label}
    </span>
  );
}

export function TierBadge({ tier }: { tier: string }) {
  const t = tier.toUpperCase();
  const styles: Record<string, string> = {
    A: "bg-tier-a text-white border-tier-a",
    B: "border-tier-b text-tier-b bg-tier-b/10",
    C: "border-tier-c text-tier-c bg-transparent",
    D: "border-tier-d text-tier-d bg-transparent",
  };
  return (
    <span
      className={clsx(
        "inline-flex h-5 min-w-[22px] items-center justify-center rounded border px-1.5 font-mono text-[10px] font-bold",
        styles[t] ?? styles.D
      )}
      title={
        t === "A"
          ? "Tier A — heaviest multi-fill Helix flow"
          : t === "D"
            ? "Tier D — borderline active"
            : `Tier ${t}`
      }
    >
      {t}
    </span>
  );
}

export function AiChip({ rulesOnly }: { rulesOnly?: boolean }) {
  if (rulesOnly) {
    return (
      <span className="rounded px-1 font-mono text-[9px] text-text-muted">Rules-based</span>
    );
  }
  return (
    <span
      className="rounded bg-ai/15 px-1 font-mono text-[9px] font-semibold text-ai"
      title="AI-generated summary — may contain errors. Verify on-chain."
    >
      AI
    </span>
  );
}

const RISK_COLORS = {
  conservative: "border-accent-primary text-accent-glow",
  moderate: "border-warning text-warning",
  aggressive: "border-short text-short",
} as const;

export function RiskBadge({ risk }: { risk?: string | null }) {
  const r = (risk || "moderate").toLowerCase();
  const colors =
    RISK_COLORS[r as keyof typeof RISK_COLORS] ?? RISK_COLORS.moderate;
  return (
    <span className={clsx("rounded border px-1.5 font-mono text-[9px] uppercase", colors)}>
      {r}
    </span>
  );
}

export function BiasBadge({ bias }: { bias?: string }) {
  const b = (bias || "NEUTRAL").toUpperCase();
  if (b === "ACCUMULATING")
    return <span className="font-mono text-xs text-long">↑ ACCUMULATING</span>;
  if (b === "DISTRIBUTING")
    return <span className="font-mono text-xs text-short">↓ DISTRIBUTING</span>;
  return <span className="font-mono text-xs text-text-muted">→ NEUTRAL</span>;
}
