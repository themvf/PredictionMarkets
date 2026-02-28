"""Trader Collection Agent.

Fetches Polymarket leaderboard data across categories and time periods,
upserts trader profiles into the traders table.

Schedule: Every 30 minutes.
"""

from __future__ import annotations

from typing import Any, Dict

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import Trader


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

        traders_upserted = 0
        errors = []

        categories = ["OVERALL", "POLITICS", "SPORTS", "CRYPTO", "ECONOMICS"]
        time_periods = ["ALL", "MONTH", "WEEK"]
        seen_wallets: set = set()

        for category in categories:
            for period in time_periods:
                try:
                    leaders = polymarket_client.get_leaderboard(
                        category=category,
                        time_period=period,
                        order_by="PNL",
                        limit=50,
                    )
                    for entry in leaders:
                        wallet = entry.get("proxyWallet", "")
                        if not wallet or wallet in seen_wallets:
                            continue
                        seen_wallets.add(wallet)

                        trader = Trader(
                            proxy_wallet=wallet,
                            user_name=entry.get("userName", ""),
                            profile_image=entry.get("profileImage", ""),
                            x_username=entry.get("xUsername", ""),
                            verified_badge=bool(entry.get("verifiedBadge", False)),
                            total_pnl=entry.get("pnl"),
                            total_volume=entry.get("vol"),
                        )
                        queries.upsert_trader(trader)
                        traders_upserted += 1
                except Exception as e:
                    errors.append(f"Leaderboard {category}/{period}: {e}")

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
