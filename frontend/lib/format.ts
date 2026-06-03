const INJ1_REGEX = /^inj1[a-z0-9]{38}$/;

export function validateWalletAddress(addr: string): string | null {
  const trimmed = addr.trim();
  if (!trimmed) return "Address is required.";
  if (trimmed.startsWith("injvaloper"))
    return "This is a validator address, not a trader wallet.";
  if (trimmed.startsWith("0x"))
    return "EVM addresses are not supported — use bech32 inj1… format.";
  if (!INJ1_REGEX.test(trimmed))
    return "Use a valid inj1… address (42 characters).";
  return null;
}

export function truncateAddress(addr: string, start = 6, end = 4): string {
  if (addr.length <= start + end + 3) return addr;
  return `${addr.slice(0, start)}…${addr.slice(-end)}`;
}

export function formatUsd(
  n: number | null | undefined,
  opts?: { compact?: boolean; adjusted?: boolean }
): string {
  if (n == null || Number.isNaN(n)) return "—";
  let base: string;
  if (opts?.compact && Math.abs(n) >= 1_000_000)
    base = `$${(n / 1_000_000).toFixed(2)}M`;
  else if (opts?.compact && Math.abs(n) >= 10_000)
    base = `$${(n / 1_000).toFixed(1)}K`;
  else base = `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  return opts?.adjusted ? `~${base}` : base;
}

export function formatPrice(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1000) return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  if (n >= 1) return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  return `$${n.toFixed(4)}`;
}

export function relativeTime(iso: string): string {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return "—";
  const sec = Math.floor((Date.now() - ts) / 1000);
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h`;
  return `${Math.floor(sec / 86400)}d`;
}

export function absoluteTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export type SideKind = "long" | "short" | "neutral" | "swap" | "transfer";

export function parseSideKind(sideOrType: string): SideKind {
  const s = (sideOrType || "").toUpperCase();
  if (s.includes("LONG") && !s.includes("CLOSE")) return "long";
  if (s.includes("SHORT") && !s.includes("CLOSE")) return "short";
  if (s.includes("LONG_CLOSE") || (s.includes("SELL") && s.includes("CLOSE"))) return "short";
  if (s.includes("SHORT_CLOSE") || (s.includes("BUY") && s.includes("CLOSE"))) return "long";
  if (s.includes("LONG")) return "long";
  if (s.includes("SHORT")) return "short";
  if (s.includes("SWAP")) return "swap";
  if (s.includes("TRANSFER")) return "transfer";
  return "neutral";
}

export function formatSideLabel(sideOrType: string): string {
  const s = (sideOrType || "").replace(/_/g, " ").toUpperCase();
  if (!s || s === "NEUTRAL") return "ACTIVITY";
  return s;
}

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
