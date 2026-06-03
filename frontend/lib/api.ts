/** Production API — override with .env.local for local backend. */
const PRODUCTION_API = "https://podium-finance.onrender.com";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.trim() || PRODUCTION_API;

function deriveWsBase(apiBase: string): string {
  const explicit = process.env.NEXT_PUBLIC_WS_BASE?.trim();
  if (explicit) return explicit;
  return apiBase.replace(/^https:/i, "wss:").replace(/^http:/i, "ws:");
}

export const WS_BASE = deriveWsBase(API_BASE);

export const EXPLORER_ACCOUNT_URL = (address: string) =>
  `https://explorer.injective.network/account/${address}`;
