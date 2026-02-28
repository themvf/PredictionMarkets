"""Named query functions for all database operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .database import DatabaseManager
from .models import (
    AgentLog, Alert, AnalysisResult, Insight,
    MarketPair, NormalizedMarket, PriceSnapshot,
    Trader, WhaleTrade, TraderPosition,
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
                    category, status, yes_price, no_price, volume, liquidity,
                    close_time, url, last_updated, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, platform_id) DO UPDATE SET
                    title=excluded.title,
                    description=excluded.description,
                    category=excluded.category,
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
                market.description, market.category, market.status,
                market.yes_price, market.no_price, market.volume,
                market.liquidity, market.close_time, market.url,
                _now(), market.raw_data,
            ))
            row = conn.execute(
                "SELECT id FROM markets WHERE platform=? AND platform_id=?",
                (market.platform, market.platform_id),
            ).fetchone()
            conn.commit()
            return row["id"]

    def get_all_markets(self, platform: Optional[str] = None,
                        status: str = "active") -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            if platform:
                rows = conn.execute(
                    "SELECT * FROM markets WHERE platform=? AND status=? ORDER BY volume DESC",
                    (platform, status),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM markets WHERE status=? ORDER BY volume DESC",
                    (status,),
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

    def search_markets(self, query: str) -> List[Dict[str, Any]]:
        with self.db._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM markets WHERE title LIKE ? AND status='active' ORDER BY volume DESC",
                (f"%{query}%",),
            ).fetchall()
            return [dict(r) for r in rows]

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
                conn.commit()
                return existing["id"]
            else:
                cursor = conn.execute("""
                    INSERT INTO market_pairs (kalshi_market_id, polymarket_market_id,
                        match_confidence, match_reason, price_gap, last_checked)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (pair.kalshi_market_id, pair.polymarket_market_id,
                      pair.match_confidence, pair.match_reason,
                      pair.price_gap, _now()))
                conn.commit()
                return cursor.lastrowid

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
            cursor = conn.execute("""
                INSERT INTO price_snapshots (market_id, yes_price, no_price,
                    volume, open_interest, best_bid, best_ask, spread, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot.market_id, snapshot.yes_price, snapshot.no_price,
                snapshot.volume, snapshot.open_interest, snapshot.best_bid,
                snapshot.best_ask, snapshot.spread, _now(),
            ))
            conn.commit()
            return cursor.lastrowid

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
            cursor = conn.execute("""
                INSERT INTO analysis_results (pair_id, kalshi_yes, poly_yes,
                    price_gap, gap_direction, llm_analysis, risk_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                result.pair_id, result.kalshi_yes, result.poly_yes,
                result.price_gap, result.gap_direction,
                result.llm_analysis, result.risk_score,
            ))
            conn.commit()
            return cursor.lastrowid

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
            cursor = conn.execute("""
                INSERT INTO alerts (alert_type, severity, market_id, pair_id,
                    title, message, data, acknowledged)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_type, alert.severity, alert.market_id,
                alert.pair_id, alert.title, alert.message,
                alert.data, 0,
            ))
            conn.commit()
            return cursor.lastrowid

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

    def acknowledge_alert(self, alert_id: int) -> None:
        with self.db._connect() as conn:
            conn.execute("UPDATE alerts SET acknowledged=1 WHERE id=?", (alert_id,))
            conn.commit()

    # ── Insights ─────────────────────────────────────────────

    def insert_insight(self, insight: Insight) -> int:
        with self.db._connect() as conn:
            cursor = conn.execute("""
                INSERT INTO insights (report_type, title, content,
                    markets_covered, model_used, tokens_used)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                insight.report_type, insight.title, insight.content,
                insight.markets_covered, insight.model_used,
                insight.tokens_used,
            ))
            conn.commit()
            return cursor.lastrowid

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
            cursor = conn.execute("""
                INSERT INTO agent_logs (agent_name, status, started_at,
                    completed_at, duration_seconds, items_processed, summary, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log.agent_name, log.status, log.started_at,
                log.completed_at, log.duration_seconds,
                log.items_processed, log.summary, log.error,
            ))
            conn.commit()
            return cursor.lastrowid

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
            conn.commit()
            return row["id"]

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
                "SELECT * FROM traders WHERE user_name LIKE ? ORDER BY total_pnl DESC",
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
            conn.commit()

    # ── Whale Trades ──────────────────────────────────────────

    def insert_whale_trade(self, trade: WhaleTrade) -> int:
        """Insert a whale trade (skip if duplicate tx hash)."""
        with self.db._connect() as conn:
            try:
                cursor = conn.execute("""
                    INSERT OR IGNORE INTO whale_trades (
                        trader_id, proxy_wallet, condition_id, market_title,
                        side, size, price, usdc_size, outcome, outcome_index,
                        transaction_hash, trade_timestamp, event_slug)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.trader_id, trade.proxy_wallet, trade.condition_id,
                    trade.market_title, trade.side, trade.size, trade.price,
                    trade.usdc_size, trade.outcome, trade.outcome_index,
                    trade.transaction_hash, trade.trade_timestamp,
                    trade.event_slug,
                ))
                conn.commit()
                return cursor.lastrowid or 0
            except Exception:
                return 0

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
        with self.db._connect() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as cnt FROM whale_trades
                WHERE created_at >= datetime('now', ?)
            """, (f"-{hours} hours",)).fetchone()
            return row["cnt"] if row else 0

    # ── Trader Positions ──────────────────────────────────────

    def insert_trader_position(self, pos: TraderPosition) -> int:
        with self.db._connect() as conn:
            cursor = conn.execute("""
                INSERT INTO trader_positions (
                    trader_id, proxy_wallet, condition_id, market_title,
                    outcome, size, avg_price, initial_value, current_value,
                    cash_pnl, percent_pnl, realized_pnl, cur_price,
                    redeemable, event_slug)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pos.trader_id, pos.proxy_wallet, pos.condition_id,
                pos.market_title, pos.outcome, pos.size, pos.avg_price,
                pos.initial_value, pos.current_value, pos.cash_pnl,
                pos.percent_pnl, pos.realized_pnl, pos.cur_price,
                1 if pos.redeemable else 0, pos.event_slug,
            ))
            conn.commit()
            return cursor.lastrowid

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
