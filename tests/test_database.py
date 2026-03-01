"""Tests for database schema creation and CRUD operations.

Supports both SQLite (default) and PostgreSQL backends.
Set DATABASE_URL env var to run tests against Neon PostgreSQL.
"""

import os
import tempfile
from pathlib import Path

import pytest

from db.database import DatabaseManager
from db.queries import MarketQueries
from db.models import (
    NormalizedMarket, PriceSnapshot, Alert, MarketPair,
    AnalysisResult, Insight, AgentLog, Trader, WhaleTrade,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def db(db_path):
    # Use TEST_DATABASE_URL (not DATABASE_URL) for intentional Postgres testing.
    # This prevents pytest from accidentally wiping production Neon data.
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url:
        mgr = DatabaseManager(database_url=database_url)
        yield mgr
        with mgr._connect() as conn:
            for table in [
                "trader_watchlist", "trader_positions",
                "whale_trades", "traders",
                "agent_logs", "insights", "alerts",
                "analysis_results", "price_snapshots",
                "market_pairs", "markets",
            ]:
                conn.execute(f"TRUNCATE {table} CASCADE")
    else:
        mgr = DatabaseManager(db_path=db_path)
        yield mgr
        try:
            with mgr._connect() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass


@pytest.fixture
def queries(db):
    return MarketQueries(db)


class TestDatabaseSchema:
    def test_schema_creates_all_tables(self, db):
        with db._connect() as conn:
            if db._backend == "postgres":
                rows = conn.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name"
                ).fetchall()
                table_names = {t["table_name"] for t in rows}
            else:
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
                table_names = {t["name"] for t in tables}

        expected = {
            "markets", "market_pairs", "price_snapshots",
            "analysis_results", "alerts", "insights", "agent_logs",
            "traders", "whale_trades", "trader_positions",
            "trader_watchlist",
        }
        assert expected.issubset(table_names)

    def test_schema_creates_indexes(self, db):
        with db._connect() as conn:
            if db._backend == "postgres":
                indexes = conn.execute(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = 'public' AND indexname LIKE ?",
                    ("idx_%",),
                ).fetchall()
                index_names = {i["indexname"] for i in indexes}
            else:
                indexes = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
                ).fetchall()
                index_names = {i["name"] for i in indexes}

        assert "idx_price_snapshots_market_time" in index_names
        assert "idx_markets_platform_status" in index_names
        assert "idx_alerts_triggered" in index_names

    def test_schema_idempotent(self, db):
        """Running _ensure_schema twice should not raise."""
        db._ensure_schema()
        db._ensure_schema()


class TestMarketQueries:
    def test_upsert_and_get_market(self, queries):
        market = NormalizedMarket(
            platform="kalshi",
            platform_id="TEST-MARKET-123",
            title="Will it rain tomorrow?",
            category="weather",
            yes_price=0.65,
            no_price=0.35,
            volume=10000,
        )
        market_id = queries.upsert_market(market)
        assert market_id > 0

        fetched = queries.get_market_by_id(market_id)
        assert fetched is not None
        assert fetched["title"] == "Will it rain tomorrow?"
        assert fetched["platform"] == "kalshi"

    def test_upsert_updates_existing(self, queries):
        market = NormalizedMarket(
            platform="kalshi", platform_id="TEST-1",
            title="Original", yes_price=0.50,
        )
        id1 = queries.upsert_market(market)

        market.title = "Updated"
        market.yes_price = 0.75
        id2 = queries.upsert_market(market)

        assert id1 == id2
        fetched = queries.get_market_by_id(id1)
        assert fetched["title"] == "Updated"
        assert fetched["yes_price"] == 0.75

    def test_get_all_markets(self, queries):
        for i in range(5):
            queries.upsert_market(NormalizedMarket(
                platform="kalshi", platform_id=f"M-{i}",
                title=f"Market {i}", volume=i * 100,
            ))
        markets = queries.get_all_markets(platform="kalshi")
        assert len(markets) == 5

    def test_search_markets(self, queries):
        queries.upsert_market(NormalizedMarket(
            platform="kalshi", platform_id="BTC-1",
            title="Will Bitcoin reach 100k?",
        ))
        queries.upsert_market(NormalizedMarket(
            platform="kalshi", platform_id="RAIN-1",
            title="Will it rain?",
        ))
        results = queries.search_markets("Bitcoin")
        assert len(results) == 1
        assert "Bitcoin" in results[0]["title"]


    def test_upsert_markets_batch(self, queries):
        markets = [
            NormalizedMarket(
                platform="polymarket", platform_id=f"BATCH-{i}",
                title=f"Batch Market {i}", volume=i * 100,
            )
            for i in range(10)
        ]
        count = queries.upsert_markets_batch(markets)
        assert count == 10

        all_markets = queries.get_all_markets(platform="polymarket")
        assert len(all_markets) == 10

    def test_upsert_markets_batch_updates(self, queries):
        markets = [
            NormalizedMarket(
                platform="polymarket", platform_id="BUPD-1",
                title="Original Title", yes_price=0.50,
            ),
        ]
        queries.upsert_markets_batch(markets)

        # Update with new price
        markets[0].title = "Updated Title"
        markets[0].yes_price = 0.80
        queries.upsert_markets_batch(markets)

        result = queries.search_markets("Updated Title")
        assert len(result) == 1
        assert result[0]["yes_price"] == 0.80

    def test_upsert_markets_batch_empty(self, queries):
        count = queries.upsert_markets_batch([])
        assert count == 0


class TestPriceSnapshots:
    def test_insert_and_get_history(self, queries):
        market_id = queries.upsert_market(NormalizedMarket(
            platform="kalshi", platform_id="SNAP-1", title="Test",
        ))
        for i in range(3):
            queries.insert_snapshot(PriceSnapshot(
                market_id=market_id, yes_price=0.5 + i * 0.01,
            ))
        history = queries.get_price_history(market_id)
        assert len(history) == 3

    def test_get_latest_snapshot(self, queries):
        market_id = queries.upsert_market(NormalizedMarket(
            platform="poly", platform_id="SNAP-2", title="Test",
        ))
        queries.insert_snapshot(PriceSnapshot(market_id=market_id, yes_price=0.40))
        queries.insert_snapshot(PriceSnapshot(market_id=market_id, yes_price=0.60))

        latest = queries.get_latest_snapshot(market_id)
        assert latest is not None
        assert latest["yes_price"] == 0.60


class TestAlerts:
    def test_insert_and_get_alerts(self, queries):
        alert = Alert(
            alert_type="price_move", severity="warning",
            title="Price spike", message="Big move up",
        )
        alert_id = queries.insert_alert(alert)
        assert alert_id > 0

        alerts = queries.get_alerts()
        assert len(alerts) == 1
        assert alerts[0]["title"] == "Price spike"

    def test_acknowledge_alert(self, queries):
        alert_id = queries.insert_alert(Alert(
            alert_type="test", title="Test alert", message="msg",
        ))
        queries.acknowledge_alert(alert_id)
        alerts = queries.get_alerts(acknowledged=True)
        assert len(alerts) == 1

    def test_filter_by_type(self, queries):
        queries.insert_alert(Alert(alert_type="price_move", title="PM", message="m"))
        queries.insert_alert(Alert(alert_type="arbitrage", title="Arb", message="m"))
        pm_alerts = queries.get_alerts(alert_type="price_move")
        assert len(pm_alerts) == 1


class TestAgentLogs:
    def test_insert_and_get_logs(self, queries):
        log = AgentLog(
            agent_name="discovery", status="success",
            duration_seconds=5.2, items_processed=100,
            summary="Found 100 markets",
        )
        queries.insert_agent_log(log)
        logs = queries.get_agent_logs(agent_name="discovery")
        assert len(logs) == 1
        assert logs[0]["items_processed"] == 100

    def test_get_latest_run(self, queries):
        queries.insert_agent_log(AgentLog(
            agent_name="collection", status="success", summary="First",
        ))
        queries.insert_agent_log(AgentLog(
            agent_name="collection", status="error", summary="Second",
        ))
        latest = queries.get_latest_agent_run("collection")
        assert latest["summary"] == "Second"


class TestInsights:
    def test_insert_and_get(self, queries):
        insight = Insight(
            report_type="briefing", title="Morning Brief",
            content="# Market Report\nAll is well.",
            markets_covered=50, model_used="gpt-4o",
        )
        queries.insert_insight(insight)
        insights = queries.get_insights()
        assert len(insights) == 1
        assert insights[0]["title"] == "Morning Brief"


class TestMarketPairs:
    def test_upsert_pair(self, queries):
        kid = queries.upsert_market(NormalizedMarket(
            platform="kalshi", platform_id="K1", title="Kalshi Market",
        ))
        pid = queries.upsert_market(NormalizedMarket(
            platform="polymarket", platform_id="P1", title="Poly Market",
        ))
        pair = MarketPair(
            kalshi_market_id=kid, polymarket_market_id=pid,
            match_confidence=0.85, match_reason="Same question",
            price_gap=0.05,
        )
        pair_id = queries.upsert_pair(pair)
        assert pair_id > 0

        pairs = queries.get_all_pairs()
        assert len(pairs) == 1
        assert pairs[0]["match_confidence"] == 0.85


class TestFirstTimeTrades:
    def test_returns_earliest_trade_per_trader(self, queries):
        # Create a polymarket market with category
        mid = queries.upsert_market(NormalizedMarket(
            platform="polymarket", platform_id="COND-POLITICS-1",
            title="Will X win?", category="Politics",
        ))
        # Create a trader
        tid = queries.upsert_trader(Trader(
            proxy_wallet="0xFIRSTTIME1", user_name="Alice",
        ))
        # Insert two trades — earlier and later
        queries.insert_whale_trade(WhaleTrade(
            trader_id=tid, proxy_wallet="0xFIRSTTIME1",
            condition_id="COND-POLITICS-1", market_title="Will X win?",
            side="BUY", usdc_size=10000, transaction_hash="tx-first-1",
            trade_timestamp=1000000,
        ))
        queries.insert_whale_trade(WhaleTrade(
            trader_id=tid, proxy_wallet="0xFIRSTTIME1",
            condition_id="COND-POLITICS-1", market_title="Will X win?",
            side="SELL", usdc_size=20000, transaction_hash="tx-second-1",
            trade_timestamp=2000000,
        ))

        results = queries.get_first_time_trades(categories=["Politics"])
        assert len(results) == 1
        assert results[0]["trade_timestamp"] == 1000000
        assert results[0]["user_name"] == "Alice"

    def test_filters_by_category(self, queries):
        # Politics market
        queries.upsert_market(NormalizedMarket(
            platform="polymarket", platform_id="COND-POL-2",
            title="Election Q", category="Politics",
        ))
        # Sports market (should be excluded)
        queries.upsert_market(NormalizedMarket(
            platform="polymarket", platform_id="COND-SPORT-1",
            title="NBA game", category="Sports",
        ))
        t1 = queries.upsert_trader(Trader(proxy_wallet="0xCAT-POL"))
        t2 = queries.upsert_trader(Trader(proxy_wallet="0xCAT-SPORT"))

        queries.insert_whale_trade(WhaleTrade(
            trader_id=t1, proxy_wallet="0xCAT-POL",
            condition_id="COND-POL-2", market_title="Election Q",
            side="BUY", usdc_size=8000, transaction_hash="tx-cat-pol",
            trade_timestamp=3000000,
        ))
        queries.insert_whale_trade(WhaleTrade(
            trader_id=t2, proxy_wallet="0xCAT-SPORT",
            condition_id="COND-SPORT-1", market_title="NBA game",
            side="BUY", usdc_size=9000, transaction_hash="tx-cat-sport",
            trade_timestamp=3000000,
        ))

        # Only Politics
        results = queries.get_first_time_trades(categories=["Politics"])
        assert len(results) == 1
        assert results[0]["category"] == "Politics"

        # Only Sports — should not appear with default Politics/Tech/Finance
        results = queries.get_first_time_trades(categories=["Sports"])
        assert len(results) == 1
        assert results[0]["category"] == "Sports"

    def test_filters_by_min_size(self, queries):
        queries.upsert_market(NormalizedMarket(
            platform="polymarket", platform_id="COND-TECH-1",
            title="AI milestone", category="Tech",
        ))
        tid = queries.upsert_trader(Trader(proxy_wallet="0xSIZE-TEST"))
        queries.insert_whale_trade(WhaleTrade(
            trader_id=tid, proxy_wallet="0xSIZE-TEST",
            condition_id="COND-TECH-1", market_title="AI milestone",
            side="BUY", usdc_size=3000, transaction_hash="tx-small",
            trade_timestamp=4000000,
        ))

        # $5K threshold should exclude the $3K trade
        results = queries.get_first_time_trades(categories=["Tech"], min_size=5000)
        assert len(results) == 0

        # $2K threshold should include it
        results = queries.get_first_time_trades(categories=["Tech"], min_size=2000)
        assert len(results) == 1


class TestWatchlist:
    def test_add_and_get_watchlist(self, queries):
        tid = queries.upsert_trader(Trader(
            proxy_wallet="0xWATCH1", user_name="WatchMe",
            total_pnl=5000.0,
        ))
        result = queries.add_to_watchlist(tid)
        assert result is True

        watchlist = queries.get_watchlist()
        assert len(watchlist) == 1
        assert watchlist[0]["user_name"] == "WatchMe"
        assert watchlist[0]["watched_since"] is not None

    def test_remove_from_watchlist(self, queries):
        tid = queries.upsert_trader(Trader(proxy_wallet="0xWATCH2"))
        queries.add_to_watchlist(tid)
        assert len(queries.get_watchlist()) == 1

        queries.remove_from_watchlist(tid)
        assert len(queries.get_watchlist()) == 0

    def test_duplicate_add_is_safe(self, queries):
        tid = queries.upsert_trader(Trader(proxy_wallet="0xWATCH3"))
        assert queries.add_to_watchlist(tid) is True
        assert queries.add_to_watchlist(tid) is False  # duplicate
        assert len(queries.get_watchlist()) == 1

    def test_is_on_watchlist(self, queries):
        tid = queries.upsert_trader(Trader(proxy_wallet="0xWATCH4"))
        assert queries.is_on_watchlist(tid) is False

        queries.add_to_watchlist(tid)
        assert queries.is_on_watchlist(tid) is True

        queries.remove_from_watchlist(tid)
        assert queries.is_on_watchlist(tid) is False
