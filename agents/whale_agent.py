"""Whale Trade Monitoring Agent.

Monitors Polymarket Data API for large trades (configurable threshold),
stores whale trades, links them to trader profiles, and generates
whale_trade alerts for the alert pipeline.

Schedule: Every 5 minutes.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from .base import AgentResult, AgentStatus, BaseAgent
from db.models import WhaleTrade, Trader, Alert


class WhaleAgent(BaseAgent):
    def __init__(self, config: Any = None) -> None:
        super().__init__(name="whale", config=config)

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        queries = context["queries"]
        polymarket_client = context.get("polymarket_client")
        config = context.get("config")

        if not polymarket_client:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                summary="Skipped -- no Polymarket client configured.",
                items_processed=0,
            )

        # Configurable whale threshold
        threshold = 5000.0
        if config and hasattr(config, "polymarket"):
            threshold = getattr(config.polymarket, "whale_threshold_usd", 5000.0)

        trades_stored = 0
        alerts_created = 0
        errors = []

        try:
            raw_trades = polymarket_client.get_trades(
                filter_type="CASH",
                filter_amount=threshold,
                limit=500,
            )

            for raw in raw_trades:
                try:
                    wallet = raw.get("proxyWallet", "")
                    tx_hash = raw.get("transactionHash", "")
                    if not wallet or not tx_hash:
                        continue

                    # Ensure trader exists
                    trader = queries.get_trader_by_wallet(wallet)
                    trader_id = None
                    if not trader:
                        new_trader = Trader(
                            proxy_wallet=wallet,
                            user_name=raw.get("pseudonym", raw.get("name", "")),
                            profile_image=raw.get("profileImage", ""),
                        )
                        trader_id = queries.upsert_trader(new_trader)
                    else:
                        trader_id = trader["id"]

                    # Prefer API-provided USD size, fall back to tokens * price
                    price = raw.get("price", 0)
                    raw_usdc = raw.get("usdcSize") or raw.get("cashSize")
                    if raw_usdc is not None:
                        usdc_value = float(raw_usdc)
                    else:
                        token_size = raw.get("size", 0)
                        if price and token_size:
                            usdc_value = float(token_size) * float(price)
                        else:
                            usdc_value = float(token_size) if token_size else 0

                    # Coerce timestamp to int
                    raw_ts = raw.get("timestamp")
                    trade_ts = int(float(raw_ts)) if raw_ts is not None else None

                    trade = WhaleTrade(
                        trader_id=trader_id,
                        proxy_wallet=wallet,
                        condition_id=raw.get("conditionId", ""),
                        market_title=raw.get("title", ""),
                        side=raw.get("side", ""),
                        size=float(raw.get("size", 0)) if raw.get("size") else None,
                        price=float(price) if price else None,
                        usdc_size=usdc_value,
                        outcome=raw.get("outcome", ""),
                        outcome_index=raw.get("outcomeIndex"),
                        transaction_hash=tx_hash,
                        trade_timestamp=trade_ts,
                        event_slug=raw.get("eventSlug", ""),
                    )

                    result_id = queries.insert_whale_trade(trade)
                    if result_id:
                        trades_stored += 1

                        # Generate whale alert for very large trades
                        if usdc_value >= threshold * 2:
                            user_display = (
                                raw.get("pseudonym")
                                or raw.get("name")
                                or wallet[:10] + "..."
                            )
                            if usdc_value >= threshold * 10:
                                severity = "critical"
                            elif usdc_value >= threshold * 3:
                                severity = "warning"
                            else:
                                severity = "info"
                            alert = Alert(
                                alert_type="whale_trade",
                                severity=severity,
                                title=f"Whale {raw.get('side', 'TRADE')} ${usdc_value:,.0f}",
                                message=(
                                    f"{user_display} {raw.get('side', 'traded')} "
                                    f"${usdc_value:,.0f} on "
                                    f"{raw.get('title', 'Unknown market')} "
                                    f"({raw.get('outcome', '')}) @ ${price:.2f}"
                                ),
                                data=json.dumps({
                                    "wallet": wallet,
                                    "usdc_size": usdc_value,
                                    "market": raw.get("title", ""),
                                    "side": raw.get("side", ""),
                                    "price": price,
                                    "outcome": raw.get("outcome", ""),
                                }),
                            )
                            queries.insert_alert(alert)
                            alerts_created += 1

                except Exception as e:
                    errors.append(f"Trade processing: {e}")

        except Exception as e:
            errors.append(f"Trades fetch: {e}")

        error_summary = f" ({len(errors)} errors)" if errors else ""
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            items_processed=trades_stored,
            summary=(
                f"Stored {trades_stored} whale trades, "
                f"generated {alerts_created} alerts{error_summary}."
            ),
            data={
                "trades_stored": trades_stored,
                "alerts_created": alerts_created,
                "errors": errors[:10],
            },
        )
