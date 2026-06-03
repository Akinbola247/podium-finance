"use client";

export function ConvictionGauge({ score, size = "md" }: { score: number; size?: "sm" | "md" }) {
  const clamped = Math.max(0, Math.min(100, score));
  const radius = size === "sm" ? 40 : 52;
  const stroke = size === "sm" ? 6 : 8;
  const box = size === "sm" ? 100 : 140;
  const fontSize = size === "sm" ? "text-xl" : "text-3xl";
  const circumference = 2 * Math.PI * radius;
  const arcLength = circumference * 0.75;
  const offset = arcLength - (clamped / 100) * arcLength;

  const color =
    clamped >= 65 ? "#00e676" : clamped >= 40 ? "#fbbf24" : "#ff4d6d";

  return (
    <div className="relative mx-auto" style={{ height: box, width: box }}>
      <svg viewBox="0 0 140 140" className="h-full w-full -rotate-[135deg]">
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke="#1a2035"
          strokeWidth={stroke}
          strokeDasharray={`${arcLength} ${circumference}`}
          strokeLinecap="round"
        />
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeDasharray={`${arcLength} ${circumference}`}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.6s ease, stroke 0.4s" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`font-mono font-bold text-text-primary ${fontSize}`}>{Math.round(clamped)}</span>
        <span className="font-mono text-[9px] tracking-[0.2em] text-text-secondary">CONVICTION</span>
      </div>
    </div>
  );
}
