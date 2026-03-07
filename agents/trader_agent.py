"""Trader Collection Agent.

Fetches Polymarket leaderboard data across all categories and time periods,
upserts trader profiles. For top traders, also fetches portfolio values
and position snapshots.

Uses concurrent fetching to parallelize leaderboard API calls
across category/period combinations.

Schedule: Every 30 minutes.
"""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import Trader, TraderPosition

_MAX_WORKERS = 10

# All Polymarket leaderboard categories
_CATEGORIES = [
    "OVERALL", "POLITICS", "ECONOMICS", "FINANCE",
    "CRYPTO", "CULTURE", "TECH",
]
_TIME_PERIODS = ["ALL", "MONTH", "WEEK"]

# How many top traders (by PNL) to fetch portfolio values and positions for
_TOP_PORTFOLIO_COUNT = 200
_TOP_POSITIONS_COUNT = 100


def _safe_float(val: Any) -> float | None:
    """Convert a value to float, returning None for NaN or invalid."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return None


class TraderAgent(BaseAgent):
    def __init__(self, config: Any = None) -> None:
        super().__init__(name="trader", config=config)

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        queries = context["queries"]
        polymarket_client = context.get("polymarket_client")

        if not polymarket_client:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                summary="Skipped -- no Polymarket client configured.",
                items_processed=0,
            )

        errors: List[str] = []

        # ── Phase 1: Fetch leaderboards across all categories ────
        combos = [
            (cat, period) for cat in _CATEGORIES for period in _TIME_PERIODS
        ]

        all_entries: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            future_to_combo = {
                executor.submit(
                    polymarket_client.get_leaderboard,
                    category=cat,
                    time_period=period,
                    order_by="PNL",
                    limit=50,
                ): (cat, period)
                for cat, period in combos
            }
            for future in as_completed(future_to_combo):
                cat, period = future_to_combo[future]
                try:
                    leaders = future.result()
                    all_entries.extend(leaders)
                except Exception as e:
                    errors.append(f"Leaderboard {cat}/{period}: {e}")

        # Deduplicate and batch upsert
        seen_wallets: set = set()
        traders_to_upsert: list = []
        for entry in all_entries:
            wallet = entry.get("proxyWallet", "")
            if not wallet or wallet in seen_wallets:
                continue
            seen_wallets.add(wallet)

            traders_to_upsert.append(Trader(
                proxy_wallet=wallet,
                user_name=entry.get("userName", ""),
                profile_image=entry.get("profileImage", ""),
                x_username=entry.get("xUsername", ""),
                verified_badge=bool(entry.get("verifiedBadge", False)),
                total_pnl=_safe_float(entry.get("pnl")),
                total_volume=_safe_float(entry.get("vol")),
            ))

        traders_upserted = queries.upsert_traders_batch(traders_to_upsert)

        # ── Phase 2: Fetch portfolio values for top traders ──────
        portfolio_updated = 0
        top_traders = queries.get_top_traders(
            order_by="total_pnl", limit=_TOP_PORTFOLIO_COUNT
        )

        def _fetch_portfolio(wallet: str) -> tuple[str, float | None]:
            try:
                result = polymarket_client.get_portfolio_value(wallet)
                val = _safe_float(result.get("value") if isinstance(result, dict) else result)
                return wallet, val
            except Exception:
                return wallet, None

        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            futures = {
                executor.submit(_fetch_portfolio, t["proxy_wallet"]): t["proxy_wallet"]
                for t in top_traders
            }
            for future in as_completed(futures):
                wallet, val = future.result()
                if val is not None:
                    try:
                        queries.update_portfolio_value(wallet, val)
                        portfolio_updated += 1
                    except Exception as e:
                        errors.append(f"Portfolio {wallet[:10]}...: {e}")

        # ── Phase 3: Fetch positions for top traders ─────────────
        positions_inserted = 0
        top_for_positions = top_traders[:_TOP_POSITIONS_COUNT]

        def _fetch_positions(trader_dict: Dict) -> list[TraderPosition]:
            wallet = trader_dict["proxy_wallet"]
            trader_id = trader_dict["id"]
            try:
                raw_positions = polymarket_client.get_positions(
                    user=wallet, limit=50, sort_by="CURRENT"
                )
                result = []
                for p in raw_positions:
                    cash_pnl = _safe_float(p.get("cashPnl"))
                    percent_pnl = _safe_float(p.get("percentPnl"))
                    result.append(TraderPosition(
                        trader_id=trader_id,
                        proxy_wallet=wallet,
                        condition_id=p.get("conditionId", ""),
                        market_title=p.get("title", ""),
                        outcome=p.get("outcome", ""),
                        size=_safe_float(p.get("size")),
                        avg_price=_safe_float(p.get("avgPrice")),
                        initial_value=_safe_float(p.get("initialValue")),
                        current_value=_safe_float(p.get("currentValue")),
                        cash_pnl=cash_pnl,
                        percent_pnl=percent_pnl,
                        realized_pnl=_safe_float(p.get("realizedPnl")),
                        cur_price=_safe_float(p.get("curPrice")),
                        redeemable=bool(p.get("redeemable", False)),
                        event_slug=p.get("eventSlug", ""),
                    ))
                return result
            except Exception:
                return []

        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            futures = [
                executor.submit(_fetch_positions, t)
                for t in top_for_positions
            ]
            all_positions: list[TraderPosition] = []
            for future in as_completed(futures):
                all_positions.extend(future.result())

        if all_positions:
            try:
                positions_inserted = queries.insert_trader_positions_batch(all_positions)
            except Exception as e:
                errors.append(f"Position batch insert: {e}")

        error_summary = f" ({len(errors)} errors)" if errors else ""
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            items_processed=traders_upserted,
            summary=(
                f"Upserted {traders_upserted} traders, "
                f"{portfolio_updated} portfolios, "
                f"{positions_inserted} positions{error_summary}."
            ),
            data={
                "traders_upserted": traders_upserted,
                "portfolio_updated": portfolio_updated,
                "positions_inserted": positions_inserted,
                "errors": errors[:10],
            },
        )
