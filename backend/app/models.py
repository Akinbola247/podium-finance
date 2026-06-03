import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ActivityType(str, enum.Enum):
    SWAP = "SWAP"
    LIQUIDITY_PROVISION = "LIQUIDITY_PROVISION"
    MARGIN_POSITION_OPEN = "MARGIN_POSITION_OPEN"
    MARGIN_POSITION_CLOSE = "MARGIN_POSITION_CLOSE"
    LARGE_TRANSFER = "LARGE_TRANSFER"


class WatchedWallet(Base):
    __tablename__ = "watched_wallets"

    wallet_address: Mapped[str] = mapped_column(String(64), primary_key=True)
    alias: Mapped[str | None] = mapped_column(String(128), nullable=True)
    risk_category_override: Mapped[str | None] = mapped_column(String(16), nullable=True)
    conviction_score: Mapped[float] = mapped_column(Float, default=0.0)
    strategy_fingerprint: Mapped[str] = mapped_column(String(32), default="UNCLASSIFIED")
    tracking_since: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WhaleActivity(Base):
    __tablename__ = "whale_activities"

    event_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    wallet_address: Mapped[str] = mapped_column(
        String(64), ForeignKey("watched_wallets.wallet_address")
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    activity_type: Mapped[ActivityType] = mapped_column(Enum(ActivityType), index=True)
    asset_symbol: Mapped[str] = mapped_column(String(16))
    amount: Mapped[float] = mapped_column(Float)
    notional_value_usd: Mapped[float] = mapped_column(Float)
    tx_hash: Mapped[str] = mapped_column(String(80), unique=True)
    raw_log: Mapped[dict] = mapped_column(JSON)
    ai_interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)
    alert_passed: Mapped[bool] = mapped_column(default=False, index=True)


class AISummary(Base):
    __tablename__ = "ai_summaries"

    summary_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    wallet_address: Mapped[str] = mapped_column(
        String(64), ForeignKey("watched_wallets.wallet_address"), index=True
    )
    window_start: Mapped[datetime] = mapped_column(DateTime)
    window_end: Mapped[datetime] = mapped_column(DateTime)
    narrative_text: Mapped[str] = mapped_column(Text)
    confidence_rating: Mapped[float] = mapped_column(Float, default=0.5)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
