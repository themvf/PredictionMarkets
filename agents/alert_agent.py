"""Alert Agent — domain-aware, liquidity-weighted monitoring.

Monitors for:
1. Price moves — thresholds scale by liquidity tier (thin markets need wider thresholds)
2. Volume spikes — compared to rolling average
3. Arbitrage gaps — vig-adjusted fair gaps, not raw price differences
4. Markets closing soon — with urgency classification
5. Keyword watchlist matches

Schedule: Every 5 minutes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import Alert
from db.market_math import (
    cross_platform_gap, liquidity_adjusted_threshold, liquidity_score,
    time_to_expiry_hours, expiry_urgency, overround,
)


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

        # ── 1. Price Move Alerts (liquidity-weighted) ────────
        alerts_created += self._check_price_moves(queries, price_threshold)

        # ── 2. Volume Spike Alerts ───────────────────────────
        alerts_created += self._check_volume_spikes(queries, volume_spike_pct)

        # ── 3. Arbitrage Gap Alerts (vig-adjusted) ───────────
        alerts_created += self._check_arbitrage_gaps(queries, arb_threshold)

        # ── 4. Closing Soon Alerts (with urgency) ────────────
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

    def _check_price_moves(self, queries: Any, base_threshold: float) -> int:
        """Alert on price moves, scaled by liquidity tier.

        A 5c move on a deep market ($100K+ volume) is significant.
        A 5c move on a micro market ($100 volume) is noise.
        The threshold scales: deep=0.8x, moderate=1x, thin=1.5x, micro=2.5x.
        """
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

            # Scale threshold by liquidity
            adjusted_threshold = liquidity_adjusted_threshold(
                base_threshold,
                market.get("volume"),
                market.get("liquidity"),
            )

            if move >= adjusted_threshold:
                direction = "up" if latest > previous else "down"
                liq_tier = liquidity_score(market.get("volume"), market.get("liquidity"))
                prob_prev = f"{previous:.0%}"
                prob_latest = f"{latest:.0%}"

                # Near-expiry moves are more critical
                expiry_h = time_to_expiry_hours(market.get("close_time"))
                urgency = expiry_urgency(expiry_h)
                if urgency in ("imminent", "soon") and liq_tier in ("deep", "moderate"):
                    severity = "critical"
                elif move >= adjusted_threshold * 2:
                    severity = "critical"
                elif liq_tier in ("deep", "moderate"):
                    severity = "warning"
                else:
                    severity = "info"

                alert = Alert(
                    alert_type="price_move",
                    severity=severity,
                    market_id=market["id"],
                    title=f"Price {direction} {move:.0%} [{liq_tier}]",
                    message=(
                        f"{market['title']} ({market['platform']}): "
                        f"implied prob moved {direction} from {prob_prev} to {prob_latest} "
                        f"(${move:.2f}) | Liquidity: {liq_tier}"
                        f"{f' | Expiry: {urgency} ({expiry_h:.0f}h)' if expiry_h else ''}"
                    ),
                    data=json.dumps({
                        "previous": previous, "latest": latest, "move": move,
                        "liquidity_tier": liq_tier, "adjusted_threshold": adjusted_threshold,
                        "expiry_hours": expiry_h, "urgency": urgency,
                    }),
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
            prev_vols = [h["volume"] for h in history[1:] if h.get("volume")]
            if not prev_vols:
                continue
            avg_vol = sum(prev_vols) / len(prev_vols)
            if avg_vol <= 0:
                continue
            spike = (latest_vol - avg_vol) / avg_vol
            if spike >= pct_threshold:
                liq_tier = liquidity_score(latest_vol, market.get("liquidity"))
                severity = "warning" if liq_tier in ("deep", "moderate") else "info"

                alert = Alert(
                    alert_type="volume_spike",
                    severity=severity,
                    market_id=market["id"],
                    title=f"Volume +{spike:.0%} [{liq_tier}]",
                    message=(
                        f"{market['title']} ({market['platform']}): "
                        f"Volume spiked {spike:.0%} above average "
                        f"(${latest_vol:,.0f} vs avg ${avg_vol:,.0f}) | Liquidity: {liq_tier}"
                    ),
                    data=json.dumps({
                        "latest_volume": latest_vol, "avg_volume": avg_vol,
                        "spike_pct": spike, "liquidity_tier": liq_tier,
                    }),
                )
                queries.insert_alert(alert)
                count += 1
        return count

    def _check_arbitrage_gaps(self, queries: Any, base_threshold: float) -> int:
        """Alert on vig-adjusted cross-platform gaps.

        Critical distinction: a raw gap of $0.05 with $0.04 of vig
        differential is NOT arbitrage — it's market structure.
        We use the fair (vig-adjusted) gap to filter real signals.
        """
        count = 0
        pairs = queries.get_all_pairs()
        for pair in pairs:
            kalshi_yes = pair.get("kalshi_yes")
            poly_yes = pair.get("poly_yes")
            if kalshi_yes is None or poly_yes is None:
                continue

            kalshi_no = pair.get("kalshi_no")
            poly_no = pair.get("poly_no")

            gap_data = cross_platform_gap(
                kalshi_yes, kalshi_no, poly_yes, poly_no,
            )
            raw_gap = gap_data["raw_gap"] or 0
            fair_gap = gap_data["fair_gap"]
            effective_gap = fair_gap if fair_gap is not None else raw_gap

            # Check if either side has meaningful liquidity
            kalshi_liq = liquidity_score(
                pair.get("kalshi_volume"), pair.get("kalshi_liquidity"),
            )
            poly_liq = liquidity_score(
                pair.get("poly_volume"), pair.get("poly_liquidity"),
            )

            if effective_gap >= base_threshold:
                is_vig_artifact = (
                    fair_gap is not None and fair_gap < 0.02 and raw_gap >= base_threshold
                )
                has_liquidity = (
                    kalshi_liq in ("deep", "moderate")
                    or poly_liq in ("deep", "moderate")
                )

                if is_vig_artifact:
                    severity = "info"
                    gap_label = "vig artifact"
                elif has_liquidity and effective_gap >= base_threshold * 2:
                    severity = "critical"
                    gap_label = "genuine gap"
                elif has_liquidity:
                    severity = "warning"
                    gap_label = "potential gap"
                else:
                    severity = "info"
                    gap_label = "thin-market gap"

                direction = "Kalshi higher" if kalshi_yes > poly_yes else "Poly higher"
                alert = Alert(
                    alert_type="arbitrage",
                    severity=severity,
                    pair_id=pair["id"],
                    title=f"Gap ${effective_gap:.2f} ({gap_label})",
                    message=(
                        f"{pair.get('kalshi_title', 'Kalshi')} vs "
                        f"{pair.get('poly_title', 'Polymarket')}: "
                        f"raw gap ${raw_gap:.2f}, fair gap ${fair_gap:.2f if fair_gap else 'N/A'} "
                        f"({direction}) | "
                        f"Vig: K={gap_data['kalshi_vig']:.1%}/{gap_data['poly_vig']:.1%} "
                        if gap_data.get("kalshi_vig") is not None and gap_data.get("poly_vig") is not None
                        else f"{pair.get('kalshi_title', 'Kalshi')} vs "
                             f"{pair.get('poly_title', 'Polymarket')}: "
                             f"gap ${effective_gap:.2f} ({direction})"
                    ),
                    data=json.dumps({
                        "raw_gap": raw_gap,
                        "fair_gap": fair_gap,
                        "kalshi_yes": kalshi_yes,
                        "poly_yes": poly_yes,
                        "kalshi_vig": gap_data.get("kalshi_vig"),
                        "poly_vig": gap_data.get("poly_vig"),
                        "kalshi_fair": gap_data.get("kalshi_fair_prob"),
                        "poly_fair": gap_data.get("poly_fair_prob"),
                        "is_vig_artifact": is_vig_artifact,
                        "kalshi_liquidity_tier": kalshi_liq,
                        "poly_liquidity_tier": poly_liq,
                    }),
                )
                queries.insert_alert(alert)
                count += 1
        return count

    def _check_closing_soon(self, queries: Any, hours: int) -> int:
        """Alert on markets closing soon, with urgency classification."""
        count = 0
        markets = queries.get_all_markets()

        for market in markets:
            expiry_h = time_to_expiry_hours(market.get("close_time"))
            if expiry_h is None or expiry_h <= 0 or expiry_h > hours:
                continue

            urgency = expiry_urgency(expiry_h)
            liq_tier = liquidity_score(market.get("volume"), market.get("liquidity"))

            # Only alert on markets with some activity
            if liq_tier == "micro":
                continue

            severity_map = {
                "imminent": "critical" if liq_tier in ("deep", "moderate") else "warning",
                "soon": "warning",
                "this_week": "info",
            }
            severity = severity_map.get(urgency, "info")

            price_str = ""
            if market.get("yes_price") is not None:
                price_str = f" | Current: {market['yes_price']:.0%} implied prob"

            alert = Alert(
                alert_type="closing_soon",
                severity=severity,
                market_id=market["id"],
                title=f"Closing {urgency} ({expiry_h:.1f}h) [{liq_tier}]",
                message=(
                    f"{market['title']} ({market['platform']}) "
                    f"closing in {expiry_h:.1f}h ({urgency}){price_str}"
                ),
                data=json.dumps({
                    "close_time": market.get("close_time"),
                    "hours_left": expiry_h,
                    "urgency": urgency,
                    "liquidity_tier": liq_tier,
                }),
            )
            queries.insert_alert(alert)
            count += 1
        return count

    def _check_keywords(self, queries: Any, keywords: List[str]) -> int:
        """Alert on new markets matching keyword watchlist."""
        count = 0
        markets = queries.get_all_markets()

        existing_alerts = queries.get_alerts(alert_type="keyword", limit=1000)
        alerted_market_ids = {a.get("market_id") for a in existing_alerts}

        for market in markets:
            if market["id"] in alerted_market_ids:
                continue
            title_lower = market.get("title", "").lower()
            matched = [kw for kw in keywords if kw.lower() in title_lower]
            if matched:
                liq_tier = liquidity_score(market.get("volume"), market.get("liquidity"))
                alert = Alert(
                    alert_type="keyword",
                    severity="info",
                    market_id=market["id"],
                    title=f"Keyword: {', '.join(matched)} [{liq_tier}]",
                    message=(
                        f"New market matches watchlist: {market['title']} "
                        f"[{', '.join(matched)}] | {market['platform']} | Liquidity: {liq_tier}"
                    ),
                    data=json.dumps({"keywords": matched, "liquidity_tier": liq_tier}),
                )
                queries.insert_alert(alert)
                count += 1
        return count
