"""Trader Collection Agent.

Fetches Polymarket leaderboard data across categories and time periods,
upserts trader profiles into the traders table.

Uses concurrent fetching to parallelize leaderboard API calls
across category/period combinations.

Schedule: Every 30 minutes.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import Trader

_MAX_WORKERS = 10


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

        categories = ["OVERALL", "POLITICS", "SPORTS", "CRYPTO", "ECONOMICS"]
        time_periods = ["ALL", "MONTH", "WEEK"]
        errors: List[str] = []

        # Build all category/period combinations
        combos = [
            (cat, period) for cat in categories for period in time_periods
        ]

        # Fetch all leaderboards concurrently
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
                total_pnl=entry.get("pnl"),
                total_volume=entry.get("vol"),
            ))

        traders_upserted = queries.upsert_traders_batch(traders_to_upsert)

        error_summary = f" ({len(errors)} errors)" if errors else ""
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            items_processed=traders_upserted,
            summary=f"Upserted {traders_upserted} trader profiles{error_summary}.",
            data={
                "traders_upserted": traders_upserted,
                "errors": errors[:10],
            },
        )
