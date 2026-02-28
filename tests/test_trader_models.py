"""Tests for trader/whale database operations and models."""

import pytest
from db.database import DatabaseManager
from db.queries import MarketQueries
from db.models import Trader, WhaleTrade, TraderPosition


@pytest.fixture
def db(tmp_path):
    mgr = DatabaseManager(tmp_path / "test.db")
    yield mgr
    try:
        with mgr._connect() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        pass


@pytest.fixture
def queries(db):
    return MarketQueries(db)


class TestTraders:
    def test_upsert_and_get_trader(self, queries):
        trader = Trader(
            proxy_wallet="0x1234567890abcdef1234567890abcdef12345678",
            user_name="TestTrader",
            total_pnl=15000.50,
            total_volume=500000.0,
        )
        trader_id = queries.upsert_trader(trader)
        assert trader_id > 0

        fetched = queries.get_trader_by_wallet(
            "0x1234567890abcdef1234567890abcdef12345678"
        )
        assert fetched is not None
        assert fetched["user_name"] == "TestTrader"
        assert fetched["total_pnl"] == 15000.50

    def test_upsert_updates_existing(self, queries):
        trader = Trader(
            proxy_wallet="0xabc",
            user_name="Original",
            total_pnl=100.0,
        )
        id1 = queries.upsert_trader(trader)
        trader.user_name = "Updated"
        trader.total_pnl = 200.0
        id2 = queries.upsert_trader(trader)
        assert id1 == id2
        fetched = queries.get_trader_by_id(id1)
        assert fetched["user_name"] == "Updated"
        assert fetched["total_pnl"] == 200.0

    def test_get_top_traders(self, queries):
        for i in range(5):
            queries.upsert_trader(Trader(
                proxy_wallet=f"0x{i:040x}",
                user_name=f"Trader{i}",
                total_pnl=float(i * 1000),
            ))
        top = queries.get_top_traders(order_by="total_pnl", limit=3)
        assert len(top) == 3
        assert top[0]["total_pnl"] == 4000.0

    def test_search_traders(self, queries):
        queries.upsert_trader(Trader(
            proxy_wallet="0xfoo", user_name="CryptoWhale"))
        queries.upsert_trader(Trader(
            proxy_wallet="0xbar", user_name="SmallFish"))
        results = queries.search_traders("Whale")
        assert len(results) == 1

    def test_get_trader_by_id(self, queries):
        tid = queries.upsert_trader(Trader(
            proxy_wallet="0xbyid", user_name="ByID"))
        fetched = queries.get_trader_by_id(tid)
        assert fetched is not None
        assert fetched["user_name"] == "ByID"


class TestWhaleTrades:
    def test_insert_whale_trade(self, queries):
        tid = queries.upsert_trader(Trader(
            proxy_wallet="0xwhale", user_name="Whale"))
        trade = WhaleTrade(
            trader_id=tid,
            proxy_wallet="0xwhale",
            market_title="Will BTC hit 100K?",
            side="BUY",
            usdc_size=25000.0,
            transaction_hash="0xhash123",
        )
        result = queries.insert_whale_trade(trade)
        assert result > 0

    def test_duplicate_tx_hash_ignored(self, queries):
        trade = WhaleTrade(
            proxy_wallet="0xwhale",
            transaction_hash="0xdup",
            usdc_size=10000.0,
        )
        queries.insert_whale_trade(trade)
        queries.insert_whale_trade(trade)  # should not raise
        trades = queries.get_whale_trades()
        assert len(trades) == 1

    def test_get_whale_trades_with_filters(self, queries):
        for size in [1000, 5000, 10000, 50000]:
            queries.insert_whale_trade(WhaleTrade(
                proxy_wallet="0x1",
                usdc_size=float(size),
                side="BUY" if size > 5000 else "SELL",
                transaction_hash=f"0x{size}",
            ))
        big_trades = queries.get_whale_trades(min_size=5000)
        assert len(big_trades) == 3  # 5000, 10000, 50000
        buy_trades = queries.get_whale_trades(side="BUY")
        assert len(buy_trades) == 2

    def test_get_whale_trades_by_trader(self, queries):
        tid = queries.upsert_trader(Trader(
            proxy_wallet="0xtrader1"))
        for i in range(3):
            queries.insert_whale_trade(WhaleTrade(
                trader_id=tid,
                proxy_wallet="0xtrader1",
                usdc_size=10000.0,
                transaction_hash=f"0xtt{i}",
            ))
        trades = queries.get_whale_trades_by_trader(tid)
        assert len(trades) == 3

    def test_whale_trade_count_since(self, queries):
        queries.insert_whale_trade(WhaleTrade(
            proxy_wallet="0x1",
            usdc_size=10000.0,
            transaction_hash="0xrecent",
        ))
        count = queries.get_whale_trade_count_since(24)
        assert count >= 1


class TestTraderPositions:
    def test_insert_and_get_positions(self, queries):
        tid = queries.upsert_trader(Trader(
            proxy_wallet="0xtrader"))
        pos = TraderPosition(
            trader_id=tid,
            proxy_wallet="0xtrader",
            market_title="Election 2028",
            outcome="Yes",
            current_value=5000.0,
            cash_pnl=1200.0,
        )
        queries.insert_trader_position(pos)
        positions = queries.get_trader_positions(tid)
        assert len(positions) == 1
        assert positions[0]["market_title"] == "Election 2028"

    def test_get_latest_positions(self, queries):
        tid = queries.upsert_trader(Trader(
            proxy_wallet="0xlatest"))
        pos = TraderPosition(
            trader_id=tid,
            proxy_wallet="0xlatest",
            market_title="Test Market",
            outcome="Yes",
            current_value=3000.0,
        )
        queries.insert_trader_position(pos)
        latest = queries.get_latest_trader_positions(tid)
        assert len(latest) == 1

    def test_empty_positions(self, queries):
        tid = queries.upsert_trader(Trader(
            proxy_wallet="0xempty"))
        latest = queries.get_latest_trader_positions(tid)
        assert len(latest) == 0
