"""Tests for prediction market domain calculations."""

import pytest
from db.market_math import (
    implied_probability, overround, vig_adjusted_price,
    cross_platform_gap, liquidity_score, liquidity_adjusted_threshold,
    time_to_expiry_hours, expiry_urgency,
)
from datetime import datetime, timezone, timedelta


class TestImpliedProbability:
    def test_normal_price(self):
        assert implied_probability(0.65) == 0.65

    def test_clamps_to_zero(self):
        assert implied_probability(-0.1) == 0.0

    def test_clamps_to_one(self):
        assert implied_probability(1.5) == 1.0

    def test_none_returns_none(self):
        assert implied_probability(None) is None


class TestOverround:
    def test_no_vig(self):
        """yes=0.65, no=0.35 -> perfectly efficient (vig=0)"""
        assert overround(0.65, 0.35) == 0.0

    def test_typical_kalshi_vig(self):
        """yes=0.55, no=0.50 -> 5% overround (typical Kalshi)"""
        assert overround(0.55, 0.50) == 0.05

    def test_tight_polymarket_vig(self):
        """yes=0.52, no=0.49 -> 1% overround (typical Polymarket)"""
        assert overround(0.52, 0.49) == 0.01

    def test_negative_vig(self):
        """Rare case where yes+no < 1 (underround)"""
        result = overround(0.40, 0.50)
        assert result == -0.1

    def test_none_input(self):
        assert overround(None, 0.50) is None
        assert overround(0.50, None) is None


class TestVigAdjustedPrice:
    def test_removes_vig(self):
        """yes=0.55, no=0.50 (5% vig) -> fair prob = 0.55/1.05 = 0.5238"""
        fair = vig_adjusted_price(0.55, 0.50)
        assert fair == pytest.approx(0.5238, abs=0.001)

    def test_no_vig_unchanged(self):
        """yes=0.65, no=0.35 (0% vig) -> fair prob = 0.65"""
        fair = vig_adjusted_price(0.65, 0.35)
        assert fair == 0.65

    def test_symmetric_vig(self):
        """yes=0.52, no=0.52 (4% vig) -> fair prob = 0.50"""
        fair = vig_adjusted_price(0.52, 0.52)
        assert fair == 0.5

    def test_none_input(self):
        assert vig_adjusted_price(None, 0.50) is None


class TestCrossPlatformGap:
    def test_vig_artifact_detection(self):
        """Kalshi (5% vig) vs Polymarket (1% vig) with similar fair prob."""
        result = cross_platform_gap(
            kalshi_yes=0.55, kalshi_no=0.50,  # 5% vig, fair=0.5238
            poly_yes=0.52, poly_no=0.49,      # 1% vig, fair=0.5149
        )
        # Raw gap is $0.03, but fair gap is only ~$0.009
        assert result["raw_gap"] == 0.03
        assert result["fair_gap"] < 0.01  # Vig artifact!
        assert result["kalshi_vig"] == 0.05
        assert result["poly_vig"] == 0.01

    def test_genuine_disagreement(self):
        """Both platforms have low vig but disagree on probability."""
        result = cross_platform_gap(
            kalshi_yes=0.70, kalshi_no=0.32,  # 2% vig, fair=0.6863
            poly_yes=0.55, poly_no=0.46,      # 1% vig, fair=0.5446
        )
        assert result["raw_gap"] == 0.15
        assert result["fair_gap"] > 0.10  # Genuine disagreement

    def test_none_prices(self):
        result = cross_platform_gap(None, None, 0.50, 0.50)
        assert result["raw_gap"] is None
        assert result["fair_gap"] is None

    def test_partial_no_prices(self):
        """Only yes prices available (no no_price data)."""
        result = cross_platform_gap(0.60, None, 0.55, None)
        assert result["raw_gap"] == 0.05
        assert result["fair_gap"] is None  # Can't compute without no prices


class TestLiquidityScore:
    def test_deep_market(self):
        assert liquidity_score(150_000, 60_000) == "deep"

    def test_deep_by_volume_alone(self):
        assert liquidity_score(100_000, 0) == "deep"

    def test_moderate_market(self):
        assert liquidity_score(50_000, 8_000) == "moderate"

    def test_thin_market(self):
        assert liquidity_score(5_000, 1_000) == "thin"

    def test_micro_market(self):
        assert liquidity_score(100, 50) == "micro"

    def test_none_values(self):
        assert liquidity_score(None, None) == "micro"


class TestLiquidityAdjustedThreshold:
    def test_deep_tighter(self):
        """Deep markets get tighter thresholds (0.8x)."""
        result = liquidity_adjusted_threshold(0.05, 200_000, 80_000)
        assert result == pytest.approx(0.04)

    def test_moderate_baseline(self):
        """Moderate markets keep the base threshold (1.0x)."""
        result = liquidity_adjusted_threshold(0.05, 50_000, 10_000)
        assert result == pytest.approx(0.05)

    def test_thin_wider(self):
        """Thin markets get wider thresholds (1.5x)."""
        result = liquidity_adjusted_threshold(0.05, 3_000, 800)
        assert result == pytest.approx(0.075)

    def test_micro_much_wider(self):
        """Micro markets get much wider thresholds (2.5x)."""
        result = liquidity_adjusted_threshold(0.05, 50, 10)
        assert result == pytest.approx(0.125)


class TestTimeToExpiry:
    def test_future_expiry(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        hours = time_to_expiry_hours(future)
        assert hours is not None
        assert abs(hours - 12.0) < 0.1

    def test_past_expiry(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        hours = time_to_expiry_hours(past)
        assert hours == 0.0

    def test_none_input(self):
        assert time_to_expiry_hours(None) is None

    def test_z_suffix(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=6)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        hours = time_to_expiry_hours(future)
        assert hours is not None
        assert abs(hours - 6.0) < 0.1


class TestExpiryUrgency:
    def test_imminent(self):
        assert expiry_urgency(2.0) == "imminent"

    def test_soon(self):
        assert expiry_urgency(12.0) == "soon"

    def test_this_week(self):
        assert expiry_urgency(72.0) == "this_week"

    def test_distant(self):
        assert expiry_urgency(500.0) == "distant"

    def test_none(self):
        assert expiry_urgency(None) == "unknown"
