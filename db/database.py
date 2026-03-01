"""Database manager with dual SQLite / PostgreSQL (Neon) backend.

When DATABASE_URL is provided, uses PostgreSQL via psycopg2.
Otherwise, falls back to SQLite for local development.

The _PgConnectionWrapper class bridges psycopg2's cursor-based API
to match sqlite3's conn.execute() pattern, so queries.py needs
minimal changes.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Optional
import sqlite3


# ---------------------------------------------------------------------------
# PostgreSQL connection wrapper
# ---------------------------------------------------------------------------

class _PgConnectionWrapper:
    """Wraps a psycopg2 connection to match sqlite3's conn.execute() API.

    sqlite3 connections expose .execute(sql, params) directly, returning
    a cursor. psycopg2 requires creating a cursor first. This wrapper
    provides the same interface so queries.py works unchanged.

    Also translates ``?`` placeholders (sqlite3) to ``%s`` (psycopg2).
    """

    def __init__(self, pg_conn) -> None:
        self._conn = pg_conn

    def execute(self, sql: str, params=None):
        # Escape any pre-existing % (e.g. in LIKE patterns baked into SQL)
        # so psycopg2 doesn't treat them as format specifiers, then
        # replace ? placeholders with %s.
        escaped = sql.replace("%", "%%")
        translated = escaped.replace("?", "%s")
        cursor = self._conn.cursor()
        cursor.execute(translated, params or ())
        return cursor

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Database manager
# ---------------------------------------------------------------------------

class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None,
                 database_url: Optional[str] = None) -> None:
        self.database_url = database_url
        self.db_path = db_path

        if self.database_url:
            self._backend = "postgres"
        else:
            self._backend = "sqlite"
            if self.db_path:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._ensure_schema()

    # ── Connection ────────────────────────────────────────────

    @contextmanager
    def _connect(self):
        """Yield a connection-like object for the active backend.

        Both backends auto-commit on clean exit and rollback on exception.
        Callers should NOT call conn.commit() — it is handled here.
        """
        if self._backend == "postgres":
            import psycopg2
            from psycopg2.extras import RealDictCursor

            conn = psycopg2.connect(self.database_url,
                                    cursor_factory=RealDictCursor)
            wrapper = _PgConnectionWrapper(conn)
            try:
                yield wrapper
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        else:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    # ── Helpers for queries.py ────────────────────────────────

    def _returning_id(self, sql: str) -> str:
        """Append ``RETURNING id`` to an INSERT for PostgreSQL."""
        if self._backend == "postgres":
            return sql.rstrip() + " RETURNING id"
        return sql

    def _last_id(self, cursor) -> int:
        """Get the auto-generated id after an INSERT.

        PostgreSQL: reads from RETURNING clause via fetchone().
        SQLite: uses cursor.lastrowid.
        """
        if self._backend == "postgres":
            row = cursor.fetchone()
            if row is None:
                return 0
            return row["id"] if isinstance(row, dict) else row[0]
        return cursor.lastrowid

    @property
    def _like(self) -> str:
        """Return the appropriate LIKE operator for the backend.

        PostgreSQL LIKE is case-sensitive; ILIKE is case-insensitive.
        SQLite LIKE is already case-insensitive for ASCII.
        """
        return "ILIKE" if self._backend == "postgres" else "LIKE"

    # ── Schema ────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        if self._backend == "postgres":
            self._ensure_schema_postgres()
        else:
            self._ensure_schema_sqlite()

    def _ensure_schema_sqlite(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS markets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    platform_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT '',
                    subcategory TEXT DEFAULT '',
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
                CREATE INDEX IF NOT EXISTS idx_markets_category_sub
                    ON markets(category, subcategory);
            """)

            # Migration: add subcategory column to existing databases
            try:
                conn.execute("ALTER TABLE markets ADD COLUMN subcategory TEXT DEFAULT ''")
            except Exception:
                pass  # Column already exists

    def _ensure_schema_postgres(self) -> None:
        with self._connect() as conn:
            # Each CREATE TABLE is a separate execute() call because
            # psycopg2 doesn't have executescript().
            conn.execute("""
                CREATE TABLE IF NOT EXISTS markets (
                    id SERIAL PRIMARY KEY,
                    platform TEXT NOT NULL,
                    platform_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT '',
                    subcategory TEXT DEFAULT '',
                    status TEXT DEFAULT 'active',
                    yes_price DOUBLE PRECISION,
                    no_price DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    liquidity DOUBLE PRECISION,
                    close_time TEXT,
                    url TEXT DEFAULT '',
                    last_updated TEXT,
                    raw_data TEXT,
                    UNIQUE(platform, platform_id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_pairs (
                    id SERIAL PRIMARY KEY,
                    kalshi_market_id INTEGER REFERENCES markets(id),
                    polymarket_market_id INTEGER REFERENCES markets(id),
                    match_confidence DOUBLE PRECISION DEFAULT 0.0,
                    match_reason TEXT DEFAULT '',
                    price_gap DOUBLE PRECISION,
                    created_at TEXT DEFAULT '',
                    last_checked TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_snapshots (
                    id SERIAL PRIMARY KEY,
                    market_id INTEGER NOT NULL REFERENCES markets(id),
                    yes_price DOUBLE PRECISION,
                    no_price DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    open_interest DOUBLE PRECISION,
                    best_bid DOUBLE PRECISION,
                    best_ask DOUBLE PRECISION,
                    spread DOUBLE PRECISION,
                    timestamp TEXT DEFAULT ''
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id SERIAL PRIMARY KEY,
                    pair_id INTEGER REFERENCES market_pairs(id),
                    kalshi_yes DOUBLE PRECISION,
                    poly_yes DOUBLE PRECISION,
                    price_gap DOUBLE PRECISION,
                    gap_direction TEXT DEFAULT '',
                    llm_analysis TEXT,
                    risk_score DOUBLE PRECISION,
                    created_at TEXT DEFAULT ''
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id SERIAL PRIMARY KEY,
                    alert_type TEXT NOT NULL,
                    severity TEXT DEFAULT 'info',
                    market_id INTEGER REFERENCES markets(id),
                    pair_id INTEGER REFERENCES market_pairs(id),
                    title TEXT NOT NULL,
                    message TEXT DEFAULT '',
                    data TEXT,
                    acknowledged INTEGER DEFAULT 0,
                    triggered_at TEXT DEFAULT ''
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS insights (
                    id SERIAL PRIMARY KEY,
                    report_type TEXT DEFAULT 'briefing',
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    markets_covered INTEGER DEFAULT 0,
                    model_used TEXT DEFAULT '',
                    tokens_used INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT ''
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id SERIAL PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    duration_seconds DOUBLE PRECISION,
                    items_processed INTEGER DEFAULT 0,
                    summary TEXT DEFAULT '',
                    error TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS traders (
                    id SERIAL PRIMARY KEY,
                    proxy_wallet TEXT NOT NULL UNIQUE,
                    user_name TEXT DEFAULT '',
                    profile_image TEXT DEFAULT '',
                    x_username TEXT DEFAULT '',
                    verified_badge INTEGER DEFAULT 0,
                    total_pnl DOUBLE PRECISION,
                    total_volume DOUBLE PRECISION,
                    portfolio_value DOUBLE PRECISION,
                    first_seen TEXT DEFAULT '',
                    last_updated TEXT DEFAULT ''
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS whale_trades (
                    id SERIAL PRIMARY KEY,
                    trader_id INTEGER REFERENCES traders(id),
                    proxy_wallet TEXT NOT NULL,
                    condition_id TEXT DEFAULT '',
                    market_title TEXT DEFAULT '',
                    side TEXT DEFAULT '',
                    size DOUBLE PRECISION,
                    price DOUBLE PRECISION,
                    usdc_size DOUBLE PRECISION,
                    outcome TEXT DEFAULT '',
                    outcome_index INTEGER,
                    transaction_hash TEXT DEFAULT '',
                    trade_timestamp INTEGER,
                    event_slug TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    UNIQUE(transaction_hash)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS trader_positions (
                    id SERIAL PRIMARY KEY,
                    trader_id INTEGER REFERENCES traders(id),
                    proxy_wallet TEXT NOT NULL,
                    condition_id TEXT DEFAULT '',
                    market_title TEXT DEFAULT '',
                    outcome TEXT DEFAULT '',
                    size DOUBLE PRECISION,
                    avg_price DOUBLE PRECISION,
                    initial_value DOUBLE PRECISION,
                    current_value DOUBLE PRECISION,
                    cash_pnl DOUBLE PRECISION,
                    percent_pnl DOUBLE PRECISION,
                    realized_pnl DOUBLE PRECISION,
                    cur_price DOUBLE PRECISION,
                    redeemable INTEGER DEFAULT 0,
                    event_slug TEXT DEFAULT '',
                    snapshot_time TEXT DEFAULT ''
                )
            """)

            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_price_snapshots_market_time ON price_snapshots(market_id, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_markets_platform_status ON markets(platform, status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_triggered ON alerts(triggered_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_logs_name ON agent_logs(agent_name, started_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_traders_wallet ON traders(proxy_wallet)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_whale_trades_timestamp ON whale_trades(trade_timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_whale_trades_trader ON whale_trades(trader_id, trade_timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_whale_trades_size ON whale_trades(usdc_size)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trader_positions_trader ON trader_positions(trader_id, snapshot_time)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_markets_category_sub ON markets(category, subcategory)")
