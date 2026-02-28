"""SQLite database manager with schema initialization.

Follows the FindingLogger pattern from codex_agent/storage.py:
- _ensure_schema() on init
- _connect() method for each operation
- 7 tables with indexes
"""

from __future__ import annotations

from pathlib import Path
import sqlite3


class DatabaseManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS markets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    platform_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT '',
                    status TEXT DEFAULT 'active',
                    yes_price REAL,
                    no_price REAL,
                    volume REAL,
                    liquidity REAL,
                    close_time TEXT,
                    url TEXT DEFAULT '',
                    last_updated TEXT,
                    raw_data TEXT,
                    UNIQUE(platform, platform_id)
                );

                CREATE TABLE IF NOT EXISTS market_pairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kalshi_market_id INTEGER REFERENCES markets(id),
                    polymarket_market_id INTEGER REFERENCES markets(id),
                    match_confidence REAL DEFAULT 0.0,
                    match_reason TEXT DEFAULT '',
                    price_gap REAL,
                    created_at TEXT DEFAULT (datetime('now')),
                    last_checked TEXT
                );

                CREATE TABLE IF NOT EXISTS price_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id INTEGER NOT NULL REFERENCES markets(id),
                    yes_price REAL,
                    no_price REAL,
                    volume REAL,
                    open_interest REAL,
                    best_bid REAL,
                    best_ask REAL,
                    spread REAL,
                    timestamp TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair_id INTEGER REFERENCES market_pairs(id),
                    kalshi_yes REAL,
                    poly_yes REAL,
                    price_gap REAL,
                    gap_direction TEXT DEFAULT '',
                    llm_analysis TEXT,
                    risk_score REAL,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    severity TEXT DEFAULT 'info',
                    market_id INTEGER REFERENCES markets(id),
                    pair_id INTEGER REFERENCES market_pairs(id),
                    title TEXT NOT NULL,
                    message TEXT DEFAULT '',
                    data TEXT,
                    acknowledged INTEGER DEFAULT 0,
                    triggered_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_type TEXT DEFAULT 'briefing',
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    markets_covered INTEGER DEFAULT 0,
                    model_used TEXT DEFAULT '',
                    tokens_used INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS agent_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    duration_seconds REAL,
                    items_processed INTEGER DEFAULT 0,
                    summary TEXT DEFAULT '',
                    error TEXT
                );

                -- Trader intelligence tables
                CREATE TABLE IF NOT EXISTS traders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proxy_wallet TEXT NOT NULL UNIQUE,
                    user_name TEXT DEFAULT '',
                    profile_image TEXT DEFAULT '',
                    x_username TEXT DEFAULT '',
                    verified_badge INTEGER DEFAULT 0,
                    total_pnl REAL,
                    total_volume REAL,
                    portfolio_value REAL,
                    first_seen TEXT DEFAULT (datetime('now')),
                    last_updated TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS whale_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trader_id INTEGER REFERENCES traders(id),
                    proxy_wallet TEXT NOT NULL,
                    condition_id TEXT DEFAULT '',
                    market_title TEXT DEFAULT '',
                    side TEXT DEFAULT '',
                    size REAL,
                    price REAL,
                    usdc_size REAL,
                    outcome TEXT DEFAULT '',
                    outcome_index INTEGER,
                    transaction_hash TEXT DEFAULT '',
                    trade_timestamp INTEGER,
                    event_slug TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(transaction_hash)
                );

                CREATE TABLE IF NOT EXISTS trader_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trader_id INTEGER REFERENCES traders(id),
                    proxy_wallet TEXT NOT NULL,
                    condition_id TEXT DEFAULT '',
                    market_title TEXT DEFAULT '',
                    outcome TEXT DEFAULT '',
                    size REAL,
                    avg_price REAL,
                    initial_value REAL,
                    current_value REAL,
                    cash_pnl REAL,
                    percent_pnl REAL,
                    realized_pnl REAL,
                    cur_price REAL,
                    redeemable INTEGER DEFAULT 0,
                    event_slug TEXT DEFAULT '',
                    snapshot_time TEXT DEFAULT (datetime('now'))
                );

                -- Performance indexes
                CREATE INDEX IF NOT EXISTS idx_price_snapshots_market_time
                    ON price_snapshots(market_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_markets_platform_status
                    ON markets(platform, status);
                CREATE INDEX IF NOT EXISTS idx_alerts_triggered
                    ON alerts(triggered_at);
                CREATE INDEX IF NOT EXISTS idx_agent_logs_name
                    ON agent_logs(agent_name, started_at);
                CREATE INDEX IF NOT EXISTS idx_traders_wallet
                    ON traders(proxy_wallet);
                CREATE INDEX IF NOT EXISTS idx_whale_trades_timestamp
                    ON whale_trades(trade_timestamp);
                CREATE INDEX IF NOT EXISTS idx_whale_trades_trader
                    ON whale_trades(trader_id, trade_timestamp);
                CREATE INDEX IF NOT EXISTS idx_whale_trades_size
                    ON whale_trades(usdc_size);
                CREATE INDEX IF NOT EXISTS idx_trader_positions_trader
                    ON trader_positions(trader_id, snapshot_time);
            """)
            conn.commit()
