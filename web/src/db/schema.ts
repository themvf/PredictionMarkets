/**
 * Drizzle ORM schema — mirrors the 11 PostgreSQL tables created by
 * db/database.py `_ensure_schema_postgres()`.
 *
 * This is read-only from the web app's perspective; the Python agents
 * own all writes except watchlist mutations and alert acknowledgements.
 */

import {
  pgTable,
  serial,
  text,
  integer,
  doublePrecision,
  index,
  unique,
} from "drizzle-orm/pg-core";

// ── Markets ────────────────────────────────────────────────

export const markets = pgTable(
  "markets",
  {
    id: serial("id").primaryKey(),
    platform: text("platform").notNull(),
    platformId: text("platform_id").notNull(),
    title: text("title").notNull(),
    description: text("description").default(""),
    category: text("category").default(""),
    subcategory: text("subcategory").default(""),
    status: text("status").default("active"),
    yesPrice: doublePrecision("yes_price"),
    noPrice: doublePrecision("no_price"),
    volume: doublePrecision("volume"),
    liquidity: doublePrecision("liquidity"),
    closeTime: text("close_time"),
    url: text("url").default(""),
    lastUpdated: text("last_updated"),
    rawData: text("raw_data"),
  },
  (t) => [
    unique("markets_platform_platform_id_key").on(t.platform, t.platformId),
    index("idx_markets_platform_status").on(t.platform, t.status),
    index("idx_markets_category_sub").on(t.category, t.subcategory),
  ]
);

// ── Market Pairs (cross-platform) ──────────────────────────

export const marketPairs = pgTable("market_pairs", {
  id: serial("id").primaryKey(),
  kalshiMarketId: integer("kalshi_market_id").references(() => markets.id),
  polymarketMarketId: integer("polymarket_market_id").references(
    () => markets.id
  ),
  matchConfidence: doublePrecision("match_confidence").default(0.0),
  matchReason: text("match_reason").default(""),
  priceGap: doublePrecision("price_gap"),
  createdAt: text("created_at").default(""),
  lastChecked: text("last_checked"),
});

// ── Price Snapshots ────────────────────────────────────────

export const priceSnapshots = pgTable(
  "price_snapshots",
  {
    id: serial("id").primaryKey(),
    marketId: integer("market_id")
      .notNull()
      .references(() => markets.id),
    yesPrice: doublePrecision("yes_price"),
    noPrice: doublePrecision("no_price"),
    volume: doublePrecision("volume"),
    openInterest: doublePrecision("open_interest"),
    bestBid: doublePrecision("best_bid"),
    bestAsk: doublePrecision("best_ask"),
    spread: doublePrecision("spread"),
    timestamp: text("timestamp").default(""),
  },
  (t) => [
    index("idx_price_snapshots_market_time").on(t.marketId, t.timestamp),
  ]
);

// ── Analysis Results ───────────────────────────────────────

export const analysisResults = pgTable("analysis_results", {
  id: serial("id").primaryKey(),
  pairId: integer("pair_id").references(() => marketPairs.id),
  kalshiYes: doublePrecision("kalshi_yes"),
  polyYes: doublePrecision("poly_yes"),
  priceGap: doublePrecision("price_gap"),
  gapDirection: text("gap_direction").default(""),
  llmAnalysis: text("llm_analysis"),
  riskScore: doublePrecision("risk_score"),
  createdAt: text("created_at").default(""),
});

// ── Alerts ─────────────────────────────────────────────────

export const alerts = pgTable(
  "alerts",
  {
    id: serial("id").primaryKey(),
    alertType: text("alert_type").notNull(),
    severity: text("severity").default("info"),
    marketId: integer("market_id").references(() => markets.id),
    pairId: integer("pair_id").references(() => marketPairs.id),
    title: text("title").notNull(),
    message: text("message").default(""),
    data: text("data"),
    acknowledged: integer("acknowledged").default(0),
    triggeredAt: text("triggered_at").default(""),
  },
  (t) => [index("idx_alerts_triggered").on(t.triggeredAt)]
);

// ── AI Insights ────────────────────────────────────────────

export const insights = pgTable("insights", {
  id: serial("id").primaryKey(),
  reportType: text("report_type").default("briefing"),
  title: text("title").notNull(),
  content: text("content").default(""),
  marketsCovered: integer("markets_covered").default(0),
  modelUsed: text("model_used").default(""),
  tokensUsed: integer("tokens_used").default(0),
  createdAt: text("created_at").default(""),
});

// ── Agent Logs ─────────────────────────────────────────────

export const agentLogs = pgTable(
  "agent_logs",
  {
    id: serial("id").primaryKey(),
    agentName: text("agent_name").notNull(),
    status: text("status").notNull(),
    startedAt: text("started_at"),
    completedAt: text("completed_at"),
    durationSeconds: doublePrecision("duration_seconds"),
    itemsProcessed: integer("items_processed").default(0),
    summary: text("summary").default(""),
    error: text("error"),
  },
  (t) => [index("idx_agent_logs_name").on(t.agentName, t.startedAt)]
);

// ── Traders ────────────────────────────────────────────────

export const traders = pgTable(
  "traders",
  {
    id: serial("id").primaryKey(),
    proxyWallet: text("proxy_wallet").notNull().unique(),
    userName: text("user_name").default(""),
    profileImage: text("profile_image").default(""),
    xUsername: text("x_username").default(""),
    verifiedBadge: integer("verified_badge").default(0),
    totalPnl: doublePrecision("total_pnl"),
    totalVolume: doublePrecision("total_volume"),
    portfolioValue: doublePrecision("portfolio_value"),
    firstSeen: text("first_seen").default(""),
    lastUpdated: text("last_updated").default(""),
  },
  (t) => [index("idx_traders_wallet").on(t.proxyWallet)]
);

// ── Whale Trades ───────────────────────────────────────────

export const whaleTrades = pgTable(
  "whale_trades",
  {
    id: serial("id").primaryKey(),
    traderId: integer("trader_id").references(() => traders.id),
    proxyWallet: text("proxy_wallet").notNull(),
    conditionId: text("condition_id").default(""),
    marketTitle: text("market_title").default(""),
    side: text("side").default(""),
    size: doublePrecision("size"),
    price: doublePrecision("price"),
    usdcSize: doublePrecision("usdc_size"),
    outcome: text("outcome").default(""),
    outcomeIndex: integer("outcome_index"),
    transactionHash: text("transaction_hash").default("").unique(),
    tradeTimestamp: integer("trade_timestamp"),
    eventSlug: text("event_slug").default(""),
    createdAt: text("created_at").default(""),
  },
  (t) => [
    index("idx_whale_trades_timestamp").on(t.tradeTimestamp),
    index("idx_whale_trades_trader").on(t.traderId, t.tradeTimestamp),
    index("idx_whale_trades_size").on(t.usdcSize),
  ]
);

// ── Trader Positions ───────────────────────────────────────

export const traderPositions = pgTable(
  "trader_positions",
  {
    id: serial("id").primaryKey(),
    traderId: integer("trader_id").references(() => traders.id),
    proxyWallet: text("proxy_wallet").notNull(),
    conditionId: text("condition_id").default(""),
    marketTitle: text("market_title").default(""),
    outcome: text("outcome").default(""),
    size: doublePrecision("size"),
    avgPrice: doublePrecision("avg_price"),
    initialValue: doublePrecision("initial_value"),
    currentValue: doublePrecision("current_value"),
    cashPnl: doublePrecision("cash_pnl"),
    percentPnl: doublePrecision("percent_pnl"),
    realizedPnl: doublePrecision("realized_pnl"),
    curPrice: doublePrecision("cur_price"),
    redeemable: integer("redeemable").default(0),
    eventSlug: text("event_slug").default(""),
    snapshotTime: text("snapshot_time").default(""),
  },
  (t) => [
    index("idx_trader_positions_trader").on(t.traderId, t.snapshotTime),
  ]
);

// ── Trader Watchlist ───────────────────────────────────────

export const traderWatchlist = pgTable("trader_watchlist", {
  id: serial("id").primaryKey(),
  traderId: integer("trader_id")
    .notNull()
    .references(() => traders.id)
    .unique(),
  notes: text("notes").default(""),
  createdAt: text("created_at").default(""),
});

// ── Inferred Types ─────────────────────────────────────────

export type Market = typeof markets.$inferSelect;
export type MarketPair = typeof marketPairs.$inferSelect;
export type PriceSnapshot = typeof priceSnapshots.$inferSelect;
export type AnalysisResult = typeof analysisResults.$inferSelect;
export type Alert = typeof alerts.$inferSelect;
export type Insight = typeof insights.$inferSelect;
export type AgentLog = typeof agentLogs.$inferSelect;
export type Trader = typeof traders.$inferSelect;
export type WhaleTrade = typeof whaleTrades.$inferSelect;
export type TraderPosition = typeof traderPositions.$inferSelect;
export type TraderWatchlistEntry = typeof traderWatchlist.$inferSelect;
