"""Named query functions for all database operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .database import DatabaseManager
from .models import (
    AgentLog, Alert, AnalysisResult, Insight,
    MarketPair, NormalizedMarket, PriceSnapshot,
    Trader, WhaleTrade, TraderPosition,
    TraderMetrics, TraderCategoryPnl, TraderAnomaly,
)

import json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MarketQueries:
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    # ── Markets ──────────────────────────────────────────────

    def upsert_market(self, market: NormalizedMarket) -> int:
        """Insert or update a market, returning its ID."""
        with self.db._connect() as conn:
            conn.execute("""
                INSERT INTO markets (platform, platform_id, title, description,
                    category, subcategory, status, yes_price, no_price, volume,
                    liquidity, close_time, url, last_updated, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, platform_id) DO UPDATE SET
                    title=excluded.title,
                    description=excluded.description,
                    category=excluded.category,
                    subcategory=excluded.subcategory,
                    status=excluded.status,
                    yes_price=excluded.yes_price,
                    no_price=excluded.no_price,
                    volume=excluded.volume,
                    liquidity=excluded.liquidity,
                    close_time=excluded.close_time,
                    url=excluded.url,
                    last_updated=excluded.last_updated,
                    raw_data=excluded.raw_data
            """, (
                market.platform, market.platform_id, market.title,
                market.description, market.category, market.subcategory,
                market.status, market.yes_price, market.no_price, market.volume,
                market.liquidity, market.close_time, market.url,
                _now(), market.raw_data,
            ))
            row = conn.execute(
                "SELECT id FROM markets WHERE platform=? AND platform_id=?",
                (market.platform, market.platform_id),
            ).fetchone()
            return row["id"]

    def upsert_markets_batch(self, markets: List[NormalizedMarket]) -> int:
        """Batch upsert markets in a single connection. Returns count upserted.

        Unlike upsert_market() which opens a new connection per market,
        this method processes ALL markets in one transaction — critical
        for performance when writing to Neon PostgreSQL over the network.
        """
        if not markets:
            return 0
        with self.db._connect() as conn:
            now = _now()
            for market in markets:
                conn.execute("""
                    INSERT INTO markets (platform, platform_id, title, description,
                        category, subcategory, status, yes_price, no_price, volume,
                        liquidity, close_time, url, last_updated, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(platform, platform_id) DO UPDATE SET
                        title=excluded.title,
                        description=excluded.description,
                        category=excluded.category,
                        subcategory=excluded.subcategory,
                        status=excluded.status,
                        yes_price=excluded.yes_price,
                        no_price=excluded.no_price,
                        volume=excluded.volume,
                        liquidity=excluded.liquidity,
                        close_time=excluded.close_time,
                        url=excluded.url,
                        last_updated=excluded.last_updated,
                        raw_data=excluded.raw_data
                """, (
                    market.platform, market.platform_id, market.title,
                    market.description, market.category, market.subcategory,
                    market.status, market.yes_price, market.no_price, market.volume,
                    market.liquidity, market.close_time, market.url,
                    now, market.raw_data,
                ))
            return len(markets)

    def get_distinct_categories(self, status: str = "active") -> List[str]:
        """Return sorted list of non-empty categories present in the markets table."""
        with self.db._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT category FROM markets WHERE status=? AND category != '' ORDER BY category",
                (status,),
            ).fetchall()
            return [r["category"] for r in rows]

    def get_distinct_subcategories(self, category: str,
                                   status: str = "active") -> List[str]:
        """Return sorted list of non-empty subcategories for a given category."""
        with self.db._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT subcategory FROM markets "
                "WHERE status=? AND category=? AND subcategory != '' "
                "ORDER BY subcategory",
                (status, category),
            ).fetchall()
            return [r["subcategory"] for r in rows]

    def get_all_markets(self, platform: Optional[str] = None,
                        status: str = "active",
                        category: Optional[str] = None,
                        subcategory: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            clauses = ["status=?"]
            params: list = [status]
            if platform:
                clauses.append("platform=?")
                params.append(platform)
            if category:
                clauses.append("category=?")
                params.append(category)
            if subcategory:
                clauses.append("subcategory=?")
                params.append(subcategory)
            where = " AND ".join(clauses)
            rows = conn.execute(
                f"SELECT * FROM markets WHERE {where} ORDER BY volume DESC",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def get_market_by_id(self, market_id: int) -> Optional[Dict[str, Any]]:
        with self.db._connect() as conn:
            row = conn.execute("SELECT * FROM markets WHERE id=?", (market_id,)).fetchone()
            return dict(row) if row else None

    def get_markets_by_platform(self, platform: str) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM markets WHERE platform=? AND status='active' ORDER BY volume DESC",
                (platform,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_markets_by_categories(
        self, platform: str, categories: List[str],
    ) -> List[Dict[str, Any]]:
        """Get active markets filtered to specific categories."""
        with self.db._connect() as conn:
            placeholders = ",".join("?" for _ in categories)
            rows = conn.execute(
                f"SELECT * FROM markets WHERE platform=? AND status='active' "
                f"AND category IN ({placeholders}) ORDER BY volume DESC",
                [platform] + categories,
            ).fetchall()
            return [dict(r) for r in rows]

    def search_markets(self, query: str) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM markets WHERE title {self.db._like} ? AND status='active' ORDER BY volume DESC",
                (f"%{query}%",),
            ).fetchall()
            return [dict(r) for r in rows]

    def close_expired_markets(self) -> int:
        """Mark active markets whose close_time has passed as 'closed'.

        Returns the number of markets updated.
        """
        with self.db._connect() as conn:
            if self.db._backend == "postgres":
                cursor = conn.execute("""
                    UPDATE markets SET status = 'closed'
                    WHERE status = 'active'
                      AND close_time IS NOT NULL
                      AND close_time != ''
                      AND close_time::timestamptz < NOW()
                """)
            else:
                cursor = conn.execute("""
                    UPDATE markets SET status = 'closed'
                    WHERE status = 'active'
                      AND close_time IS NOT NULL
                      AND close_time != ''
                      AND close_time < datetime('now')
                """)
            return cursor.rowcount

    def prune_old_closed_markets(self, days: int = 30) -> Dict[str, int]:
        """Delete closed markets older than `days`, preserving those with whale trades.

        Deletes associated price_snapshots, market_pairs, and alerts first.
        Returns counts of deleted rows per table.
        """
        result = {"markets": 0, "price_snapshots": 0, "market_pairs": 0, "alerts": 0}

        with self.db._connect() as conn:
            if self.db._backend == "postgres":
                cutoff_clause = f"close_time::timestamptz < NOW() - INTERVAL '{days} days'"
            else:
                cutoff_clause = f"close_time < datetime('now', '-{days} days')"

            # Find prunable market IDs: closed, past cutoff, no whale trades
            ids_rows = conn.execute(f"""
                SELECT m.id FROM markets m
                WHERE m.status = 'closed'
                  AND m.close_time IS NOT NULL
                  AND m.close_time != ''
                  AND {cutoff_clause}
                  AND NOT EXISTS (
                      SELECT 1 FROM whale_trades wt
                      WHERE wt.condition_id = m.platform_id
                  )
            """).fetchall()

            market_ids = [r["id"] for r in ids_rows]
            if not market_ids:
                return result

            placeholders = ",".join("?" for _ in market_ids)

            # Delete child rows first
            cur = conn.execute(
                f"DELETE FROM price_snapshots WHERE market_id IN ({placeholders})",
                market_ids,
            )
            result["price_snapshots"] = cur.rowcount

            cur = conn.execute(
                f"DELETE FROM market_pairs WHERE kalshi_market_id IN ({placeholders}) "
                f"OR polymarket_market_id IN ({placeholders})",
                market_ids + market_ids,
            )
            result["market_pairs"] = cur.rowcount

            cur = conn.execute(
                f"DELETE FROM alerts WHERE market_id IN ({placeholders})",
                market_ids,
            )
            result["alerts"] = cur.rowcount

            # Delete the markets
            cur = conn.execute(
                f"DELETE FROM markets WHERE id IN ({placeholders})",
                market_ids,
            )
            result["markets"] = cur.rowcount

        return result

    # ── Market Pairs ─────────────────────────────────────────

    def upsert_pair(self, pair: MarketPair) -> int:
        with self.db._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM market_pairs WHERE kalshi_market_id=? AND polymarket_market_id=?",
                (pair.kalshi_market_id, pair.polymarket_market_id),
            ).fetchone()
            if existing:
                conn.execute("""
                    UPDATE market_pairs SET match_confidence=?, match_reason=?,
                        price_gap=?, last_checked=?
                    WHERE id=?
                """, (pair.match_confidence, pair.match_reason,
                      pair.price_gap, _now(), existing["id"]))
                return existing["id"]
            else:
                sql = """
                    INSERT INTO market_pairs (kalshi_market_id, polymarket_market_id,
                        match_confidence, match_reason, price_gap, last_checked)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                cursor = conn.execute(self.db._returning_id(sql),
                    (pair.kalshi_market_id, pair.polymarket_market_id,
                     pair.match_confidence, pair.match_reason,
                     pair.price_gap, _now()))
                return self.db._last_id(cursor)

    def get_all_pairs(self) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            rows = conn.execute("""
                SELECT mp.*,
                    km.title as kalshi_title, km.yes_price as kalshi_yes,
                    km.no_price as kalshi_no, km.volume as kalshi_volume,
                    km.liquidity as kalshi_liquidity, km.category as kalshi_category,
                    km.close_time as kalshi_close_time,
                    km.platform_id as kalshi_platform_id,
                    pm.title as poly_title, pm.yes_price as poly_yes,
                    pm.no_price as poly_no, pm.volume as poly_volume,
                    pm.liquidity as poly_liquidity, pm.category as poly_category,
                    pm.close_time as poly_close_time,
                    pm.platform_id as poly_platform_id
                FROM market_pairs mp
                LEFT JOIN markets km ON mp.kalshi_market_id = km.id
                LEFT JOIN markets pm ON mp.polymarket_market_id = pm.id
                ORDER BY mp.price_gap DESC
            """).fetchall()
            return [dict(r) for r in rows]

    # ── Price Snapshots ──────────────────────────────────────

    def insert_snapshot(self, snapshot: PriceSnapshot) -> int:
        with self.db._connect() as conn:
            sql = """
                INSERT INTO price_snapshots (market_id, yes_price, no_price,
                    volume, open_interest, best_bid, best_ask, spread, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor = conn.execute(self.db._returning_id(sql), (
                snapshot.market_id, snapshot.yes_price, snapshot.no_price,
                snapshot.volume, snapshot.open_interest, snapshot.best_bid,
                snapshot.best_ask, snapshot.spread, _now(),
            ))
            return self.db._last_id(cursor)

    def insert_snapshots_batch(self, snapshots: List[PriceSnapshot]) -> int:
        """Batch insert price snapshots in a single connection."""
        if not snapshots:
            return 0
        with self.db._connect() as conn:
            now = _now()
            for s in snapshots:
                conn.execute("""
                    INSERT INTO price_snapshots (market_id, yes_price, no_price,
                        volume, open_interest, best_bid, best_ask, spread, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s.market_id, s.yes_price, s.no_price,
                    s.volume, s.open_interest, s.best_bid,
                    s.best_ask, s.spread, now,
                ))
            return len(snapshots)

    def get_price_history(self, market_id: int,
                          limit: int = 500) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM price_snapshots
                WHERE market_id=?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (market_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_latest_snapshot(self, market_id: int) -> Optional[Dict[str, Any]]:
        with self.db._connect() as conn:
            row = conn.execute("""
                SELECT * FROM price_snapshots
                WHERE market_id=?
                ORDER BY timestamp DESC LIMIT 1
            """, (market_id,)).fetchone()
            return dict(row) if row else None

    # ── Analysis Results ─────────────────────────────────────

    def insert_analysis(self, result: AnalysisResult) -> int:
        with self.db._connect() as conn:
            sql = """
                INSERT INTO analysis_results (pair_id, kalshi_yes, poly_yes,
                    price_gap, gap_direction, llm_analysis, risk_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            cursor = conn.execute(self.db._returning_id(sql), (
                result.pair_id, result.kalshi_yes, result.poly_yes,
                result.price_gap, result.gap_direction,
                result.llm_analysis, result.risk_score,
            ))
            return self.db._last_id(cursor)

    def get_latest_analyses(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            rows = conn.execute("""
                SELECT ar.*, mp.kalshi_market_id, mp.polymarket_market_id,
                    km.title as kalshi_title, pm.title as poly_title
                FROM analysis_results ar
                LEFT JOIN market_pairs mp ON ar.pair_id = mp.id
                LEFT JOIN markets km ON mp.kalshi_market_id = km.id
                LEFT JOIN markets pm ON mp.polymarket_market_id = pm.id
                ORDER BY ar.created_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ── Alerts ───────────────────────────────────────────────

    def insert_alert(self, alert: Alert) -> int:
        with self.db._connect() as conn:
            sql = """
                INSERT INTO alerts (alert_type, severity, market_id, pair_id,
                    title, message, data, acknowledged)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor = conn.execute(self.db._returning_id(sql), (
                alert.alert_type, alert.severity, alert.market_id,
                alert.pair_id, alert.title, alert.message,
                alert.data, 0,
            ))
            return self.db._last_id(cursor)

    def get_alerts(self, alert_type: Optional[str] = None,
                   acknowledged: Optional[bool] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            query = "SELECT a.*, m.title as market_title FROM alerts a LEFT JOIN markets m ON a.market_id = m.id WHERE 1=1"
            params: list = []
            if alert_type:
                query += " AND a.alert_type=?"
                params.append(alert_type)
            if acknowledged is not None:
                query += " AND a.acknowledged=?"
                params.append(1 if acknowledged else 0)
            query += " ORDER BY a.triggered_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def insert_alerts_batch(self, alerts: List[Alert]) -> int:
        """Batch insert alerts in a single connection."""
        if not alerts:
            return 0
        with self.db._connect() as conn:
            for alert in alerts:
                conn.execute("""
                    INSERT INTO alerts (alert_type, severity, market_id, pair_id,
                        title, message, data, acknowledged)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    alert.alert_type, alert.severity, alert.market_id,
                    alert.pair_id, alert.title, alert.message,
                    alert.data, 0,
                ))
            return len(alerts)

    def acknowledge_alert(self, alert_id: int) -> None:
        with self.db._connect() as conn:
            conn.execute("UPDATE alerts SET acknowledged=1 WHERE id=?", (alert_id,))

    # ── Insights ─────────────────────────────────────────────

    def insert_insight(self, insight: Insight) -> int:
        with self.db._connect() as conn:
            sql = """
                INSERT INTO insights (report_type, title, content,
                    markets_covered, model_used, tokens_used)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            cursor = conn.execute(self.db._returning_id(sql), (
                insight.report_type, insight.title, insight.content,
                insight.markets_covered, insight.model_used,
                insight.tokens_used,
            ))
            return self.db._last_id(cursor)

    def get_insights(self, report_type: Optional[str] = None,
                     limit: int = 20) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            if report_type:
                rows = conn.execute(
                    "SELECT * FROM insights WHERE report_type=? ORDER BY created_at DESC LIMIT ?",
                    (report_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM insights ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Agent Logs ───────────────────────────────────────────

    def insert_agent_log(self, log: AgentLog) -> int:
        with self.db._connect() as conn:
            sql = """
                INSERT INTO agent_logs (agent_name, status, started_at,
                    completed_at, duration_seconds, items_processed, summary, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor = conn.execute(self.db._returning_id(sql), (
                log.agent_name, log.status, log.started_at,
                log.completed_at, log.duration_seconds,
                log.items_processed, log.summary, log.error,
            ))
            return self.db._last_id(cursor)

    def get_agent_logs(self, agent_name: Optional[str] = None,
                       limit: int = 50) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            if agent_name:
                rows = conn.execute(
                    "SELECT * FROM agent_logs WHERE agent_name=? ORDER BY started_at DESC LIMIT ?",
                    (agent_name, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM agent_logs ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_latest_agent_run(self, agent_name: str) -> Optional[Dict[str, Any]]:
        with self.db._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_logs WHERE agent_name=? ORDER BY started_at DESC LIMIT 1",
                (agent_name,),
            ).fetchone()
            return dict(row) if row else None

    # ── Stats ────────────────────────────────────────────────

    def get_market_counts(self) -> Dict[str, int]:
        with self.db._connect() as conn:
            rows = conn.execute(
                "SELECT platform, COUNT(*) as cnt FROM markets WHERE status='active' GROUP BY platform"
            ).fetchall()
            return {r["platform"]: r["cnt"] for r in rows}

    def get_alert_counts_by_type(self) -> Dict[str, int]:
        with self.db._connect() as conn:
            rows = conn.execute(
                "SELECT alert_type, COUNT(*) as cnt FROM alerts GROUP BY alert_type"
            ).fetchall()
            return {r["alert_type"]: r["cnt"] for r in rows}

    # ── Traders ───────────────────────────────────────────────

    def upsert_trader(self, trader: Trader) -> int:
        """Insert or update a trader, returning their ID.

        Uses COALESCE to preserve existing non-null data when the incoming
        Trader object has NULL/empty fields (e.g. from whale agent creating
        a minimal profile).
        """
        with self.db._connect() as conn:
            conn.execute("""
                INSERT INTO traders (proxy_wallet, user_name, profile_image,
                    x_username, verified_badge, total_pnl, total_volume,
                    portfolio_value, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(proxy_wallet) DO UPDATE SET
                    user_name = CASE WHEN excluded.user_name != ''
                                THEN excluded.user_name ELSE traders.user_name END,
                    profile_image = CASE WHEN excluded.profile_image != ''
                                THEN excluded.profile_image ELSE traders.profile_image END,
                    x_username = CASE WHEN excluded.x_username != ''
                                THEN excluded.x_username ELSE traders.x_username END,
                    verified_badge = CASE WHEN excluded.verified_badge != 0
                                THEN excluded.verified_badge ELSE traders.verified_badge END,
                    total_pnl = COALESCE(excluded.total_pnl, traders.total_pnl),
                    total_volume = COALESCE(excluded.total_volume, traders.total_volume),
                    portfolio_value = COALESCE(excluded.portfolio_value, traders.portfolio_value),
                    last_updated = excluded.last_updated
            """, (
                trader.proxy_wallet, trader.user_name, trader.profile_image,
                trader.x_username, 1 if trader.verified_badge else 0,
                trader.total_pnl, trader.total_volume,
                trader.portfolio_value, _now(),
            ))
            row = conn.execute(
                "SELECT id FROM traders WHERE proxy_wallet=?",
                (trader.proxy_wallet,),
            ).fetchone()
            return row["id"]

    def upsert_traders_batch(self, traders: List[Trader]) -> int:
        """Batch upsert traders in a single connection. Returns count upserted."""
        if not traders:
            return 0
        with self.db._connect() as conn:
            now = _now()
            for trader in traders:
                conn.execute("""
                    INSERT INTO traders (proxy_wallet, user_name, profile_image,
                        x_username, verified_badge, total_pnl, total_volume,
                        portfolio_value, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(proxy_wallet) DO UPDATE SET
                        user_name = CASE WHEN excluded.user_name != ''
                                    THEN excluded.user_name ELSE traders.user_name END,
                        profile_image = CASE WHEN excluded.profile_image != ''
                                    THEN excluded.profile_image ELSE traders.profile_image END,
                        x_username = CASE WHEN excluded.x_username != ''
                                    THEN excluded.x_username ELSE traders.x_username END,
                        verified_badge = CASE WHEN excluded.verified_badge != 0
                                    THEN excluded.verified_badge ELSE traders.verified_badge END,
                        total_pnl = COALESCE(excluded.total_pnl, traders.total_pnl),
                        total_volume = COALESCE(excluded.total_volume, traders.total_volume),
                        portfolio_value = COALESCE(excluded.portfolio_value, traders.portfolio_value),
                        last_updated = excluded.last_updated
                """, (
                    trader.proxy_wallet, trader.user_name, trader.profile_image,
                    trader.x_username, 1 if trader.verified_badge else 0,
                    trader.total_pnl, trader.total_volume,
                    trader.portfolio_value, now,
                ))
            return len(traders)

    def get_traders_by_wallets(self, wallets: List[str]) -> Dict[str, Dict[str, Any]]:
        """Batch lookup traders by wallet addresses. Returns {wallet: trader_dict}."""
        if not wallets:
            return {}
        with self.db._connect() as conn:
            result = {}
            for wallet in wallets:
                row = conn.execute(
                    "SELECT * FROM traders WHERE proxy_wallet=?", (wallet,),
                ).fetchone()
                if row:
                    result[wallet] = dict(row)
            return result

    def get_trader_by_wallet(self, wallet: str) -> Optional[Dict[str, Any]]:
        with self.db._connect() as conn:
            row = conn.execute(
                "SELECT * FROM traders WHERE proxy_wallet=?", (wallet,),
            ).fetchone()
            return dict(row) if row else None

    def get_trader_by_id(self, trader_id: int) -> Optional[Dict[str, Any]]:
        with self.db._connect() as conn:
            row = conn.execute(
                "SELECT * FROM traders WHERE id=?", (trader_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_top_traders(self, order_by: str = "total_pnl",
                        limit: int = 50) -> List[Dict[str, Any]]:
        """Get top traders sorted by PNL or volume."""
        _VALID_SORT = {"total_pnl", "total_volume"}
        col = order_by if order_by in _VALID_SORT else "total_pnl"
        with self.db._connect() as conn:
            rows = conn.execute(f"""
                SELECT * FROM traders
                WHERE {col} IS NOT NULL
                ORDER BY {col} DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def search_traders(self, query: str) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM traders WHERE user_name {self.db._like} ? ORDER BY total_pnl DESC",
                (f"%{query}%",),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_portfolio_value(self, wallet: str, value: float) -> None:
        """Update only the portfolio value for a trader."""
        with self.db._connect() as conn:
            conn.execute(
                "UPDATE traders SET portfolio_value=?, last_updated=? WHERE proxy_wallet=?",
                (value, _now(), wallet),
            )

    # ── Whale Trades ──────────────────────────────────────────

    def insert_whale_trade(self, trade: WhaleTrade) -> int:
        """Insert a whale trade (skip if duplicate tx hash)."""
        with self.db._connect() as conn:
            try:
                params = (
                    trade.trader_id, trade.proxy_wallet, trade.condition_id,
                    trade.market_title, trade.side, trade.size, trade.price,
                    trade.usdc_size, trade.outcome, trade.outcome_index,
                    trade.transaction_hash, trade.trade_timestamp,
                    trade.event_slug, _now(),
                )
                if self.db._backend == "postgres":
                    sql = """
                        INSERT INTO whale_trades (
                            trader_id, proxy_wallet, condition_id, market_title,
                            side, size, price, usdc_size, outcome, outcome_index,
                            transaction_hash, trade_timestamp, event_slug, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (transaction_hash) DO NOTHING
                        RETURNING id
                    """
                else:
                    sql = """
                        INSERT OR IGNORE INTO whale_trades (
                            trader_id, proxy_wallet, condition_id, market_title,
                            side, size, price, usdc_size, outcome, outcome_index,
                            transaction_hash, trade_timestamp, event_slug, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                cursor = conn.execute(sql, params)
                if self.db._backend == "postgres":
                    row = cursor.fetchone()
                    return row["id"] if row else 0
                return cursor.lastrowid or 0
            except Exception:
                return 0

    def insert_whale_trades_batch(self, trades: List[WhaleTrade]) -> int:
        """Batch insert whale trades in a single connection. Skips duplicates."""
        if not trades:
            return 0
        inserted = 0
        with self.db._connect() as conn:
            now = _now()
            for trade in trades:
                try:
                    params = (
                        trade.trader_id, trade.proxy_wallet, trade.condition_id,
                        trade.market_title, trade.side, trade.size, trade.price,
                        trade.usdc_size, trade.outcome, trade.outcome_index,
                        trade.transaction_hash, trade.trade_timestamp,
                        trade.event_slug, now,
                    )
                    if self.db._backend == "postgres":
                        sql = """
                            INSERT INTO whale_trades (
                                trader_id, proxy_wallet, condition_id, market_title,
                                side, size, price, usdc_size, outcome, outcome_index,
                                transaction_hash, trade_timestamp, event_slug, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT (transaction_hash) DO NOTHING
                            RETURNING id
                        """
                        cursor = conn.execute(sql, params)
                        row = cursor.fetchone()
                        if row:
                            inserted += 1
                    else:
                        sql = """
                            INSERT OR IGNORE INTO whale_trades (
                                trader_id, proxy_wallet, condition_id, market_title,
                                side, size, price, usdc_size, outcome, outcome_index,
                                transaction_hash, trade_timestamp, event_slug, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        cursor = conn.execute(sql, params)
                        if cursor.lastrowid:
                            inserted += 1
                except Exception:
                    continue
        return inserted

    def get_whale_trades(self, limit: int = 100,
                         min_size: float = 0,
                         side: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            query = """
                SELECT wt.*, t.user_name, t.profile_image, t.verified_badge
                FROM whale_trades wt
                LEFT JOIN traders t ON wt.trader_id = t.id
                WHERE wt.usdc_size >= ?
            """
            params: list = [min_size]
            if side:
                query += " AND wt.side=?"
                params.append(side)
            query += " ORDER BY wt.trade_timestamp DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_whale_trades_by_trader(self, trader_id: int,
                                    limit: int = 50) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM whale_trades
                WHERE trader_id=?
                ORDER BY trade_timestamp DESC LIMIT ?
            """, (trader_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_whale_trade_count_since(self, hours: int = 24) -> int:
        """Count whale trades in the last N hours."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self.db._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM whale_trades WHERE created_at >= ?",
                (cutoff,),
            ).fetchone()
            return row["cnt"] if row else 0

    def get_first_time_trades(
        self,
        categories: Optional[List[str]] = None,
        min_size: float = 5000,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get each trader's earliest whale trade, filtered by category and min size.

        Returns first-time predictions where the trader's debut trade
        meets the size threshold and falls in specified market categories.
        """
        if not categories:
            categories = ["Politics", "Tech", "Finance"]

        placeholders = ",".join(["?"] * len(categories))
        with self.db._connect() as conn:
            rows = conn.execute(f"""
                WITH first_trades AS (
                    SELECT trader_id, MIN(trade_timestamp) as first_ts
                    FROM whale_trades
                    GROUP BY trader_id
                )
                SELECT wt.*, t.user_name, t.profile_image, t.verified_badge,
                       t.first_seen, m.category, m.subcategory, m.title as market_name
                FROM whale_trades wt
                JOIN first_trades ft
                    ON wt.trader_id = ft.trader_id
                    AND wt.trade_timestamp = ft.first_ts
                LEFT JOIN traders t ON wt.trader_id = t.id
                LEFT JOIN markets m
                    ON wt.condition_id = m.platform_id
                    AND m.platform = 'polymarket'
                WHERE wt.usdc_size >= ?
                  AND m.category IN ({placeholders})
                ORDER BY wt.trade_timestamp DESC
                LIMIT ?
            """, (min_size, *categories, limit)).fetchall()
            return [dict(r) for r in rows]

    # ── Trader Positions ──────────────────────────────────────

    def insert_trader_position(self, pos: TraderPosition) -> int:
        with self.db._connect() as conn:
            sql = """
                INSERT INTO trader_positions (
                    trader_id, proxy_wallet, condition_id, market_title,
                    outcome, size, avg_price, initial_value, current_value,
                    cash_pnl, percent_pnl, realized_pnl, cur_price,
                    redeemable, event_slug)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor = conn.execute(self.db._returning_id(sql), (
                pos.trader_id, pos.proxy_wallet, pos.condition_id,
                pos.market_title, pos.outcome, pos.size, pos.avg_price,
                pos.initial_value, pos.current_value, pos.cash_pnl,
                pos.percent_pnl, pos.realized_pnl, pos.cur_price,
                1 if pos.redeemable else 0, pos.event_slug,
            ))
            return self.db._last_id(cursor)

    def get_trader_positions(self, trader_id: int,
                             limit: int = 100) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM trader_positions
                WHERE trader_id=?
                ORDER BY snapshot_time DESC, current_value DESC
                LIMIT ?
            """, (trader_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_latest_trader_positions(self, trader_id: int) -> List[Dict[str, Any]]:
        """Get the most recent position snapshot for a trader."""
        with self.db._connect() as conn:
            latest_time = conn.execute("""
                SELECT MAX(snapshot_time) as t FROM trader_positions
                WHERE trader_id=?
            """, (trader_id,)).fetchone()
            if not latest_time or not latest_time["t"]:
                return []
            rows = conn.execute("""
                SELECT * FROM trader_positions
                WHERE trader_id=? AND snapshot_time=?
                ORDER BY current_value DESC
            """, (trader_id, latest_time["t"])).fetchall()
            return [dict(r) for r in rows]

    # ── Trader Watchlist ──────────────────────────────────────

    def add_to_watchlist(self, trader_id: int) -> bool:
        """Add a trader to the watchlist. Returns True if added, False if already on list."""
        with self.db._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO trader_watchlist (trader_id, created_at) VALUES (?, ?)",
                    (trader_id, _now()),
                )
                return True
            except Exception as e:
                err_str = str(e).lower()
                if "unique" in err_str or "duplicate" in err_str:
                    return False
                raise

    def remove_from_watchlist(self, trader_id: int) -> None:
        """Remove a trader from the watchlist."""
        with self.db._connect() as conn:
            conn.execute(
                "DELETE FROM trader_watchlist WHERE trader_id=?",
                (trader_id,),
            )

    def get_watchlist(self) -> List[Dict[str, Any]]:
        """Get all watched traders with their full profile details."""
        with self.db._connect() as conn:
            rows = conn.execute("""
                SELECT t.*, w.created_at as watched_since
                FROM trader_watchlist w
                JOIN traders t ON w.trader_id = t.id
                ORDER BY w.created_at DESC
            """).fetchall()
            return [dict(r) for r in rows]

    def is_on_watchlist(self, trader_id: int) -> bool:
        """Check if a trader is on the watchlist."""
        with self.db._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM trader_watchlist WHERE trader_id=?",
                (trader_id,),
            ).fetchone()
            return row is not None

    def get_watchlist_ids(self) -> set:
        """Return the set of trader_ids currently on the watchlist (single query)."""
        with self.db._connect() as conn:
            rows = conn.execute(
                "SELECT trader_id FROM trader_watchlist"
            ).fetchall()
            return {r["trader_id"] for r in rows}

    # ── Trader Metrics ─────────────────────────────────────────

    def upsert_trader_metrics(self, m: TraderMetrics) -> int:
        """Insert or update computed metrics for a trader."""
        with self.db._connect() as conn:
            conn.execute("""
                INSERT INTO trader_metrics (
                    trader_id, proxy_wallet, win_rate, total_trades,
                    avg_trade_size, avg_hold_time_hours, largest_win,
                    largest_loss, sharpe_ratio, consistency_score,
                    conviction_score, active_markets, categories_traded,
                    primary_category, computed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trader_id) DO UPDATE SET
                    win_rate=excluded.win_rate,
                    total_trades=excluded.total_trades,
                    avg_trade_size=excluded.avg_trade_size,
                    avg_hold_time_hours=excluded.avg_hold_time_hours,
                    largest_win=excluded.largest_win,
                    largest_loss=excluded.largest_loss,
                    sharpe_ratio=excluded.sharpe_ratio,
                    consistency_score=excluded.consistency_score,
                    conviction_score=excluded.conviction_score,
                    active_markets=excluded.active_markets,
                    categories_traded=excluded.categories_traded,
                    primary_category=excluded.primary_category,
                    computed_at=excluded.computed_at
            """, (
                m.trader_id, m.proxy_wallet, m.win_rate, m.total_trades,
                m.avg_trade_size, m.avg_hold_time_hours, m.largest_win,
                m.largest_loss, m.sharpe_ratio, m.consistency_score,
                m.conviction_score, m.active_markets, m.categories_traded,
                m.primary_category, _now(),
            ))
            row = conn.execute(
                "SELECT id FROM trader_metrics WHERE trader_id=?",
                (m.trader_id,),
            ).fetchone()
            return row["id"] if row else 0

    def get_trader_metrics(self, trader_id: int) -> Optional[Dict[str, Any]]:
        with self.db._connect() as conn:
            row = conn.execute(
                "SELECT * FROM trader_metrics WHERE trader_id=?",
                (trader_id,),
            ).fetchone()
            return dict(row) if row else None

    # ── Trader Category P&L ────────────────────────────────────

    def upsert_trader_category_pnl_batch(
        self, rows: List[TraderCategoryPnl]
    ) -> int:
        """Batch upsert per-category P&L for a trader."""
        if not rows:
            return 0
        now = _now()
        with self.db._connect() as conn:
            for r in rows:
                conn.execute("""
                    INSERT INTO trader_category_pnl (
                        trader_id, category, pnl, volume,
                        trade_count, win_count, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(trader_id, category) DO UPDATE SET
                        pnl=excluded.pnl,
                        volume=excluded.volume,
                        trade_count=excluded.trade_count,
                        win_count=excluded.win_count,
                        computed_at=excluded.computed_at
                """, (
                    r.trader_id, r.category, r.pnl, r.volume,
                    r.trade_count, r.win_count, now,
                ))
            return len(rows)

    def get_trader_category_pnl(
        self, trader_id: int
    ) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trader_category_pnl WHERE trader_id=? ORDER BY volume DESC",
                (trader_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Trader Anomalies ───────────────────────────────────────

    def insert_trader_anomaly(self, a: TraderAnomaly) -> int:
        """Insert an anomaly (skip if duplicate type+market for this trader)."""
        with self.db._connect() as conn:
            try:
                if self.db._backend == "postgres":
                    sql = """
                        INSERT INTO trader_anomalies (
                            trader_id, proxy_wallet, anomaly_type, severity,
                            market_title, description, data, detected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (trader_id, anomaly_type, market_title)
                        DO NOTHING RETURNING id
                    """
                    cursor = conn.execute(sql, (
                        a.trader_id, a.proxy_wallet, a.anomaly_type,
                        a.severity, a.market_title, a.description,
                        a.data, _now(),
                    ))
                    row = cursor.fetchone()
                    return row["id"] if row else 0
                else:
                    sql = """
                        INSERT OR IGNORE INTO trader_anomalies (
                            trader_id, proxy_wallet, anomaly_type, severity,
                            market_title, description, data, detected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    cursor = conn.execute(sql, (
                        a.trader_id, a.proxy_wallet, a.anomaly_type,
                        a.severity, a.market_title, a.description,
                        a.data, _now(),
                    ))
                    return cursor.lastrowid or 0
            except Exception:
                return 0

    def insert_trader_anomalies_batch(self, anomalies: List[TraderAnomaly]) -> int:
        """Batch insert anomalies, skipping duplicates."""
        if not anomalies:
            return 0
        inserted = 0
        now = _now()
        with self.db._connect() as conn:
            for a in anomalies:
                try:
                    if self.db._backend == "postgres":
                        sql = """
                            INSERT INTO trader_anomalies (
                                trader_id, proxy_wallet, anomaly_type, severity,
                                market_title, description, data, detected_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT (trader_id, anomaly_type, market_title)
                            DO NOTHING RETURNING id
                        """
                        cursor = conn.execute(sql, (
                            a.trader_id, a.proxy_wallet, a.anomaly_type,
                            a.severity, a.market_title, a.description,
                            a.data, now,
                        ))
                        row = cursor.fetchone()
                        if row:
                            inserted += 1
                    else:
                        sql = """
                            INSERT OR IGNORE INTO trader_anomalies (
                                trader_id, proxy_wallet, anomaly_type, severity,
                                market_title, description, data, detected_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        cursor = conn.execute(sql, (
                            a.trader_id, a.proxy_wallet, a.anomaly_type,
                            a.severity, a.market_title, a.description,
                            a.data, now,
                        ))
                        if cursor.lastrowid:
                            inserted += 1
                except Exception:
                    continue
        return inserted

    def get_trader_anomalies(self, trader_id: int,
                              limit: int = 20) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM trader_anomalies
                WHERE trader_id=?
                ORDER BY detected_at DESC LIMIT ?
            """, (trader_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_recent_anomalies(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent anomalies across all traders with trader info."""
        with self.db._connect() as conn:
            rows = conn.execute("""
                SELECT ta.*, t.user_name, t.profile_image, t.verified_badge
                FROM trader_anomalies ta
                LEFT JOIN traders t ON ta.trader_id = t.id
                ORDER BY ta.detected_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def update_trader_intelligence(
        self, trader_id: int, *,
        win_rate: Optional[float] = None,
        total_trades: Optional[int] = None,
        avg_position_size: Optional[float] = None,
        active_positions: Optional[int] = None,
        trader_tier: Optional[str] = None,
        primary_category: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> None:
        """Update the denormalized intelligence fields on the traders table."""
        updates = []
        params: list = []
        if win_rate is not None:
            updates.append("win_rate=?")
            params.append(win_rate)
        if total_trades is not None:
            updates.append("total_trades=?")
            params.append(total_trades)
        if avg_position_size is not None:
            updates.append("avg_position_size=?")
            params.append(avg_position_size)
        if active_positions is not None:
            updates.append("active_positions=?")
            params.append(active_positions)
        if trader_tier is not None:
            updates.append("trader_tier=?")
            params.append(trader_tier)
        if primary_category is not None:
            updates.append("primary_category=?")
            params.append(primary_category)
        if tags is not None:
            updates.append("tags=?")
            params.append(tags)
        if not updates:
            return
        params.append(_now())
        params.append(trader_id)
        with self.db._connect() as conn:
            conn.execute(
                f"UPDATE traders SET {', '.join(updates)}, last_updated=? WHERE id=?",
                params,
            )

    def insert_trader_positions_batch(self, positions: List[TraderPosition]) -> int:
        """Batch insert trader position snapshots in a single connection."""
        if not positions:
            return 0
        now = _now()
        with self.db._connect() as conn:
            for pos in positions:
                conn.execute("""
                    INSERT INTO trader_positions (
                        trader_id, proxy_wallet, condition_id, market_title,
                        outcome, size, avg_price, initial_value, current_value,
                        cash_pnl, percent_pnl, realized_pnl, cur_price,
                        redeemable, event_slug, snapshot_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pos.trader_id, pos.proxy_wallet, pos.condition_id,
                    pos.market_title, pos.outcome, pos.size, pos.avg_price,
                    pos.initial_value, pos.current_value, pos.cash_pnl,
                    pos.percent_pnl, pos.realized_pnl, pos.cur_price,
                    1 if pos.redeemable else 0, pos.event_slug, now,
                ))
            return len(positions)

    def get_active_trader_ids(self, days: int = 30,
                               limit: int = 500) -> List[Dict[str, Any]]:
        """Get trader IDs that have whale trades in the last N days."""
        cutoff_ts = int(
            (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
        )
        with self.db._connect() as conn:
            rows = conn.execute("""
                SELECT DISTINCT wt.trader_id, t.proxy_wallet
                FROM whale_trades wt
                JOIN traders t ON wt.trader_id = t.id
                WHERE wt.trade_timestamp >= ?
                ORDER BY wt.trader_id
                LIMIT ?
            """, (cutoff_ts, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_trader_trades_summary(self, trader_id: int) -> Dict[str, Any]:
        """Get aggregated trade stats for a trader from whale_trades."""
        with self.db._connect() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    AVG(usdc_size) as avg_trade_size,
                    MAX(usdc_size) as max_trade_size,
                    SUM(usdc_size) as total_volume,
                    SUM(CASE WHEN side='BUY' THEN 1 ELSE 0 END) as buy_count,
                    SUM(CASE WHEN side='SELL' THEN 1 ELSE 0 END) as sell_count
                FROM whale_trades WHERE trader_id=?
            """, (trader_id,)).fetchone()
            return dict(row) if row else {}

    def get_trader_trades_with_categories(
        self, trader_id: int
    ) -> List[Dict[str, Any]]:
        """Get whale trades for a trader, joined with market category info."""
        with self.db._connect() as conn:
            rows = conn.execute("""
                SELECT wt.*, m.category, m.subcategory, m.status as market_status
                FROM whale_trades wt
                LEFT JOIN markets m
                    ON wt.condition_id = m.platform_id
                    AND m.platform = 'polymarket'
                WHERE wt.trader_id=?
                ORDER BY wt.trade_timestamp DESC
            """, (trader_id,)).fetchall()
            return [dict(r) for r in rows]
