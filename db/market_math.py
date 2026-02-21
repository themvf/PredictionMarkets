"""Prediction market domain calculations.

Encodes core financial concepts specific to binary prediction markets:
- Implied probability from price
- Vigorish (overround/vig) — the "house edge" built into prices
- Liquidity-adjusted gap scoring
- Time-decay weighting for price moves near expiry
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def implied_probability(yes_price: Optional[float]) -> Optional[float]:
    """Convert a market price to implied probability.

    In an efficient binary market, the yes price IS the implied probability.
    A yes price of $0.65 implies a 65% probability of the event occurring.
    """
    if yes_price is None:
        return None
    return max(0.0, min(1.0, yes_price))


def overround(yes_price: Optional[float], no_price: Optional[float]) -> Optional[float]:
    """Calculate the vigorish (overround) of a binary market.

    In a perfectly efficient market: yes_price + no_price = 1.00
    In practice: yes_price + no_price > 1.00 (the excess is the vig).

    Examples:
      yes=0.52, no=0.52 -> overround=0.04 (4% vig)
      yes=0.65, no=0.35 -> overround=0.00 (no vig, rare)
      yes=0.60, no=0.45 -> overround=0.05 (5% vig)

    Kalshi typically: 2-6% overround (regulated, USD settlement)
    Polymarket typically: 1-3% overround (crypto-native, lower fees)
    """
    if yes_price is None or no_price is None:
        return None
    return round(yes_price + no_price - 1.0, 4)


def vig_adjusted_price(yes_price: Optional[float],
                       no_price: Optional[float]) -> Optional[float]:
    """Remove the vig to get a "fair" probability estimate.

    Normalizes prices so they sum to 1.0 by distributing the
    overround proportionally.

    Example: yes=0.55, no=0.50 (overround=0.05)
      -> fair_yes = 0.55 / 1.05 = 0.5238
    """
    if yes_price is None or no_price is None:
        return None
    total = yes_price + no_price
    if total <= 0:
        return None
    return round(yes_price / total, 4)


def cross_platform_gap(kalshi_yes: Optional[float], kalshi_no: Optional[float],
                       poly_yes: Optional[float], poly_no: Optional[float]) -> dict:
    """Calculate the meaningful gap between platforms, accounting for vig.

    Returns both the raw gap and the vig-adjusted ("fair") gap.
    The fair gap strips out structural vig differences, revealing
    the genuine pricing disagreement.
    """
    raw_gap = None
    fair_gap = None
    kalshi_vig = None
    poly_vig = None
    kalshi_fair = None
    poly_fair = None

    if kalshi_yes is not None and poly_yes is not None:
        raw_gap = round(abs(kalshi_yes - poly_yes), 4)

    kalshi_vig = overround(kalshi_yes, kalshi_no)
    poly_vig = overround(poly_yes, poly_no)
    kalshi_fair = vig_adjusted_price(kalshi_yes, kalshi_no)
    poly_fair = vig_adjusted_price(poly_yes, poly_no)

    if kalshi_fair is not None and poly_fair is not None:
        fair_gap = round(abs(kalshi_fair - poly_fair), 4)

    return {
        "raw_gap": raw_gap,
        "fair_gap": fair_gap,
        "kalshi_vig": kalshi_vig,
        "poly_vig": poly_vig,
        "kalshi_fair_prob": kalshi_fair,
        "poly_fair_prob": poly_fair,
    }


def liquidity_score(volume: Optional[float],
                    liquidity: Optional[float]) -> str:
    """Classify market depth into tiers.

    Thin markets are noisy — a 5c move on a $500 volume market
    is meaningless compared to a 5c move on a $500K market.

    Tiers based on prediction market norms:
      deep:     volume >= $100K or liquidity >= $50K
      moderate: volume >= $10K  or liquidity >= $5K
      thin:     volume >= $1K   or liquidity >= $500
      micro:    everything else
    """
    vol = volume or 0
    liq = liquidity or 0
    if vol >= 100_000 or liq >= 50_000:
        return "deep"
    if vol >= 10_000 or liq >= 5_000:
        return "moderate"
    if vol >= 1_000 or liq >= 500:
        return "thin"
    return "micro"


def liquidity_adjusted_threshold(base_threshold: float,
                                 volume: Optional[float],
                                 liquidity: Optional[float]) -> float:
    """Scale alert thresholds by liquidity tier.

    Thin markets need wider thresholds (more noise),
    deep markets get tighter thresholds (moves are more meaningful).

    Returns the adjusted threshold.
    """
    tier = liquidity_score(volume, liquidity)
    multipliers = {
        "deep": 0.8,       # Tighter: moves on deep markets matter more
        "moderate": 1.0,    # Baseline
        "thin": 1.5,        # Wider: thin markets are noisier
        "micro": 2.5,       # Much wider: micro markets are very noisy
    }
    return base_threshold * multipliers[tier]


def time_to_expiry_hours(close_time_str: Optional[str]) -> Optional[float]:
    """Calculate hours until market close/resolution."""
    if not close_time_str:
        return None
    try:
        ct = close_time_str.replace("Z", "+00:00")
        close_time = datetime.fromisoformat(ct)
        if close_time.tzinfo is None:
            close_time = close_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = (close_time - now).total_seconds() / 3600
        return round(delta, 2) if delta > 0 else 0.0
    except (ValueError, TypeError):
        return None


def expiry_urgency(hours_left: Optional[float]) -> str:
    """Classify time-to-expiry into urgency tiers.

    Near-expiry moves are far more significant:
      imminent:  < 4 hours
      soon:      < 24 hours
      this_week: < 168 hours (7 days)
      distant:   >= 168 hours
    """
    if hours_left is None:
        return "unknown"
    if hours_left < 4:
        return "imminent"
    if hours_left < 24:
        return "soon"
    if hours_left < 168:
        return "this_week"
    return "distant"
