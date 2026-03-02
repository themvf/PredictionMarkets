/** Agent metadata for the Agent Status page */
export const AGENTS = [
  {
    name: "discovery",
    label: "Market Discovery",
    description: "Fetches new markets from Polymarket and Kalshi",
    icon: "Search",
  },
  {
    name: "collection",
    label: "Price Collection",
    description: "Snapshots current prices and volume",
    icon: "BarChart3",
  },
  {
    name: "analysis",
    label: "Cross-Platform Analysis",
    description: "Finds arbitrage opportunities across platforms",
    icon: "GitCompare",
  },
  {
    name: "insight",
    label: "AI Insights",
    description: "Generates market briefings and reports",
    icon: "Brain",
  },
  {
    name: "trader",
    label: "Trader Tracker",
    description: "Monitors whale traders and positions",
    icon: "Users",
  },
] as const;

/** Alert severity levels with display colors */
export const SEVERITY_COLORS: Record<string, string> = {
  critical: "text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-950",
  warning: "text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-950",
  info: "text-blue-600 bg-blue-50 dark:text-blue-400 dark:bg-blue-950",
};

/** Market categories used across the app */
export const CATEGORIES = [
  "All",
  "Politics",
  "Sports",
  "Crypto",
  "Culture",
  "Weather",
  "Economics",
  "Tech",
  "Finance",
] as const;

/** Default pagination size */
export const PAGE_SIZE = 50;

/** Smart filter definitions for homepage */
export const SMART_FILTERS = [
  {
    key: "whale_favorites",
    label: "Whale Favorites",
    icon: "Waves",
    className: "border-cyan-400 text-cyan-400 hover:bg-cyan-400/10",
    activeClassName: "border-cyan-400 text-cyan-400 bg-cyan-400/20",
  },
  {
    key: "closing_soon",
    label: "Closing Soon",
    icon: "Clock",
    className: "border-orange-400 text-orange-400 hover:bg-orange-400/10",
    activeClassName: "border-orange-400 text-orange-400 bg-orange-400/20",
  },
  {
    key: "near_5050",
    label: "Near 50/50",
    icon: "Scale",
    className: "border-green-400 text-green-400 hover:bg-green-400/10",
    activeClassName: "border-green-400 text-green-400 bg-green-400/20",
  },
  {
    key: "high_arb",
    label: "High Arb Potential",
    icon: "TrendingUp",
    className: "border-purple-400 text-purple-400 hover:bg-purple-400/10",
    activeClassName: "border-purple-400 text-purple-400 bg-purple-400/20",
  },
  {
    key: "hottest_24h",
    label: "Hottest 24h",
    icon: "Flame",
    className: "border-red-400 text-red-400 hover:bg-red-400/10",
    activeClassName: "border-red-400 text-red-400 bg-red-400/20",
  },
] as const;
