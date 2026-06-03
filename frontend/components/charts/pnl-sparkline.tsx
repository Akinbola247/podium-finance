"use client";

import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";

type FillPoint = {
  timestamp: string;
  realized_pnl_usd?: number | null;
  notional_usd?: number;
};

export function PnlSparkline({
  fills,
  title = "Recent fill P&L",
}: {
  fills: FillPoint[];
  title?: string;
}) {
  const data = fills
    .slice(-12)
    .map((f, i) => ({
      i: i + 1,
      pnl: f.realized_pnl_usd ?? 0,
      label: new Date(f.timestamp).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      }),
    }))
    .filter((d) => d.pnl !== 0 || fills.length <= 3);

  if (data.length === 0) {
    return (
      <div className="flex h-full min-h-0 flex-1 items-center justify-center font-mono text-[10px] text-text-muted">
        P&L bars appear after matched closes
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 w-full min-w-0 flex-col overflow-hidden">
      <p className="mb-1 shrink-0 font-mono text-[9px] uppercase tracking-wider text-text-muted">
        {title}
      </p>
      <div className="min-h-0 flex-1">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
          <XAxis dataKey="label" tick={{ fontSize: 8, fill: "#4b5563" }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{
              background: "#0c0f1c",
              border: "1px solid #1a2035",
              borderRadius: 6,
              fontSize: 10,
              fontFamily: "monospace",
            }}
            formatter={(v) => [`$${Number(v).toLocaleString()}`, "P&L"]}
          />
          <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.pnl >= 0 ? "#00e676" : "#ff4d6d"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      </div>
    </div>
  );
}
