"""Prompt templates for GPT-4o interactions.

Domain-grounded prompts for prediction market analysis.
Each prompt includes platform-specific context, vig awareness,
and liquidity weighting so the LLM operates with real market structure
knowledge rather than guessing from generic training data.

Four core prompts:
1. Market Matching — cross-platform equivalent identification
2. Gap Analysis — vig-aware, liquidity-weighted discrepancy analysis
3. Market Briefing — intelligence report with domain context
4. Alert Summary — actionable alert digest
"""

# ── Platform Context Block ───────────────────────────────────
# Injected into every prompt so GPT-4o understands the structural
# differences between platforms rather than treating them as identical.

PLATFORM_CONTEXT = """
## Platform Reference (use this context for your analysis)

**Kalshi** — US-based, CFTC-regulated exchange:
- Settlement: USD (US bank accounts only)
- User base: predominantly US retail + institutional
- Pricing: denominated in cents (0-99), displayed as dollars ($0.01-$0.99)
- Typical overround (vig): 2-6% due to regulatory compliance costs and wider spreads
- Liquidity: generally lower than Polymarket; concentrated in politics, economics, and weather
- Position limits: $25K per market (regulatory cap)
- Notable bias: US-centric user base can overweight domestic news narratives
- Market structure: event-series model (e.g., "Fed Rate Decision" series spawns individual meeting markets)

**Polymarket** — Crypto-native prediction market (non-US):
- Settlement: USDC on Polygon blockchain
- User base: global, crypto-native traders and sophisticated market makers
- Pricing: decimal (0.00-1.00), direct probability interpretation
- Typical overround (vig): 1-3% due to competitive automated market makers
- Liquidity: generally higher, especially on politically and crypto-adjacent topics
- Position limits: none (limited only by available liquidity)
- Notable bias: crypto-native users may overweight crypto/tech narratives; non-US users may underweight US-specific context
- Market structure: flat market model with event grouping via slugs

**Key structural differences that cause legitimate price gaps:**
1. **Vig differential** — Kalshi's higher vig means raw prices diverge even when implied probabilities agree. ALWAYS compare vig-adjusted fair probabilities, not raw prices.
2. **Settlement risk** — Polymarket settles in USDC (crypto risk), Kalshi in USD. Near-certain markets (>$0.90) may show gaps due to different discount rates.
3. **Regulatory access** — Kalshi is US-only; Polymarket is non-US. Information available to each user base may differ.
4. **Timing lag** — API update frequencies differ. Kalshi updates on trade; Polymarket CLOB updates continuously. Short-lived gaps may be stale data, not real disagreement.
5. **Position limits** — Kalshi's $25K cap means large informed traders may only be able to express views on Polymarket, leading to faster price discovery there for high-conviction events.
"""

PROMPTS = {
    # ── Market Matching ──────────────────────────────────────
    "market_matching": """You are a prediction market analyst specializing in cross-platform market identification.

Your task: identify markets on Kalshi and Polymarket that ask the **same underlying question**, even if worded differently.

{platform_context}

**Matching Rules:**
- Match on the **core question**, not surface wording. "Will the Fed cut rates in March?" and "Federal Reserve March 2026 rate decision: Cut?" are the same market.
- Be aware that Kalshi uses event-series tickers (e.g., "FED-25MAR-T4.50") while Polymarket uses natural language questions.
- Multi-outcome events: Kalshi may split "Who wins the election?" into individual yes/no markets per candidate, while Polymarket has a single multi-outcome market. Match the individual Kalshi markets to the parent Polymarket market.
- Do NOT match markets that are related but ask different questions (e.g., "Will Bitcoin reach $100K by June?" vs "Will Bitcoin reach $100K by December?").
- Time horizon must match: same resolution date or close enough (within 48 hours).

**Kalshi Markets:**
{kalshi_markets}

**Polymarket Markets:**
{polymarket_markets}

For each match, return:
- confidence: 0.0-1.0 (0.9+ for exact same question, 0.7-0.9 for equivalent with minor wording differences)
- reason: explain WHY these are the same underlying question

Respond with JSON only:
{{
    "matches": [
        {{
            "kalshi_id": <kalshi market db id>,
            "polymarket_id": <polymarket market db id>,
            "confidence": <0.0 to 1.0>,
            "reason": "<brief explanation>"
        }}
    ]
}}

Only include matches with confidence >= 0.7. If no matches, return {{"matches": []}}.""",

    # ── Gap Analysis ─────────────────────────────────────────
    "gap_analysis": """You are a quantitative prediction market analyst specializing in cross-platform pricing discrepancies.

{platform_context}

**Analyze this matched market pair:**

**Kalshi Market:**
- Title: {kalshi_title}
- Yes Price (raw): {kalshi_yes}
- No Price (raw): {kalshi_no}
- Overround (vig): {kalshi_vig}
- Fair Probability (vig-adjusted): {kalshi_fair_prob}
- Volume: {kalshi_volume}
- Liquidity: {kalshi_liquidity}
- Liquidity Tier: {kalshi_liq_tier}
- Time to Expiry: {kalshi_expiry}
- Category: {kalshi_category}

**Polymarket Market:**
- Title: {poly_title}
- Yes Price (raw): {poly_yes}
- No Price (raw): {poly_no}
- Overround (vig): {poly_vig}
- Fair Probability (vig-adjusted): {poly_fair_prob}
- Volume: {poly_volume}
- Liquidity: {poly_liquidity}
- Liquidity Tier: {poly_liq_tier}
- Time to Expiry: {poly_expiry}
- Category: {poly_category}

**Gap Metrics:**
- Raw Price Gap: {raw_gap} ({gap_direction})
- Vig-Adjusted Fair Gap: {fair_gap}
- Vig Differential: Kalshi {kalshi_vig} vs Polymarket {poly_vig}

**Analysis Framework (apply in order):**
1. **Vig check**: If the fair gap is < $0.02, the raw gap is likely explained by vig differential alone. Note this explicitly.
2. **Liquidity check**: If either side is "thin" or "micro" liquidity, the gap may be noise (wide spreads, stale quotes). Discount accordingly.
3. **Timing check**: If time to expiry differs or is very short (< 4 hours), the gap may be stale data rather than disagreement.
4. **Structural factors**: Consider settlement risk (USDC vs USD), regulatory access (US-only vs global), position limits ($25K cap on Kalshi).
5. **Genuine disagreement**: Only after ruling out the above — is there a real information asymmetry or difference in assessment?

Respond with JSON only:
{{
    "analysis": "<2-3 paragraph analysis following the framework above>",
    "gap_type": "<one of: vig_artifact, liquidity_noise, timing_stale, settlement_risk, regulatory_divergence, position_limit_effect, genuine_disagreement>",
    "is_actionable": <true if genuine disagreement, false if structural>,
    "efficient_platform": "<kalshi or polymarket or neither — which has better price discovery for this market?>",
    "confidence_in_assessment": <0.0 to 1.0 — how confident are you in this gap classification?>,
    "risk_score": <1-10 — 1=structural noise, 10=significant mispricing>,
    "key_factors": ["<factor1>", "<factor2>", "<factor3>"]
}}""",

    # ── Report Generation ────────────────────────────────────
    "market_briefing": """You are a prediction market intelligence analyst producing a daily briefing for a professional audience that understands market structure.

{platform_context}

**Current Market Data:**
- Total active markets: {total_markets} (Kalshi: {kalshi_count}, Polymarket: {poly_count})
- Cross-platform matched pairs: {pair_count}
- Active unacknowledged alerts: {alert_count}

**Top Markets by Volume (with implied probabilities):**
{top_markets}

**Notable Cross-Platform Gaps (vig-adjusted):**
{price_gaps}

**Recent Alerts:**
{recent_alerts}

**Generate a market intelligence briefing covering:**

1. **Market Pulse** — overall activity levels. Compare Kalshi vs Polymarket volume distribution. Note any unusual concentration in specific categories. Comment on aggregate vig levels (are spreads tightening or widening?).

2. **Key Movers** — significant price changes, but ONLY flag moves on markets with "moderate" or "deep" liquidity. Ignore micro-market noise. Express moves in probability terms (e.g., "implied probability of X rose from 35% to 48%"), not just dollar prices.

3. **Cross-Platform Analysis** — focus on vig-adjusted fair gaps. Distinguish between:
   - Gaps that are vig artifacts (note but deprioritize)
   - Gaps with genuine disagreement (highlight with explanation)
   Note which platform showed faster price discovery for recent events.

4. **Watch List** — markets to monitor, weighted by: (a) liquidity tier, (b) time to expiry, (c) gap significance. Near-expiry markets with deep liquidity and genuine disagreement get highest priority.

5. **Risk Assessment** — structural risks: vig compression, unusual volume patterns, potential market manipulation signals (e.g., sudden micro-market activity before news), regulatory developments affecting either platform.

Keep the report at 400-600 words. Use bullet points. Express all prices as both dollars and implied probabilities. Prioritize actionable intelligence over comprehensive coverage.
Respond with the markdown report directly (not wrapped in JSON).""",

    # ── Alert Summary ────────────────────────────────────────
    "alert_summary": """You are a prediction market analyst producing an actionable alert digest for a professional audience.

{platform_context}

**Active Alerts:**
{alerts}

**Produce an alert digest (200-300 words in markdown) that:**

1. **Triage by signal quality**: Separate alerts into:
   - **High signal**: Deep/moderate liquidity markets with genuine price moves or cross-platform disagreement
   - **Low signal**: Micro/thin liquidity markets, vig-artifact gaps, or stale-data timing issues

2. **Group by theme**: Cluster alerts by underlying event or category (e.g., "Multiple Fed-related markets moving together suggests rate expectations shifting")

3. **Prioritize**: Rank the top 3-5 alerts that warrant immediate attention, with reasoning

4. **Context**: For arbitrage alerts, note whether the gap is vig-adjusted or raw — a raw $0.05 gap with $0.04 of vig differential is NOT an arbitrage opportunity

Respond with the markdown digest directly.""",
}
