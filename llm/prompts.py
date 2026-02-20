"""Prompt templates for GPT-4o interactions.

Three core prompts:
1. Market Matching — identify equivalent markets across platforms
2. Gap Analysis — qualitative analysis of price discrepancies
3. Report Generation — market intelligence briefings
"""

PROMPTS = {
    # ── Market Matching ──────────────────────────────────────
    "market_matching": """You are a prediction market analyst. Your task is to match equivalent markets across Kalshi and Polymarket.

Two markets are a "match" if they are asking the same underlying question, even if worded differently.

**Kalshi Markets:**
{kalshi_markets}

**Polymarket Markets:**
{polymarket_markets}

For each match you find, return the pair with a confidence score (0.0-1.0) and a brief reason.

Respond with JSON only:
{{
    "matches": [
        {{
            "kalshi_id": <kalshi market db id>,
            "polymarket_id": <polymarket market db id>,
            "confidence": <0.0 to 1.0>,
            "reason": "<brief explanation of why these match>"
        }}
    ]
}}

Only include matches with confidence >= 0.7. If no matches found, return {{"matches": []}}.""",

    # ── Gap Analysis ─────────────────────────────────────────
    "gap_analysis": """You are a prediction market analyst specializing in cross-platform price discrepancies.

Analyze the following matched market pair and explain the pricing gap:

**Kalshi Market:**
- Title: {kalshi_title}
- Yes Price: {kalshi_yes}
- Volume: {kalshi_volume}
- Category: {kalshi_category}

**Polymarket Market:**
- Title: {poly_title}
- Yes Price: {poly_yes}
- Volume: {poly_volume}
- Category: {poly_category}

**Price Gap:** {price_gap} ({gap_direction})

Analyze:
1. Why might this price discrepancy exist?
2. Which platform's pricing seems more efficient?
3. What information asymmetry could explain the gap?
4. Risk assessment for this discrepancy (1-10 scale)

Respond with JSON only:
{{
    "analysis": "<2-3 paragraph qualitative analysis>",
    "likely_cause": "<one of: information_asymmetry, liquidity_difference, timing_lag, platform_bias, genuine_disagreement>",
    "efficient_platform": "<kalshi or polymarket>",
    "risk_score": <1-10>,
    "key_factors": ["<factor1>", "<factor2>", "<factor3>"]
}}""",

    # ── Report Generation ────────────────────────────────────
    "market_briefing": """You are a prediction market intelligence analyst. Generate a concise market briefing.

**Current Market Summary:**
- Total active markets: {total_markets}
- Kalshi markets: {kalshi_count}
- Polymarket markets: {poly_count}
- Cross-platform pairs: {pair_count}
- Active alerts: {alert_count}

**Top Markets by Volume:**
{top_markets}

**Notable Price Gaps (Cross-Platform):**
{price_gaps}

**Recent Alerts:**
{recent_alerts}

Generate a markdown market intelligence briefing covering:
1. **Market Pulse** — overall market activity and sentiment
2. **Key Movers** — significant price changes and volume spikes
3. **Cross-Platform Analysis** — notable discrepancies between Kalshi and Polymarket
4. **Watch List** — markets to monitor closely and why
5. **Risk Assessment** — potential market risks and anomalies

Keep the report concise (400-600 words). Use bullet points for clarity.
Respond with the markdown report directly (not wrapped in JSON).""",

    # ── Alert Summary ────────────────────────────────────────
    "alert_summary": """You are a prediction market analyst. Summarize the following alerts into an actionable brief.

**Alerts:**
{alerts}

Generate a concise summary (200-300 words) in markdown that:
1. Groups alerts by type/theme
2. Highlights the most critical alerts
3. Suggests which alerts need immediate attention
4. Notes any patterns across the alerts

Respond with the markdown summary directly.""",
}
