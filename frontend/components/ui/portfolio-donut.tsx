"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

const COLORS = ["#3b82f6", "#00e676", "#a78bfa", "#fbbf24", "#ff4d6d", "#6b7280"];

export function PortfolioDonut({
  distribution,
  compact = false,
}: {
  distribution: { asset: string; percentage: number }[];
  compact?: boolean;
}) {
  if (!distribution?.length) return null;
  const data = distribution.slice(0, 5).map((d) => ({
    name: d.asset,
    value: Math.round(d.percentage * 100),
  }));
  const other = distribution.slice(5).reduce((s, d) => s + d.percentage, 0);
  if (other > 0) data.push({ name: "Other", value: Math.round(other * 100) });

  if (compact) {
    return (
      <div className="flex h-full min-h-0 w-full min-w-0 items-center gap-2 overflow-hidden">
        <div className="h-[72px] w-[72px] shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                innerRadius={22}
                outerRadius={34}
                paddingAngle={2}
                dataKey="value"
                stroke="none"
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "#0c0f1c",
                  border: "1px solid #1a2035",
                  borderRadius: 6,
                  fontSize: 10,
                  fontFamily: "monospace",
                }}
                formatter={(v) => [`${v}%`, "Share"]}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <ul className="metrics-donut-legend min-h-0 min-w-0 flex-1 space-y-0.5 overflow-y-auto pr-0.5">
          {data.map((d, i) => (
            <li
              key={d.name}
              className="flex items-center gap-1.5 font-mono text-[9px] leading-tight text-text-secondary"
            >
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ background: COLORS[i % COLORS.length] }}
              />
              <span className="truncate">
                {d.name} <span className="text-text-muted">{d.value}%</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className="w-full">
      <div className="h-[88px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              innerRadius={28}
              outerRadius={42}
              paddingAngle={2}
              dataKey="value"
              stroke="none"
            >
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "#0c0f1c",
                border: "1px solid #1a2035",
                borderRadius: 6,
                fontSize: 11,
                fontFamily: "monospace",
              }}
              formatter={(v) => [`${v}%`, "Share"]}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-2 gap-y-1">
        {data.map((d, i) => (
          <span
            key={d.name}
            className="flex items-center gap-1 font-mono text-[10px] text-text-secondary"
          >
            <span
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ background: COLORS[i % COLORS.length] }}
            />
            {d.name} {d.value}%
          </span>
        ))}
      </div>
    </div>
  );
}
