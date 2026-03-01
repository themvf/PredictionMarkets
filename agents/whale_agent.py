"""Whale Trade Monitoring Agent.

Monitors Polymarket Data API for large trades (configurable threshold),
stores whale trades, links them to trader profiles, and generates
whale_trade alerts for the alert pipeline.

Uses batch database operations (single connection for traders, trades,
and alerts) to minimize round-trip overhead to Neon PostgreSQL.

Schedule: Every 5 minutes.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

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

        errors: List[str] = []

        try:
            raw_trades = polymarket_client.get_trades(
                filter_type="CASH",
                filter_amount=threshold,
                limit=500,
            )
        except Exception as e:
            errors.append(f"Trades fetch: {e}")
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                items_processed=0,
                summary=f"Stored 0 whale trades (1 errors).",
                data={"trades_stored": 0, "alerts_created": 0, "errors": errors[:10]},
            )

        # ── Phase 1: Parse all trades and collect unique wallets ──
        parsed_trades: List[Dict[str, Any]] = []
        wallets_needed: set = set()

        for raw in raw_trades:
            try:
                wallet = raw.get("proxyWallet", "")
                tx_hash = raw.get("transactionHash", "")
                if not wallet or not tx_hash:
                    continue

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

                raw_ts = raw.get("timestamp")
                trade_ts = int(float(raw_ts)) if raw_ts is not None else None

                wallets_needed.add(wallet)
                parsed_trades.append({
                    "raw": raw,
                    "wallet": wallet,
                    "tx_hash": tx_hash,
                    "price": price,
                    "usdc_value": usdc_value,
                    "trade_ts": trade_ts,
                })
            except Exception as e:
                errors.append(f"Trade parsing: {e}")

        # ── Phase 2: Batch lookup/create traders (1 connection) ──
        existing_traders = queries.get_traders_by_wallets(list(wallets_needed))

        new_traders = []
        for pt in parsed_trades:
            wallet = pt["wallet"]
            if wallet not in existing_traders:
                raw = pt["raw"]
                new_traders.append(Trader(
                    proxy_wallet=wallet,
                    user_name=raw.get("pseudonym", raw.get("name", "")),
                    profile_image=raw.get("profileImage", ""),
                ))
                # Mark as "will exist" to avoid duplicates
                existing_traders[wallet] = {"id": None}

        if new_traders:
            queries.upsert_traders_batch(new_traders)
            # Re-fetch to get IDs for the new traders
            new_wallets = [t.proxy_wallet for t in new_traders]
            new_trader_map = queries.get_traders_by_wallets(new_wallets)
            existing_traders.update(new_trader_map)

        # ── Phase 3: Build trade and alert objects ──────────────
        trades_to_insert: List[WhaleTrade] = []
        alerts_to_insert: List[Alert] = []

        for pt in parsed_trades:
            wallet = pt["wallet"]
            raw = pt["raw"]
            trader_data = existing_traders.get(wallet, {})
            trader_id = trader_data.get("id")

            trade = WhaleTrade(
                trader_id=trader_id,
                proxy_wallet=wallet,
                condition_id=raw.get("conditionId", ""),
                market_title=raw.get("title", ""),
                side=raw.get("side", ""),
                size=float(raw.get("size", 0)) if raw.get("size") else None,
                price=float(pt["price"]) if pt["price"] else None,
                usdc_size=pt["usdc_value"],
                outcome=raw.get("outcome", ""),
                outcome_index=raw.get("outcomeIndex"),
                transaction_hash=pt["tx_hash"],
                trade_timestamp=pt["trade_ts"],
                event_slug=raw.get("eventSlug", ""),
            )
            trades_to_insert.append(trade)

            # Generate whale alert for very large trades
            usdc_value = pt["usdc_value"]
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
                alerts_to_insert.append(Alert(
                    alert_type="whale_trade",
                    severity=severity,
                    title=f"Whale {raw.get('side', 'TRADE')} ${usdc_value:,.0f}",
                    message=(
                        f"{user_display} {raw.get('side', 'traded')} "
                        f"${usdc_value:,.0f} on "
                        f"{raw.get('title', 'Unknown market')} "
                        f"({raw.get('outcome', '')}) @ ${pt['price']:.2f}"
                    ),
                    data=json.dumps({
                        "wallet": wallet,
                        "usdc_size": usdc_value,
                        "market": raw.get("title", ""),
                        "side": raw.get("side", ""),
                        "price": pt["price"],
                        "outcome": raw.get("outcome", ""),
                    }),
                ))

        # ── Phase 4: Batch write trades + alerts (2 connections) ──
        trades_stored = queries.insert_whale_trades_batch(trades_to_insert)
        alerts_created = queries.insert_alerts_batch(alerts_to_insert)

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
