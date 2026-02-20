"""Configuration dataclasses and .env loading for PredictionMarkets."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import os

from dotenv import load_dotenv

load_dotenv()

# Project root
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "prediction_markets.db"


@dataclass
class KalshiConfig:
    api_key_id: str = ""
    private_key_path: str = ""
    base_url: str = "https://api.elections.kalshi.com/trade-api/v2"
    rate_limit_delay: float = 0.06  # ~16 req/sec, under 20/sec limit

    @classmethod
    def from_env(cls) -> KalshiConfig:
        return cls(
            api_key_id=os.getenv("KALSHI_API_KEY_ID", ""),
            private_key_path=os.getenv(
                "KALSHI_PRIVATE_KEY_PATH",
                str(Path("C:/Docs/_AI Python Projects/Kalshi/Kalshi.txt")),
            ),
        )


@dataclass
class PolymarketConfig:
    gamma_url: str = "https://gamma-api.polymarket.com"
    clob_url: str = "https://clob.polymarket.com"

    @classmethod
    def from_env(cls) -> PolymarketConfig:
        return cls()


@dataclass
class OpenAIConfig:
    api_key: str = ""
    model: str = "gpt-4o"
    temperature: float = 0.3
    max_tokens: int = 2000

    @classmethod
    def from_env(cls) -> OpenAIConfig:
        return cls(api_key=os.getenv("OPENAI_API_KEY", ""))


@dataclass
class SchedulerConfig:
    discovery_interval_minutes: int = 30
    collection_interval_minutes: int = 5
    analyzer_interval_minutes: int = 15
    alert_interval_minutes: int = 5
    insight_interval_minutes: int = 60


@dataclass
class AlertRules:
    price_move_threshold: float = 0.05      # 5 cents
    volume_spike_pct: float = 0.50           # 50%
    arbitrage_gap_threshold: float = 0.05    # 5 cents
    close_hours_threshold: int = 24          # hours before close
    keywords: list = field(default_factory=lambda: [
        "election", "fed", "rate", "bitcoin", "trump",
    ])


@dataclass
class AppConfig:
    kalshi: KalshiConfig = field(default_factory=KalshiConfig)
    polymarket: PolymarketConfig = field(default_factory=PolymarketConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    alerts: AlertRules = field(default_factory=AlertRules)
    db_path: Path = DB_PATH

    @classmethod
    def from_env(cls) -> AppConfig:
        return cls(
            kalshi=KalshiConfig.from_env(),
            polymarket=PolymarketConfig.from_env(),
            openai=OpenAIConfig.from_env(),
        )


def load_config() -> AppConfig:
    """Load configuration from environment variables."""
    return AppConfig.from_env()
