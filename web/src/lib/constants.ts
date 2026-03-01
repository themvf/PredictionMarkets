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
