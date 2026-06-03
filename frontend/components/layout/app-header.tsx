"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { StreamStatusPill } from "../ui/badges";
import { useStream } from "../../context/stream-context";
import { useHealth } from "../../hooks/use-health";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/discover", label: "Discover" },
  { href: "/watchlist", label: "Watchlist" },
];

function PodiumIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden>
      <rect x="4" y="16" width="5" height="8" rx="1" fill="#3b82f6" />
      <rect x="11.5" y="10" width="5" height="14" rx="1" fill="#1a56db" />
      <rect x="19" y="4" width="5" height="20" rx="1" fill="#00e676" />
    </svg>
  );
}

export function AppHeader() {
  const pathname = usePathname();
  const { streamStatus } = useStream();
  const health = useHealth();
  const isLiveData = health?.data_source === "injective_explorer_live";

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-bg-base/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1600px] items-center justify-between gap-4 px-4 lg:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2.5">
          <PodiumIcon />
          <span className="font-display text-lg font-bold tracking-tight text-text-primary">
            PODIUM
            <sup className="ml-0.5 text-[9px] font-normal tracking-widest text-text-secondary">
              FINANCE
            </sup>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "rounded-md px-3 py-1.5 font-mono text-xs tracking-wide transition-colors",
                pathname === item.href
                  ? "bg-accent-primary/20 text-accent-glow"
                  : "text-text-secondary hover:bg-bg-card-hover hover:text-text-primary"
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <div className="hidden flex-col items-end sm:flex">
            <span className="font-mono text-[10px] text-text-secondary">Injective Mainnet</span>
            <span
              className={`font-mono text-[9px] ${isLiveData ? "text-long" : "text-text-muted"}`}
              title={
                isLiveData
                  ? `${health?.stored_activities ?? 0} activities ingested from explorer`
                  : "Backend health unavailable"
              }
            >
              {isLiveData ? "● Live explorer data" : "Explorer API"}
            </span>
          </div>
          <StreamStatusPill status={streamStatus} />
        </div>
      </div>

      <nav className="flex gap-1 border-t border-border-subtle px-4 py-1 md:hidden">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={clsx(
              "flex-1 rounded py-1.5 text-center font-mono text-[10px]",
              pathname === item.href ? "text-accent-glow" : "text-text-muted"
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
