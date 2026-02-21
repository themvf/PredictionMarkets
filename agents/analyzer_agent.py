"""Cross-Platform Analyzer Agent.

Compares matched market pairs using domain-aware calculations:
- Vig-adjusted fair probability comparison (not raw prices)
- Liquidity-tier classification
- Time-to-expiry urgency weighting
- GPT-4o analysis grounded with platform context and computed metrics

Schedule: Every 15 minutes.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import AnalysisResult
from db.market_math import (
    cross_platform_gap, liquidity_score, overround,
    vig_adjusted_price, time_to_expiry_hours, expiry_urgency,
)
from llm.sanitize import sanitize_for_prompt


class AnalyzerAgent(BaseAgent):
    def __init__(self, config: Any = None) -> None:
        super().__init__(name="analyzer", config=config)

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        queries = context["queries"]
        openai_client = context.get("openai_client")

        pairs = queries.get_all_pairs()
        analyses_created = 0
        significant_gaps = 0
        vig_artifact_count = 0

        for pair in pairs:
            kalshi_yes = pair.get("kalshi_yes")
            poly_yes = pair.get("poly_yes")

            if kalshi_yes is None or poly_yes is None:
                continue

            # ── Domain calculations ──────────────────────────
            kalshi_no = pair.get("kalshi_no")
            poly_no = pair.get("poly_no")

            gap_metrics = cross_platform_gap(
                kalshi_yes, kalshi_no, poly_yes, poly_no,
            )
            raw_gap = gap_metrics["raw_gap"] or 0
            fair_gap = gap_metrics["fair_gap"]
            gap_direction = "kalshi_higher" if kalshi_yes > poly_yes else "poly_higher"

            # Classify: is this gap real or just vig noise?
            is_vig_artifact = (
                fair_gap is not None and fair_gap < 0.02 and raw_gap >= 0.02
            )
            if is_vig_artifact:
                vig_artifact_count += 1

            # Update pair's price gap (use fair gap if available)
            from db.models import MarketPair
            updated_pair = MarketPair(
                kalshi_market_id=pair["kalshi_market_id"],
                polymarket_market_id=pair["polymarket_market_id"],
                match_confidence=pair.get("match_confidence", 0),
                match_reason=pair.get("match_reason", ""),
                price_gap=fair_gap if fair_gap is not None else raw_gap,
            )
            queries.upsert_pair(updated_pair)

            # ── LLM analysis for significant fair gaps ───────
            # Only send to GPT-4o if the vig-adjusted gap is meaningful
            # AND at least one side has moderate+ liquidity
            llm_analysis = None
            risk_score = None
            analysis_threshold = 0.03 if not is_vig_artifact else 0.05

            kalshi_liq_tier = liquidity_score(
                pair.get("kalshi_volume"), pair.get("kalshi_liquidity"),
            )
            poly_liq_tier = liquidity_score(
                pair.get("poly_volume"), pair.get("poly_liquidity"),
            )
            has_meaningful_liquidity = (
                kalshi_liq_tier in ("deep", "moderate")
                or poly_liq_tier in ("deep", "moderate")
            )

            effective_gap = fair_gap if fair_gap is not None else raw_gap
            if (effective_gap >= analysis_threshold
                    and has_meaningful_liquidity
                    and openai_client):
                significant_gaps += 1
                try:
                    analysis = self._analyze_gap(
                        pair, gap_metrics, gap_direction,
                        kalshi_liq_tier, poly_liq_tier,
                        openai_client,
                    )
                    llm_analysis = json.dumps(analysis)
                    risk_score = analysis.get("risk_score")
                except Exception:
                    llm_analysis = None

            result = AnalysisResult(
                pair_id=pair["id"],
                kalshi_yes=kalshi_yes,
                poly_yes=poly_yes,
                price_gap=effective_gap,
                gap_direction=gap_direction,
                llm_analysis=llm_analysis,
                risk_score=risk_score,
            )
            queries.insert_analysis(result)
            analyses_created += 1

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            items_processed=analyses_created,
            summary=(
                f"Analyzed {analyses_created} pairs. "
                f"{significant_gaps} significant (sent to GPT-4o). "
                f"{vig_artifact_count} were vig artifacts."
            ),
            data={
                "analyses_created": analyses_created,
                "significant_gaps": significant_gaps,
                "vig_artifacts": vig_artifact_count,
            },
        )

    def _analyze_gap(self, pair: Dict[str, Any],
                     gap_metrics: Dict[str, Any],
                     gap_direction: str,
                     kalshi_liq_tier: str,
                     poly_liq_tier: str,
                     openai_client: Any) -> Dict[str, Any]:
        """Send domain-enriched gap data to GPT-4o for qualitative analysis."""
        from llm.prompts import PROMPTS, PLATFORM_CONTEXT

        kalshi_expiry_h = time_to_expiry_hours(pair.get("kalshi_close_time"))
        poly_expiry_h = time_to_expiry_hours(pair.get("poly_close_time"))

        def _fmt_expiry(h):
            if h is None:
                return "Unknown"
            urgency = expiry_urgency(h)
            return f"{h:.1f}h ({urgency})"

        def _fmt_price(p):
            return f"${p:.2f}" if p is not None else "N/A"

        def _fmt_vol(v):
            if v is None:
                return "N/A"
            return f"${v:,.0f}"

        def _fmt_pct(p):
            if p is None:
                return "N/A"
            return f"{p:.1%}"

        def _fmt_vig(v):
            if v is None:
                return "N/A"
            return f"{v:.2%}"

        prompt = PROMPTS["gap_analysis"].format(
            platform_context=PLATFORM_CONTEXT,
            kalshi_title=sanitize_for_prompt(pair.get("kalshi_title", "Unknown")),
            kalshi_yes=_fmt_price(pair.get("kalshi_yes")),
            kalshi_no=_fmt_price(pair.get("kalshi_no")),
            kalshi_vig=_fmt_vig(gap_metrics.get("kalshi_vig")),
            kalshi_fair_prob=_fmt_pct(gap_metrics.get("kalshi_fair_prob")),
            kalshi_volume=_fmt_vol(pair.get("kalshi_volume")),
            kalshi_liquidity=_fmt_vol(pair.get("kalshi_liquidity")),
            kalshi_liq_tier=kalshi_liq_tier,
            kalshi_expiry=_fmt_expiry(kalshi_expiry_h),
            kalshi_category=sanitize_for_prompt(pair.get("kalshi_category", "N/A"), max_length=80),
            poly_title=sanitize_for_prompt(pair.get("poly_title", "Unknown")),
            poly_yes=_fmt_price(pair.get("poly_yes")),
            poly_no=_fmt_price(pair.get("poly_no")),
            poly_vig=_fmt_vig(gap_metrics.get("poly_vig")),
            poly_fair_prob=_fmt_pct(gap_metrics.get("poly_fair_prob")),
            poly_volume=_fmt_vol(pair.get("poly_volume")),
            poly_liquidity=_fmt_vol(pair.get("poly_liquidity")),
            poly_liq_tier=poly_liq_tier,
            poly_expiry=_fmt_expiry(poly_expiry_h),
            poly_category=sanitize_for_prompt(pair.get("poly_category", "N/A"), max_length=80),
            raw_gap=_fmt_price(gap_metrics.get("raw_gap")),
            fair_gap=_fmt_price(gap_metrics.get("fair_gap")),
            gap_direction=gap_direction,
        )

        return openai_client.chat(prompt, expect_json=True)
