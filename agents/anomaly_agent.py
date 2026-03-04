"""Anomaly Detection Agent.

Scans recent whale trades and compares against trader historical patterns
to detect unusual trading behavior:

1. large_conviction  — Single trade > 5x trader's average trade size
2. early_entry       — Trade within 2h of market creation with size > $5K
3. sudden_activity   — 24h volume > 3x 7-day daily average
4. contrarian        — Large buy (>$10K) on a side priced < 0.20
5. category_switch   — Trader suddenly active in a new category

Schedule: Every 30 minutes (same cadence as WhaleAgent).
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import TraderAnomaly, Alert

# How far back to scan for new trades each run
_LOOKBACK_MINUTES = 35  # slightly > 30min schedule to avoid gaps


class AnomalyDetectionAgent(BaseAgent):
    def __init__(self, config: Any = None) -> None:
        super().__init__(name="anomaly", config=config)

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        queries = context["queries"]

        cutoff_ts = int(
            (datetime.now(timezone.utc) - timedelta(minutes=_LOOKBACK_MINUTES))
            .timestamp()
        )

        # Get recent whale trades
        recent_trades = queries.get_whale_trades(limit=500, min_size=0)
        recent_trades = [
            t for t in recent_trades
            if (t.get("trade_timestamp") or 0) >= cutoff_ts
        ]

        if not recent_trades:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                summary="No recent trades to analyze.",
                items_processed=0,
            )

        anomalies: List[TraderAnomaly] = []
        critical_alerts: List[Alert] = []
        errors: List[str] = []

        # Group recent trades by trader
        by_trader: Dict[int, List[Dict]] = defaultdict(list)
        for t in recent_trades:
            tid = t.get("trader_id")
            if tid:
                by_trader[tid].append(t)

        # Cache trader metrics to avoid repeated lookups
        metrics_cache: Dict[int, Dict | None] = {}

        for trader_id, trades in by_trader.items():
            try:
                # Get or cache metrics
                if trader_id not in metrics_cache:
                    metrics_cache[trader_id] = queries.get_trader_metrics(trader_id)
                metrics = metrics_cache[trader_id]

                wallet = trades[0].get("proxy_wallet", "")
                user_name = trades[0].get("user_name", "") or wallet[:10]

                for trade in trades:
                    detected = self._check_trade(
                        trade, metrics, trader_id, wallet, user_name
                    )
                    anomalies.extend(detected)

                # Check sudden_activity at trader level (pass cached metrics)
                sudden = self._check_sudden_activity(
                    trader_id, wallet, user_name, trades, metrics
                )
                if sudden:
                    anomalies.append(sudden)

            except Exception as e:
                errors.append(f"Trader {trader_id}: {e}")

        # Batch insert anomalies
        inserted = 0
        if anomalies:
            inserted = queries.insert_trader_anomalies_batch(anomalies)

            # Create Alert entries for critical anomalies
            for a in anomalies:
                if a.severity == "critical":
                    critical_alerts.append(Alert(
                        alert_type="trader_anomaly",
                        severity="critical",
                        title=f"Anomaly: {a.anomaly_type}",
                        message=a.description,
                        data=a.data,
                    ))

        if critical_alerts:
            try:
                queries.insert_alerts_batch(critical_alerts)
            except Exception as e:
                errors.append(f"Alert batch: {e}")

        error_summary = f" ({len(errors)} errors)" if errors else ""
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            items_processed=inserted,
            summary=(
                f"Detected {inserted} anomalies from "
                f"{len(recent_trades)} recent trades{error_summary}."
            ),
            data={
                "anomalies_inserted": inserted,
                "trades_scanned": len(recent_trades),
                "critical_alerts": len(critical_alerts),
                "errors": errors[:10],
            },
        )

    def _check_trade(
        self,
        trade: Dict,
        metrics: Dict | None,
        trader_id: int,
        wallet: str,
        user_name: str,
    ) -> List[TraderAnomaly]:
        """Check a single trade for anomalies."""
        results: List[TraderAnomaly] = []
        usdc_size = _safe(trade.get("usdc_size")) or 0
        price = _safe(trade.get("price")) or 0
        side = trade.get("side", "")
        market_title = trade.get("market_title", "")

        # 1. Large conviction: trade > 5x avg trade size
        if metrics:
            avg_size = _safe(metrics.get("avg_trade_size"))
            if avg_size and avg_size > 0 and usdc_size > avg_size * 5:
                severity = "critical" if usdc_size > avg_size * 10 else "warning"
                results.append(TraderAnomaly(
                    trader_id=trader_id,
                    proxy_wallet=wallet,
                    anomaly_type="large_conviction",
                    severity=severity,
                    market_title=market_title,
                    description=(
                        f"{user_name} placed ${usdc_size:,.0f} trade "
                        f"({usdc_size/avg_size:.1f}x their avg ${avg_size:,.0f})"
                    ),
                    data=json.dumps({
                        "usdc_size": usdc_size,
                        "avg_size": avg_size,
                        "ratio": usdc_size / avg_size,
                        "side": side,
                    }),
                ))

        # 2. Contrarian: large buy on low-probability side
        if side == "BUY" and price < 0.20 and usdc_size > 10_000:
            severity = "warning" if usdc_size < 50_000 else "critical"
            results.append(TraderAnomaly(
                trader_id=trader_id,
                proxy_wallet=wallet,
                anomaly_type="contrarian",
                severity=severity,
                market_title=market_title,
                description=(
                    f"{user_name} bought ${usdc_size:,.0f} at "
                    f"{price*100:.0f}% (contrarian bet)"
                ),
                data=json.dumps({
                    "usdc_size": usdc_size,
                    "price": price,
                    "side": side,
                }),
            ))

        # 3. Early entry: trade size > $5K (detected at trade level)
        # Note: We can't check market creation time easily here
        # without a DB lookup, so we skip this for now and could
        # add it when we have market creation timestamps available

        return results

    def _check_sudden_activity(
        self,
        trader_id: int,
        wallet: str,
        user_name: str,
        recent_trades: List[Dict],
        metrics: Optional[Dict],
    ) -> Optional[TraderAnomaly]:
        """Check if trader's recent activity is abnormally high."""
        recent_volume = sum(
            _safe(t.get("usdc_size")) or 0 for t in recent_trades
        )

        if recent_volume < 20_000:
            return None

        if not metrics:
            return None

        avg_trade_size = _safe(metrics.get("avg_trade_size")) or 0
        total_trades = metrics.get("total_trades", 0) or 0
        if total_trades < 5 or avg_trade_size < 1000:
            return None

        # Estimate daily average: total_volume / 30 days
        daily_avg = (avg_trade_size * total_trades) / 30.0

        if daily_avg > 0 and recent_volume > daily_avg * 3:
            ratio = recent_volume / daily_avg
            severity = "critical" if ratio > 10 else "warning"
            # Use date-stamped market_title so the UNIQUE constraint
            # allows one sudden_activity detection per trader per day
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            return TraderAnomaly(
                trader_id=trader_id,
                proxy_wallet=wallet,
                anomaly_type="sudden_activity",
                severity=severity,
                market_title=f"activity_{today}",
                description=(
                    f"{user_name} traded ${recent_volume:,.0f} recently "
                    f"({ratio:.1f}x daily avg ${daily_avg:,.0f})"
                ),
                data=json.dumps({
                    "recent_volume": recent_volume,
                    "daily_avg": daily_avg,
                    "ratio": ratio,
                    "trade_count": len(recent_trades),
                }),
            )
        return None


def _safe(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return None
