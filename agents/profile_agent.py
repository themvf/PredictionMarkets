"""Trader Profile Agent.

Computes derived metrics from whale_trades and trader_positions data:
- Win rate, average trade size, largest win/loss
- Category-level P&L breakdown
- Trader tier classification (whale/shark/dolphin/fish)
- Behavioral tags (early_mover, contrarian, category_specialist, high_conviction)
- Consistency score from trade P&L standard deviation

Schedule: Every 2 hours.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from typing import Any, Dict, List

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import TraderMetrics, TraderCategoryPnl


def _tier_from_volume(volume_30d: float) -> str:
    """Classify trader tier based on 30-day trading volume."""
    if volume_30d >= 500_000:
        return "whale"
    if volume_30d >= 100_000:
        return "shark"
    if volume_30d >= 10_000:
        return "dolphin"
    return "fish"


class ProfileAgent(BaseAgent):
    def __init__(self, config: Any = None) -> None:
        super().__init__(name="profile", config=config)

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        queries = context["queries"]

        # Get traders active in the last 30 days (have whale trades)
        active_traders = queries.get_active_trader_ids(days=30, limit=500)

        if not active_traders:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                summary="No active traders to profile.",
                items_processed=0,
            )

        metrics_count = 0
        category_pnl_count = 0
        errors: List[str] = []

        for trader_info in active_traders:
            trader_id = trader_info["trader_id"]
            wallet = trader_info["proxy_wallet"]

            try:
                cat_rows = self._compute_profile(queries, trader_id, wallet)
                metrics_count += 1
                category_pnl_count += cat_rows
            except Exception as e:
                errors.append(f"Trader {trader_id}: {e}")

        error_summary = f" ({len(errors)} errors)" if errors else ""
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            items_processed=metrics_count,
            summary=(
                f"Profiled {metrics_count} traders, "
                f"{category_pnl_count} category PnL rows{error_summary}."
            ),
            data={
                "metrics_computed": metrics_count,
                "category_pnl_rows": category_pnl_count,
                "errors": errors[:10],
            },
        )

    def _compute_profile(
        self, queries: Any, trader_id: int, wallet: str
    ) -> int:
        """Compute metrics, tags, and category PnL for a single trader.

        Returns the number of category PnL rows upserted.
        """
        # Fetch all whale trades with market category info
        trades = queries.get_trader_trades_with_categories(trader_id)
        if not trades:
            return 0

        summary = queries.get_trader_trades_summary(trader_id)

        total_trades = summary.get("total_trades", 0) or 0
        avg_trade_size = _safe(summary.get("avg_trade_size"))
        total_volume = _safe(summary.get("total_volume")) or 0

        # Compute PnL per trade for consistency scoring + category breakdown
        trade_pnls: List[float] = []
        cat_data: Dict[str, Dict] = defaultdict(
            lambda: {"pnl": 0.0, "volume": 0.0, "count": 0, "wins": 0}
        )
        contrarian_count = 0

        for t in trades:
            usdc = _safe(t.get("usdc_size")) or 0
            price = _safe(t.get("price")) or 0
            side = t.get("side", "")
            category = t.get("category", "") or "Unknown"

            cat_data[category]["volume"] += usdc
            cat_data[category]["count"] += 1

            # Estimate PnL: buy at price p, expected payout 1.0 if correct
            if side == "BUY" and price > 0:
                estimated_pnl = usdc * (1.0 / price - 1.0)
            elif side == "SELL" and price > 0:
                estimated_pnl = usdc * (1.0 - price) / price
            else:
                estimated_pnl = 0
            trade_pnls.append(estimated_pnl)

            cat_data[category]["pnl"] += estimated_pnl
            if estimated_pnl > 0:
                cat_data[category]["wins"] += 1

            # Contrarian: buying at price < 0.30
            if side == "BUY" and price < 0.30:
                contrarian_count += 1

        # Win rate from resolved positions (simplistic: positive PnL = win)
        wins = sum(1 for p in trade_pnls if p > 0)
        losses = sum(1 for p in trade_pnls if p < 0)
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else None

        # Consistency score: 1.0 = perfectly consistent, 0.0 = wildly variable
        consistency_score = None
        if len(trade_pnls) >= 3:
            try:
                stdev = statistics.stdev(trade_pnls)
                mean = statistics.mean(trade_pnls)
                # Normalize: lower CV = more consistent
                cv = abs(stdev / mean) if mean != 0 else 10.0
                consistency_score = max(0.0, min(1.0, 1.0 / (1.0 + cv)))
            except (statistics.StatisticsError, ZeroDivisionError):
                pass

        # Largest win/loss
        largest_win = max(trade_pnls) if trade_pnls else None
        largest_loss = min(trade_pnls) if trade_pnls else None

        # Conviction score: avg position size normalized
        conviction_score = None
        if avg_trade_size and avg_trade_size > 0:
            # Scale: $50K+ = 1.0, $5K = 0.1
            conviction_score = min(1.0, avg_trade_size / 50_000)

        # Active positions from latest snapshot
        positions = queries.get_latest_trader_positions(trader_id)
        active_markets = len(positions)

        # Primary category and categories traded
        primary_category = ""
        if cat_data:
            primary_category = max(cat_data, key=lambda c: cat_data[c]["volume"])
        categories_traded = json.dumps(
            sorted(cat_data.keys())
        )

        # Tier
        trader_tier = _tier_from_volume(total_volume)

        # Tags
        tags_list: List[str] = []
        if contrarian_count > total_trades * 0.5 and total_trades >= 3:
            tags_list.append("contrarian")
        if primary_category and cat_data:
            top_vol = cat_data[primary_category]["volume"]
            if total_volume > 0 and top_vol / total_volume > 0.70:
                tags_list.append("category_specialist")
        if avg_trade_size and avg_trade_size > 20_000:
            tags_list.append("high_conviction")

        tags = ",".join(tags_list)

        # Upsert trader_metrics
        metrics = TraderMetrics(
            trader_id=trader_id,
            proxy_wallet=wallet,
            win_rate=win_rate,
            total_trades=total_trades,
            avg_trade_size=avg_trade_size,
            largest_win=largest_win,
            largest_loss=largest_loss,
            consistency_score=consistency_score,
            conviction_score=conviction_score,
            active_markets=active_markets,
            categories_traded=categories_traded,
            primary_category=primary_category,
        )
        queries.upsert_trader_metrics(metrics)

        # Update denormalized fields on traders table
        queries.update_trader_intelligence(
            trader_id,
            win_rate=win_rate,
            total_trades=total_trades,
            avg_position_size=avg_trade_size,
            active_positions=active_markets,
            trader_tier=trader_tier,
            primary_category=primary_category,
            tags=tags,
        )

        # Upsert per-category P&L breakdown
        cat_rows = [
            TraderCategoryPnl(
                trader_id=trader_id,
                category=cat,
                pnl=data["pnl"],
                volume=data["volume"],
                trade_count=data["count"],
                win_count=data["wins"],
            )
            for cat, data in cat_data.items()
        ]
        return queries.upsert_trader_category_pnl_batch(cat_rows) if cat_rows else 0


def _safe(val: Any) -> float | None:
    """Convert to float, returning None for NaN/inf/None."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return None
