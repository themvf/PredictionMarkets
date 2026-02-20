"""Insight/Report Agent.

Generates natural language market intelligence briefings using GPT-4o
from aggregated market data, alerts, and analysis results.

Schedule: Every 60 minutes.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import Insight


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

        # Top markets by volume
        all_markets = queries.get_all_markets()
        top_markets = all_markets[:15]
        top_markets_text = "\n".join(
            f"- [{m['platform']}] {m['title']} — Yes: ${m.get('yes_price', 0) or 0:.2f}, Vol: {m.get('volume', 0) or 0:,.0f}"
            for m in top_markets
        )

        # Notable price gaps
        gap_pairs = [p for p in pairs if p.get("price_gap") and p["price_gap"] >= 0.02]
        gap_pairs.sort(key=lambda p: p.get("price_gap", 0), reverse=True)
        price_gaps_text = "\n".join(
            f"- {p.get('kalshi_title', 'Kalshi')}: ${p.get('kalshi_yes', 0) or 0:.2f} vs {p.get('poly_title', 'Poly')}: ${p.get('poly_yes', 0) or 0:.2f} (gap: ${p.get('price_gap', 0):.2f})"
            for p in gap_pairs[:10]
        ) or "No significant price gaps detected."

        # Recent alerts
        alerts_text = "\n".join(
            f"- [{a['severity'].upper()}] {a['title']}: {a['message']}"
            for a in alerts[:10]
        ) or "No recent alerts."

        # ── Generate briefing ────────────────────────────────
        from llm.prompts import PROMPTS
        prompt = PROMPTS["market_briefing"].format(
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

        # Persist the insight
        insight = Insight(
            report_type="briefing",
            title=f"Market Intelligence Briefing",
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

    def generate_alert_summary(self, context: Dict[str, Any]) -> str:
        """Generate an on-demand alert summary."""
        queries = context["queries"]
        openai_client = context.get("openai_client")

        if not openai_client:
            return "OpenAI client not configured."

        alerts = queries.get_alerts(acknowledged=False, limit=50)
        if not alerts:
            return "No unacknowledged alerts to summarize."

        alerts_text = "\n".join(
            f"- [{a['severity']}] {a['alert_type']}: {a['title']} — {a['message']}"
            for a in alerts
        )

        from llm.prompts import PROMPTS
        prompt = PROMPTS["alert_summary"].format(alerts=alerts_text)
        result = openai_client.chat(prompt)

        # Save as insight
        insight = Insight(
            report_type="alert_summary",
            title="Alert Summary",
            content=result if isinstance(result, str) else json.dumps(result),
            markets_covered=len(alerts),
            model_used="gpt-4o",
        )
        queries.insert_insight(insight)

        return result if isinstance(result, str) else json.dumps(result)
