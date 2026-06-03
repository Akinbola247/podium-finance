import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@lru_cache
def get_settings():
    return Settings()


class Settings:
    def __init__(self) -> None:
        self.injective_explorer_base = os.getenv(
            "INJECTIVE_EXPLORER_URL",
            "https://sentry.exchange.grpc-web.injective.network/api/explorer/v1",
        ).rstrip("/")
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_alerts_channel = os.getenv("REDIS_ALERTS_CHANNEL", "podium:live_alerts")
        self.poll_interval_seconds = float(os.getenv("POLL_INTERVAL_SECONDS", "12"))
        self.global_tx_batch_size = int(os.getenv("GLOBAL_TX_BATCH_SIZE", "40"))
        self.account_tx_backfill_limit = int(os.getenv("ACCOUNT_TX_BACKFILL_LIMIT", "80"))
        self.wallet_poll_batch_size = int(os.getenv("WALLET_POLL_BATCH_SIZE", "5"))
        self.wallet_poll_tx_limit = int(os.getenv("WALLET_POLL_TX_LIMIT", "25"))
        self.large_transfer_usd = float(os.getenv("LARGE_TRANSFER_USD", "500"))
        self.min_notional_usd = float(os.getenv("MIN_NOTIONAL_USD", "25"))
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.discover_default_limit = int(os.getenv("DISCOVER_DEFAULT_LIMIT", "100"))
        self.discover_scan_pages = int(os.getenv("DISCOVER_SCAN_PAGES", "40"))
        self.discover_page_size = int(os.getenv("DISCOVER_PAGE_SIZE", "80"))
        self.discover_min_notional_usd = float(os.getenv("DISCOVER_MIN_NOTIONAL_USD", "75"))
        self.discover_min_exchange_events = int(os.getenv("DISCOVER_MIN_EXCHANGE_EVENTS", "2"))
        self.discover_min_exchange_volume_usd = float(
            os.getenv("DISCOVER_MIN_EXCHANGE_VOLUME_USD", "500")
        )
        self.discover_min_largest_clip_usd = float(
            os.getenv("DISCOVER_MIN_LARGEST_CLIP_USD", "100")
        )
