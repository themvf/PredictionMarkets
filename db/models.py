"""Data models for prediction market entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class NormalizedMarket:
    """Platform-agnostic market representation."""
    id: Optional[int] = None
    platform: str = ""                  # "kalshi" or "polymarket"
    platform_id: str = ""               # original ID from platform
    title: str = ""
    description: str = ""
    category: str = ""
    status: str = "active"              # active, closed, settled
    yes_price: Optional[float] = None
    no_price: Optional[float] = None
    volume: Optional[float] = None
    liquidity: Optional[float] = None
    close_time: Optional[str] = None
    url: str = ""
    last_updated: Optional[str] = None
    raw_data: Optional[str] = None      # JSON string of original API response


@dataclass
class MarketPair:
    """A matched pair of markets across platforms."""
    id: Optional[int] = None
    kalshi_market_id: Optional[int] = None
    polymarket_market_id: Optional[int] = None
    match_confidence: float = 0.0
    match_reason: str = ""
    price_gap: Optional[float] = None   # abs(kalshi_yes - poly_yes)
    created_at: Optional[str] = None
    last_checked: Optional[str] = None


@dataclass
class PriceSnapshot:
    """Point-in-time price capture for a market."""
    id: Optional[int] = None
    market_id: Optional[int] = None
    yes_price: Optional[float] = None
    no_price: Optional[float] = None
    volume: Optional[float] = None
    open_interest: Optional[float] = None
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    timestamp: Optional[str] = None


@dataclass
class AnalysisResult:
    """Cross-platform analysis output."""
    id: Optional[int] = None
    pair_id: Optional[int] = None
    kalshi_yes: Optional[float] = None
    poly_yes: Optional[float] = None
    price_gap: Optional[float] = None
    gap_direction: str = ""             # "kalshi_higher" or "poly_higher"
    llm_analysis: Optional[str] = None  # GPT-4o qualitative analysis
    risk_score: Optional[float] = None
    created_at: Optional[str] = None


@dataclass
class Alert:
    """Generated alert from rule-based monitoring."""
    id: Optional[int] = None
    alert_type: str = ""                # price_move, volume_spike, arbitrage, closing_soon, keyword
    severity: str = "info"              # info, warning, critical
    market_id: Optional[int] = None
    pair_id: Optional[int] = None
    title: str = ""
    message: str = ""
    data: Optional[str] = None          # JSON details
    acknowledged: bool = False
    triggered_at: Optional[str] = None


@dataclass
class Insight:
    """AI-generated market intelligence report."""
    id: Optional[int] = None
    report_type: str = "briefing"       # briefing, deep_dive, alert_summary
    title: str = ""
    content: str = ""                   # Markdown report
    markets_covered: int = 0
    model_used: str = ""
    tokens_used: int = 0
    created_at: Optional[str] = None


@dataclass
class AgentLog:
    """Execution log entry for an agent run."""
    id: Optional[int] = None
    agent_name: str = ""
    status: str = ""                    # running, success, error
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    items_processed: int = 0
    summary: str = ""
    error: Optional[str] = None


@dataclass
class Trader:
    """Polymarket trader profile from Data API leaderboard."""
    id: Optional[int] = None
    proxy_wallet: str = ""
    user_name: str = ""
    profile_image: str = ""
    x_username: str = ""
    verified_badge: bool = False
    total_pnl: Optional[float] = None
    total_volume: Optional[float] = None
    portfolio_value: Optional[float] = None
    first_seen: Optional[str] = None
    last_updated: Optional[str] = None


@dataclass
class WhaleTrade:
    """Large trade from Polymarket Data API."""
    id: Optional[int] = None
    trader_id: Optional[int] = None
    proxy_wallet: str = ""
    condition_id: str = ""
    market_title: str = ""
    side: str = ""                      # BUY or SELL
    size: Optional[float] = None        # token size
    price: Optional[float] = None
    usdc_size: Optional[float] = None   # USD value
    outcome: str = ""
    outcome_index: Optional[int] = None
    transaction_hash: str = ""
    trade_timestamp: Optional[int] = None
    event_slug: str = ""
    created_at: Optional[str] = None


@dataclass
class TraderPosition:
    """Snapshot of a trader's position in a market."""
    id: Optional[int] = None
    trader_id: Optional[int] = None
    proxy_wallet: str = ""
    condition_id: str = ""
    market_title: str = ""
    outcome: str = ""
    size: Optional[float] = None
    avg_price: Optional[float] = None
    initial_value: Optional[float] = None
    current_value: Optional[float] = None
    cash_pnl: Optional[float] = None
    percent_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None
    cur_price: Optional[float] = None
    redeemable: bool = False
    event_slug: str = ""
    snapshot_time: Optional[str] = None
