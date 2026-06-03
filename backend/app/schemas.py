from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WatchlistCreate(BaseModel):
    wallet_address: str = Field(..., min_length=10, max_length=64)
    alias: str | None = Field(default=None, max_length=128)
    risk_category_override: Literal["conservative", "moderate", "aggressive"] | None = None


class WatchlistCreateResponse(BaseModel):
    status: str
    data: dict


class WatchlistBulkImport(BaseModel):
    limit: int = Field(default=20, ge=1, le=200)
    min_inj_staked: float = Field(default=500.0, ge=0)


class ActiveTradersImport(BaseModel):
    limit: int = Field(default=30, ge=1, le=100)


class WhaleDiscoverRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=150)
    scan_pages: int = Field(default=40, ge=5, le=50)
    page_size: int = Field(default=80, ge=20, le=80)
    min_notional_usd: float = Field(
        default=50,
        ge=25,
        description="Minimum USD per Helix fill (filters dust).",
    )
    min_exchange_events: int = Field(default=2, ge=1, le=20)
    min_exchange_volume_usd: float = Field(default=300, ge=100)
    min_largest_clip_usd: float = Field(default=75, ge=25)
    prefer_multi_asset: bool = True
    exclude_watchlist: bool = True


class WhaleDiscoverImportRequest(BaseModel):
    search_id: str = Field(..., min_length=8)
    limit: int = Field(default=100, ge=1, le=150)
    addresses: list[str] | None = None


class WhaleProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    address: str
    alias: str | None
    metrics: dict
    portfolio_distribution: list[dict]
    updated_at: datetime


class ActivityItem(BaseModel):
    event_id: str
    wallet_address: str
    timestamp: datetime
    activity_type: str
    asset_affected: str
    notional_value_usd: float
    notional_adjusted: bool = False
    raw_payload_summary: dict
    ai_interpretation: str | None = None
    fill_price_usd: float | None = None
    execution_side: str | None = None
    realized_pnl_usd: float | None = None
    unrealized_pnl_usd: float | None = None
    pnl_kind: str | None = None


class RiskExecutionPlanRequest(BaseModel):
    whale_event_id: str
    user_portfolio_usd: float = Field(..., gt=0)
    max_drawdown_tolerance_percent: float = Field(..., gt=0, le=100)
    leverage_cap: float = Field(..., gt=0)


class RiskExecutionPlanResponse(BaseModel):
    execution_blueprint: dict
