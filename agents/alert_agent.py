"""Alert Agent — rule-based monitoring.

Monitors for:
1. Price moves > threshold (default 5c)
2. Volume spikes > threshold (default 50%)
3. Arbitrage gaps > threshold (default 5c)
4. Markets closing within threshold (default 24h)
5. Keyword watchlist matches

Schedule: Every 5 minutes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import Alert


class AlertAgent(BaseAgent):
    def __init__(self, config: Any = None) -> None:
        super().__init__(name="alert", config=config)

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        queries = context["queries"]
        alert_rules = context.get("alert_rules")

        # Default thresholds
        price_threshold = 0.05
        volume_spike_pct = 0.50
        arb_threshold = 0.05
        close_hours = 24
        keywords: List[str] = ["election", "fed", "rate", "bitcoin", "trump"]

        if alert_rules:
            price_threshold = alert_rules.price_move_threshold
            volume_spike_pct = alert_rules.volume_spike_pct
            arb_threshold = alert_rules.arbitrage_gap_threshold
            close_hours = alert_rules.close_hours_threshold
            keywords = alert_rules.keywords

        alerts_created = 0

        # ── 1. Price Move Alerts ─────────────────────────────
        alerts_created += self._check_price_moves(queries, price_threshold)

        # ── 2. Volume Spike Alerts ───────────────────────────
        alerts_created += self._check_volume_spikes(queries, volume_spike_pct)

        # ── 3. Arbitrage Gap Alerts ──────────────────────────
        alerts_created += self._check_arbitrage_gaps(queries, arb_threshold)

        # ── 4. Closing Soon Alerts ───────────────────────────
        alerts_created += self._check_closing_soon(queries, close_hours)

        # ── 5. Keyword Watchlist ─────────────────────────────
        alerts_created += self._check_keywords(queries, keywords)

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            items_processed=alerts_created,
            summary=f"Generated {alerts_created} alerts.",
            data={"alerts_created": alerts_created},
        )

    def _check_price_moves(self, queries: Any, threshold: float) -> int:
        """Alert on significant price movements."""
        count = 0
        markets = queries.get_all_markets()
        for market in markets:
            history = queries.get_price_history(market["id"], limit=2)
            if len(history) < 2:
                continue
            latest = history[0].get("yes_price")
            previous = history[1].get("yes_price")
            if latest is None or previous is None:
                continue
            move = abs(latest - previous)
            if move >= threshold:
                direction = "up" if latest > previous else "down"
                severity = "critical" if move >= threshold * 2 else "warning"
                alert = Alert(
                    alert_type="price_move",
                    severity=severity,
                    market_id=market["id"],
                    title=f"Price move {direction} ${move:.2f}",
                    message=f"{market['title']}: {market['platform']} price moved {direction} by ${move:.2f} (${previous:.2f} -> ${latest:.2f})",
                    data=json.dumps({"previous": previous, "latest": latest, "move": move}),
                )
                queries.insert_alert(alert)
                count += 1
        return count

    def _check_volume_spikes(self, queries: Any, pct_threshold: float) -> int:
        """Alert on volume spikes compared to recent history."""
        count = 0
        markets = queries.get_all_markets()
        for market in markets:
            history = queries.get_price_history(market["id"], limit=10)
            if len(history) < 3:
                continue
            latest_vol = history[0].get("volume")
            if latest_vol is None:
                continue
            # Average of previous snapshots
            prev_vols = [h["volume"] for h in history[1:] if h.get("volume")]
            if not prev_vols:
                continue
            avg_vol = sum(prev_vols) / len(prev_vols)
            if avg_vol <= 0:
                continue
            spike = (latest_vol - avg_vol) / avg_vol
            if spike >= pct_threshold:
                alert = Alert(
                    alert_type="volume_spike",
                    severity="warning",
                    market_id=market["id"],
                    title=f"Volume spike +{spike:.0%}",
                    message=f"{market['title']}: Volume spiked {spike:.0%} above average ({latest_vol:.0f} vs avg {avg_vol:.0f})",
                    data=json.dumps({"latest_volume": latest_vol, "avg_volume": avg_vol, "spike_pct": spike}),
                )
                queries.insert_alert(alert)
                count += 1
        return count

    def _check_arbitrage_gaps(self, queries: Any, threshold: float) -> int:
        """Alert on cross-platform arbitrage opportunities."""
        count = 0
        pairs = queries.get_all_pairs()
        for pair in pairs:
            gap = pair.get("price_gap")
            if gap is not None and gap >= threshold:
                severity = "critical" if gap >= threshold * 2 else "warning"
                alert = Alert(
                    alert_type="arbitrage",
                    severity=severity,
                    pair_id=pair["id"],
                    title=f"Arbitrage gap ${gap:.2f}",
                    message=f"Cross-platform gap: {pair.get('kalshi_title', 'Kalshi')} vs {pair.get('poly_title', 'Polymarket')} — ${gap:.2f} gap",
                    data=json.dumps({
                        "kalshi_yes": pair.get("kalshi_yes"),
                        "poly_yes": pair.get("poly_yes"),
                        "gap": gap,
                    }),
                )
                queries.insert_alert(alert)
                count += 1
        return count

    def _check_closing_soon(self, queries: Any, hours: int) -> int:
        """Alert on markets closing within threshold hours."""
        count = 0
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours)
        markets = queries.get_all_markets()

        for market in markets:
            close_time_str = market.get("close_time")
            if not close_time_str:
                continue
            try:
                # Handle various datetime formats
                close_time_str = close_time_str.replace("Z", "+00:00")
                close_time = datetime.fromisoformat(close_time_str)
                if close_time.tzinfo is None:
                    close_time = close_time.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            if now < close_time <= cutoff:
                hours_left = (close_time - now).total_seconds() / 3600
                alert = Alert(
                    alert_type="closing_soon",
                    severity="info",
                    market_id=market["id"],
                    title=f"Closing in {hours_left:.1f}h",
                    message=f"{market['title']} ({market['platform']}) closing in {hours_left:.1f} hours",
                    data=json.dumps({"close_time": close_time_str, "hours_left": hours_left}),
                )
                queries.insert_alert(alert)
                count += 1
        return count

    def _check_keywords(self, queries: Any, keywords: List[str]) -> int:
        """Alert on new markets matching keyword watchlist."""
        count = 0
        markets = queries.get_all_markets()

        # Only alert on markets we haven't alerted on before
        existing_alerts = queries.get_alerts(alert_type="keyword", limit=1000)
        alerted_market_ids = {a.get("market_id") for a in existing_alerts}

        for market in markets:
            if market["id"] in alerted_market_ids:
                continue
            title_lower = market.get("title", "").lower()
            matched = [kw for kw in keywords if kw.lower() in title_lower]
            if matched:
                alert = Alert(
                    alert_type="keyword",
                    severity="info",
                    market_id=market["id"],
                    title=f"Keyword match: {', '.join(matched)}",
                    message=f"New market matches watchlist: {market['title']} [{', '.join(matched)}]",
                    data=json.dumps({"keywords": matched}),
                )
                queries.insert_alert(alert)
                count += 1
        return count
