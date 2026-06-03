export type Activity = {
  event_id: string;
  wallet_address: string;
  timestamp: string;
  activity_type: string;
  asset_affected: string;
  notional_value_usd: number;
  notional_adjusted?: boolean;
  ai_interpretation?: string;
  fill_price_usd?: number | null;
  execution_side?: string | null;
  realized_pnl_usd?: number | null;
  unrealized_pnl_usd?: number | null;
  pnl_kind?: string | null;
};

export type WatchlistItem = {
  wallet_address: string;
  alias: string | null;
  risk_category_override?: string | null;
  conviction_score?: number;
};

export type LiveAlert = {
  type: string;
  event_id: string;
  wallet_address: string;
  timestamp: string;
  activity_type: string;
  asset_affected: string;
  notional_value_usd: number;
  ai_interpretation?: string;
  alert_passed?: boolean;
};

export type StreamStatus = "connecting" | "live" | "reconnecting" | "offline";

export type RiskCategory = "conservative" | "moderate" | "aggressive";

export type DiscoveredWhale = {
  address: string;
  label: string;
  score: number;
  copyability_tier: string;
  exchange_events_sampled: number;
  exchange_volume_usd: number;
  median_clip_usd: number;
  largest_clip_usd: number;
  volume_usd_sampled: number;
  asset_count: number;
  non_inj_asset_count: number;
  top_assets: string[];
  assets_seen: Record<string, number>;
};
