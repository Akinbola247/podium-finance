"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";
import { API_BASE } from "../../lib/api";
import type { Activity } from "../../lib/types";
import { formatUsd, formatPrice, absoluteTime } from "../../lib/format";
import { SideBadge, AiChip } from "../ui/badges";

export function BlueprintPanel({
  open,
  onClose,
  selectedEvent,
  selectedEventId,
}: {
  open: boolean;
  onClose: () => void;
  selectedEvent: Activity | undefined;
  selectedEventId: string;
}) {
  const [portfolioUsd, setPortfolioUsd] = useState("10000");
  const [drawdownPct, setDrawdownPct] = useState("5");
  const [plan, setPlan] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setPlan(null);
  }, [selectedEventId]);

  async function generatePlan() {
    if (!selectedEventId) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/risk/execution-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          whale_event_id: selectedEventId,
          user_portfolio_usd: Number(portfolioUsd) || 10000,
          max_drawdown_tolerance_percent: Number(drawdownPct) || 5,
          leverage_cap: 1,
        }),
      });
      setPlan(await res.json());
    } finally {
      setLoading(false);
    }
  }

  const bp = plan?.execution_blueprint;
  const isWatch = bp?.execution_mode === "WATCH";

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.5 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black"
            onClick={onClose}
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-[480px] flex-col border-l border-border bg-bg-panel shadow-2xl"
          >
            <header className="flex items-center justify-between border-b border-border px-4 py-3">
              <div>
                <h2 className="font-mono text-xs font-semibold tracking-[0.15em] text-text-primary">
                  EXECUTION BLUEPRINT
                </h2>
                {selectedEvent && (
                  <p className="mt-1 flex flex-wrap items-center gap-2 font-mono text-[10px] text-text-secondary">
                    <SideBadge side={selectedEvent.execution_side || selectedEvent.activity_type} />
                    {selectedEvent.asset_affected} · {formatUsd(selectedEvent.notional_value_usd)}
                    · {absoluteTime(selectedEvent.timestamp)}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-border px-2 py-1 font-mono text-lg text-text-secondary hover:text-text-primary"
                aria-label="Close"
              >
                ×
              </button>
            </header>

            <div className="flex-1 overflow-y-auto px-4 py-4">
              <div className="disclaimer-block mb-4">
                Educational analytics only. Not financial advice. Risk-bounded sizing for
                learning purposes only.
              </div>

              <div className="space-y-3">
                <label className="block">
                  <span className="font-mono text-[10px] text-text-muted">Portfolio USD</span>
                  <div className="relative mt-1">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 font-mono text-text-muted">
                      $
                    </span>
                    <input
                      className="input-field !pl-7"
                      value={portfolioUsd}
                      onChange={(e) => setPortfolioUsd(e.target.value)}
                    />
                  </div>
                </label>
                <label className="block">
                  <span className="font-mono text-[10px] text-text-muted">
                    Max drawdown % ({drawdownPct}%)
                  </span>
                  <input
                    type="range"
                    min={1}
                    max={20}
                    value={drawdownPct}
                    onChange={(e) => setDrawdownPct(e.target.value)}
                    className="mt-2 w-full accent-accent-primary"
                  />
                  <input
                    className="input-field mt-1"
                    value={drawdownPct}
                    onChange={(e) => setDrawdownPct(e.target.value)}
                  />
                </label>
                <button
                  type="button"
                  className="btn-primary w-full"
                  disabled={!selectedEventId || loading}
                  onClick={generatePlan}
                >
                  {loading ? "Generating…" : "Generate Blueprint"}
                </button>
              </div>

              {!bp && selectedEventId && (
                <p className="mt-4 font-mono text-[10px] text-text-muted">
                  Event {selectedEventId.slice(0, 8)}… — generate to see risk-bounded sizing.
                </p>
              )}

              {bp && (
                <div className="mt-6 space-y-4">
                  <div
                    className={clsx(
                      "rounded-lg border p-4",
                      isWatch
                        ? "border-warning/50 bg-warning/5"
                        : "border-accent-glow/40 bg-accent-primary/10"
                    )}
                  >
                    <p className="font-mono text-lg font-bold text-text-primary">
                      {bp.execution_mode || "EXECUTE"}
                    </p>
                    <p className="mt-1 font-mono text-sm text-text-secondary">
                      {bp.action} · {bp.target_asset}
                    </p>
                    {isWatch ? (
                      <p className="mt-2 font-mono text-base text-text-primary">
                        $0 recommended — monitor only
                        {bp.hypothetical_allocation_usd != null && (
                          <span className="mt-1 block text-sm italic text-text-muted">
                            (hypothetical) {formatUsd(bp.hypothetical_allocation_usd)}
                          </span>
                        )}
                      </p>
                    ) : (
                      <p className="mt-2 font-mono text-xl font-bold text-long">
                        {formatUsd(bp.recommended_allocation_usd)}
                        <span className="ml-2 text-sm font-normal text-text-secondary">
                          ({bp.percentage_of_user_portfolio}% of portfolio)
                        </span>
                      </p>
                    )}
                  </div>

                  {bp.quant_metrics && (
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        ["Whale fill", bp.quant_metrics.whale_fill_price_usd],
                        ["Entry", bp.quant_metrics.whale_entry_price_usd],
                        ["Exit", bp.quant_metrics.whale_exit_price_usd],
                        ["Event P&L", bp.quant_metrics.event_realized_pnl_usd],
                        ["30d P&L", bp.quant_metrics.wallet_combined_pnl_30d_usd],
                        ["Win rate", bp.quant_metrics.wallet_win_rate_30d_pct],
                      ].map(([label, val]) => (
                        <div key={String(label)} className="rounded border border-border bg-bg-card p-2">
                          <p className="font-mono text-[9px] text-text-muted">{label}</p>
                          <p className="font-mono text-xs font-semibold text-text-primary">
                            {label === "Win rate"
                              ? val != null
                                ? `${val}%`
                                : "—"
                              : typeof val === "number"
                                ? formatPrice(val)
                                : "—"}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}

                  {bp.trade_conclusion && (
                    <div className="rounded-lg border border-border bg-bg-card p-3">
                      <div className="mb-2 flex items-center gap-2">
                        <strong className="font-mono text-xs">Trade conclusion</strong>
                        <AiChip rulesOnly />
                      </div>
                      <div className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary">
                        {bp.trade_conclusion.split(/\*\*/).map((part: string, i: number) =>
                          i % 2 === 1 ? (
                            <strong key={i} className="text-text-primary">
                              {part}
                            </strong>
                          ) : (
                            <span key={i}>{part}</span>
                          )
                        )}
                      </div>
                    </div>
                  )}

                  {bp.sizing_rationale && (
                    <details className="rounded border border-border">
                      <summary className="cursor-pointer px-3 py-2 font-mono text-[10px] text-text-secondary">
                        Sizing rationale
                      </summary>
                      <p className="px-3 pb-3 text-xs text-text-secondary">{bp.sizing_rationale}</p>
                    </details>
                  )}

                  <details className="rounded border border-border">
                    <summary className="cursor-pointer px-3 py-2 font-mono text-[10px] text-text-muted">
                      Raw data (advanced)
                    </summary>
                    <pre className="max-h-48 overflow-auto p-3 font-mono text-[10px] text-text-muted">
                      {JSON.stringify(bp, null, 2)}
                    </pre>
                  </details>
                </div>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
