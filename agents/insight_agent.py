"""Insight/Report Agent.

Generates natural language market intelligence briefings using GPT-4o
from aggregated market data, alerts, and analysis results.

Now includes domain context: implied probabilities, vig-adjusted gaps,
liquidity tier classification, and platform-specific grounding.

Schedule: Every 60 minutes.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import Insight
from db.market_math import (
    implied_probability, overround, cross_platform_gap,
    liquidity_score, vig_adjusted_price,
)
from llm.sanitize import sanitize_for_prompt


class InsightAgent(BaseAgent):
    def __init__(self, config: Any = None) -> None:
        super().__init__(name="insight", config=config)

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        queries = context["queries"]
        openai_client = context.get("openai_client")

        if not openai_client:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                summary="Skipped — no OpenAI client configured.",
                items_processed=0,
            )

        # ── Gather data for the briefing ─────────────────────
        market_counts = queries.get_market_counts()
        kalshi_count = market_counts.get("kalshi", 0)
        poly_count = market_counts.get("polymarket", 0)
        total_markets = kalshi_count + poly_count

        pairs = queries.get_all_pairs()
        pair_count = len(pairs)

        alerts = queries.get_alerts(acknowledged=False, limit=20)
        alert_count = len(alerts)

        # Top markets by volume — with implied probabilities and liquidity tiers
        all_markets = queries.get_all_markets()
        top_markets = all_markets[:15]
        top_markets_text = "\n".join(
            self._format_market_line(m) for m in top_markets
        )

        # Notable price gaps — vig-adjusted
        gap_pairs = [p for p in pairs if p.get("price_gap") and p["price_gap"] >= 0.02]
        gap_pairs.sort(key=lambda p: p.get("price_gap", 0), reverse=True)
        price_gaps_text = "\n".join(
            self._format_gap_line(p) for p in gap_pairs[:10]
        ) or "No significant vig-adjusted price gaps detected."

        # Recent alerts — with enriched context (sanitized for prompt safety)
        alerts_text = "\n".join(
            f"- [{a['severity'].upper()}] "
            f"{sanitize_for_prompt(a['title'], max_length=100)}: "
            f"{sanitize_for_prompt(a['message'], max_length=200)}"
            for a in alerts[:10]
        ) or "No recent alerts."

        # ── Generate briefing ────────────────────────────────
        from llm.prompts import PROMPTS, PLATFORM_CONTEXT
        prompt = PROMPTS["market_briefing"].format(
            platform_context=PLATFORM_CONTEXT,
            total_markets=total_markets,
            kalshi_count=kalshi_count,
            poly_count=poly_count,
            pair_count=pair_count,
            alert_count=alert_count,
            top_markets=top_markets_text or "No markets available.",
            price_gaps=price_gaps_text,
            recent_alerts=alerts_text,
        )

        report_content = openai_client.chat(prompt)
        if isinstance(report_content, dict):
            report_content = json.dumps(report_content)

        insight = Insight(
            report_type="briefing",
            title="Market Intelligence Briefing",
            content=report_content,
            markets_covered=total_markets,
            model_used="gpt-4o",
        )
        queries.insert_insight(insight)

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            items_processed=1,
            summary=f"Generated market briefing covering {total_markets} markets.",
            data={
                "total_markets": total_markets,
                "pair_count": pair_count,
                "alert_count": alert_count,
            },
        )

    def _format_market_line(self, m: Dict[str, Any]) -> str:
        """Format a single market line with domain context."""
        price = m.get("yes_price")
        no_price = m.get("no_price")
        vol = m.get("volume", 0) or 0
        liq_tier = liquidity_score(vol, m.get("liquidity"))
        vig = overround(price, no_price)

        prob_str = f"{price:.0%}" if price is not None else "N/A"
        price_str = f"${price:.2f}" if price is not None else "N/A"
        vig_str = f", vig: {vig:.1%}" if vig is not None else ""

        safe_title = sanitize_for_prompt(m['title'], max_length=150)
        return (
            f"- [{m['platform']}] {safe_title} — "
            f"Implied prob: {prob_str} (price: {price_str}{vig_str}) | "
            f"Vol: ${vol:,.0f} [{liq_tier}]"
        )

    def _format_gap_line(self, p: Dict[str, Any]) -> str:
        """Format a cross-platform gap line with vig-adjusted data."""
        kalshi_yes = p.get("kalshi_yes")
        poly_yes = p.get("poly_yes")
        kalshi_no = p.get("kalshi_no")
        poly_no = p.get("poly_no")

        gap_data = cross_platform_gap(kalshi_yes, kalshi_no, poly_yes, poly_no)
        raw_gap = gap_data.get("raw_gap", 0) or 0
        fair_gap = gap_data.get("fair_gap")

        k_prob = f"{kalshi_yes:.0%}" if kalshi_yes else "N/A"
        p_prob = f"{poly_yes:.0%}" if poly_yes else "N/A"
        fair_str = f"${fair_gap:.2f}" if fair_gap is not None else "N/A"

        safe_k_title = sanitize_for_prompt(p.get('kalshi_title', 'Kalshi'), max_length=100)
        safe_p_title = sanitize_for_prompt(p.get('poly_title', 'Poly'), max_length=100)
        return (
            f"- {safe_k_title}: {k_prob} vs "
            f"{safe_p_title}: {p_prob} "
            f"(raw gap: ${raw_gap:.2f}, fair gap: {fair_str})"
        )

    def generate_alert_summary(self, context: Dict[str, Any]) -> str:
        """Generate an on-demand alert summary with domain context."""
        queries = context["queries"]
        openai_client = context.get("openai_client")

        if not openai_client:
            return "OpenAI client not configured."

        alerts = queries.get_alerts(acknowledged=False, limit=50)
        if not alerts:
            return "No unacknowledged alerts to summarize."

        alerts_text = "\n".join(
            f"- [{a['severity']}] {a['alert_type']}: "
            f"{sanitize_for_prompt(a['title'], max_length=100)} — "
            f"{sanitize_for_prompt(a['message'], max_length=200)}"
            for a in alerts
        )

        from llm.prompts import PROMPTS, PLATFORM_CONTEXT
        prompt = PROMPTS["alert_summary"].format(
            platform_context=PLATFORM_CONTEXT,
            alerts=alerts_text,
        )
        result = openai_client.chat(prompt)

        insight = Insight(
            report_type="alert_summary",
            title="Alert Summary",
            content=result if isinstance(result, str) else json.dumps(result),
            markets_covered=len(alerts),
            model_used="gpt-4o",
        )
        queries.insert_insight(insight)

        return result if isinstance(result, str) else json.dumps(result)
