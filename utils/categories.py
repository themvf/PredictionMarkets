"""Category normalization and subcategory extraction.

Maps raw API category values (e.g. "US-current-affairs", "KXFED") to clean
display categories (e.g. "Politics", "Finance"), and extracts subcategories
from market titles using keyword matching.
"""

from __future__ import annotations

# ── Raw API category → Clean display category ─────────────────────
# Keys are lowercased for case-insensitive matching.

CATEGORY_MAP: dict[str, str] = {
    # Polymarket Gamma API values
    "us-current-affairs": "Politics",
    "politics": "Politics",
    "us politics": "Politics",
    "global-politics": "Politics",
    "geopolitics": "Politics",
    "sports": "Sports",
    "crypto": "Crypto",
    "cryptocurrency": "Crypto",
    "pop-culture": "Culture",
    "pop culture": "Culture",
    "culture": "Culture",
    "entertainment": "Culture",
    "tech": "Tech",
    "technology": "Tech",
    "ai": "Tech",
    "science": "Climate & Science",
    "climate": "Climate & Science",
    "climate & science": "Climate & Science",
    "weather": "Climate & Science",
    "finance": "Finance",
    "business": "Finance",
    "economics": "Economy",
    "economy": "Economy",
    "earnings": "Finance",
    "world": "World",
    "international": "World",
    "chess": "Sports",
    "esports": "Sports",
    "mentions": "Culture",
    "breaking": "Breaking",
    "trending": "Trending",
    "new": "New",
    # Kalshi series tickers
    "kxmidterm": "Politics",
    "kxelection": "Politics",
    "kxpresidential": "Politics",
    "kxsenate": "Politics",
    "kxhouse": "Politics",
    "kxfed": "Economy",
    "kxcpi": "Economy",
    "kxgdp": "Economy",
    "kxjobs": "Economy",
    "kxrates": "Economy",
    "kxearnings": "Finance",
    "kxbtc": "Crypto",
    "kxeth": "Crypto",
    "kxsol": "Crypto",
    "kxnfl": "Sports",
    "kxnba": "Sports",
    "kxmlb": "Sports",
    "kxsoccer": "Sports",
    "kxmma": "Sports",
    "kxufc": "Sports",
    "kxweather": "Climate & Science",
    "kxtemp": "Climate & Science",
    "kxhurricane": "Climate & Science",
    "kxai": "Tech",
    "kxtech": "Tech",
    "kxmovies": "Culture",
    "kxtv": "Culture",
    "kxmusic": "Culture",
    "kxoscar": "Culture",
}

# ── Series slug prefix → Clean display category ──────────────────
# Polymarket's modern markets use seriesSlug instead of category.
# Matched by prefix: "aapl-neg-risk-weekly" starts with "aapl" → Finance.

SERIES_PREFIX_MAP: dict[str, str] = {
    # Sports
    "premier-league": "Sports",
    "la-liga": "Sports",
    "bundesliga": "Sports",
    "serie-a": "Sports",
    "champions-league": "Sports",
    "europa-league": "Sports",
    "europa-conference": "Sports",
    "nba": "Sports",
    "nfl": "Sports",
    "mlb": "Sports",
    "nhl": "Sports",
    "atp": "Sports",
    "wta": "Sports",
    "counter-strike": "Sports",
    "league-of-legends": "Sports",
    "dota": "Sports",
    "valorant": "Sports",
    "ufc": "Sports",
    "f1-": "Sports",
    "copa-america": "Sports",
    "rugby": "Sports",
    "cricket": "Sports",
    "ncaa": "Sports",
    "fifa": "Sports",
    # Finance / Equities — stock tickers
    "aapl": "Finance",
    "tsla": "Finance",
    "msft": "Finance",
    "nvda": "Finance",
    "goog": "Finance",
    "googl": "Finance",
    "amzn": "Finance",
    "meta-": "Finance",
    "spy-": "Finance",
    "qqq-": "Finance",
    "nflx": "Finance",
    "coin-": "Finance",
    "dis-": "Finance",
    "bac-": "Finance",
    "jpm-": "Finance",
    "pltr": "Finance",
    "avgo": "Finance",
    "crwd": "Finance",
    "cost": "Finance",
    "adbe": "Finance",
    "tgt-": "Finance",
    "anf-": "Finance",
    "gtlb": "Finance",
    "mrx-": "Finance",
    "snap-": "Finance",
    "uber-": "Finance",
    "abnb": "Finance",
    "shop": "Finance",
    "roku": "Finance",
    "sq-": "Finance",
    "pypl": "Finance",
    "intc": "Finance",
    "amd-": "Finance",
    "mu-": "Finance",
    "arm-": "Finance",
    "smci": "Finance",
    # Finance / Equities — company names (seriesSlug uses full names)
    "nvidia-": "Finance",
    "palantir-": "Finance",
    "broadcom-": "Finance",
    "tesla-": "Finance",
    "apple-": "Finance",
    "microsoft-": "Finance",
    "amazon-": "Finance",
    "alphabet-": "Finance",
    "crowdstrike-": "Finance",
    "costco-": "Finance",
    "adobe-": "Finance",
    "target-": "Finance",
    "netflix-": "Finance",
    # Finance / Indices
    "spx-": "Finance",
    "ndx-": "Finance",
    "djia-": "Finance",
    "rut-": "Finance",
    "nik-": "Finance",
    "nya-": "Finance",
    "vix-": "Finance",
    "dxy-": "Finance",
    # Finance / Commodities
    "crude-oil": "Finance",
    "natural-gas": "Finance",
    "will-gold": "Finance",
    "gold-gc": "Finance",
    "gc-": "Finance",
    "will-silver": "Finance",
    "silver-si": "Finance",
    "si-hit": "Finance",
    "copper-": "Finance",
    "wheat-": "Finance",
    "corn-": "Finance",
    # Finance / Forex
    "eurusd": "Finance",
    "usdjpy": "Finance",
    "gbpusd": "Finance",
    "usd-korean": "Finance",
    "will-eurusd": "Finance",
    "will-usdjpy": "Finance",
    "will-gbpusd": "Finance",
    # Finance / IPO & Other
    "largest-company": "Finance",
    "spacex-ipo": "Finance",
    "anthropic-ipo": "Finance",
    "ipos-before": "Finance",
    "earnings-": "Finance",
    # Crypto
    "bitcoin": "Crypto",
    "ethereum": "Crypto",
    "solana": "Crypto",
    "bnb-": "Crypto",
    "xrp-": "Crypto",
    "dogecoin": "Crypto",
    "cardano": "Crypto",
    "btc-": "Crypto",
    "eth-": "Crypto",
    "sol-": "Crypto",
    # Climate & Science
    "chicago-daily-weather": "Climate & Science",
    "nyc-daily-weather": "Climate & Science",
    "la-daily-weather": "Climate & Science",
    "miami-daily-weather": "Climate & Science",
    "houston-daily-weather": "Climate & Science",
    "phoenix-daily-weather": "Climate & Science",
    # Culture
    "elon-tweet": "Culture",
    # World / Politics
    "china-invade": "World",
    "us-election": "Politics",
    "us-presidential": "Politics",
}

# ── Series slug keyword → Clean display category ─────────────────
# If a keyword appears ANYWHERE in the seriesSlug, map to this category.
# Checked after prefix matching; first match wins.

SERIES_KEYWORD_MAP: dict[str, str] = {
    "-earnings": "Finance",
    "multi-strikes": "Finance",
    "neg-risk": "Finance",
    "-ipo-": "Finance",
    "quarterly-earnings": "Finance",
    "hit-price": "Finance",
    "above-on-": "Finance",
    "largest-company": "Finance",
}

# Title-based fallback keywords when category is empty or unmapped.
# Checked in order; first match wins.
_TITLE_CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("Politics", ["trump", "biden", "congress", "senate", "election", "president",
                  "governor", "democrat", "republican", "gop", "parliament",
                  "prime minister", "impeach", "ballot", "vote", "legislation"]),
    ("Economy", ["fed ", "federal reserve", "interest rate", "inflation", "cpi",
                 "gdp", "jobs report", "unemployment", "recession", "tariff",
                 "trade war", "trade deal", "treasury", "housing market",
                 "mortgage rate", "consumer confidence", "pce", "fomc",
                 "rate cut", "rate hike", "global rates", "central bank",
                 "tsa checkpoint", "tsa throughput", "macro"]),
    ("Finance", ["s&p", "nasdaq", "dow jones",
                 "earnings", "ipo", "stock", "equities", "close at $",
                 "share price", "market cap", "quarterly",
                 "aapl", "tsla", "nvda", "msft", "goog", "amzn", "beat earnings",
                 "close above", "close below", "finish week", "finish month",
                 "open up or down", "commodity", "forex", "gold ", "silver ",
                 "crude oil", "natural gas"]),
    ("Crypto", ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", "crypto",
                "defi", "nft", "memecoin", "doge", "token"]),
    ("Sports", ["nba", "nfl", "mlb", "nhl", "soccer", "premier league",
                "champions league", "super bowl", "world series", "ufc", "mma",
                "tennis", "golf", "olympics", "world cup", "f1", "formula 1"]),
    ("Tech", ["openai", "chatgpt", "google", "apple", "microsoft", "meta ",
              "tiktok", "spacex", "tesla", "ai ", "artificial intelligence"]),
    ("Culture", ["oscar", "grammy", "emmy", "box office", "movie", "album",
                 "celebrity", "viral", "elon musk tweet", "kanye"]),
    ("Climate & Science", ["hurricane", "earthquake", "temperature", "climate",
                           "wildfire", "nasa", "space", "asteroid"]),
    ("World", ["ukraine", "russia", "china", "iran", "israel", "gaza",
               "north korea", "venezuela", "nato", "eu "]),
]


# ── Subcategory keywords per category ─────────────────────────────
# For each clean category, map subcategory labels to title keywords.

SUBCATEGORY_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "Politics": {
        "Trump": ["trump", "donald trump", "maga", "mar-a-lago"],
        "Texas Senate": ["texas senate"],
        "Midterms": ["midterm", "midterms"],
        "Primaries": ["primary", "primaries", "nomination", "nominee", "caucus"],
        "Trade War": ["tariff", "trade war", "trade deal", "sanctions"],
        "US Election": ["presidential election", "president 2028", "president 2026",
                        "electoral college", "general election", "us election"],
    },
    "Sports": {
        "NBA": ["nba", "basketball", "lakers", "celtics", "warriors", "nets",
                "bucks", "76ers", "knicks", "mavericks", "heat"],
        "NFL": ["nfl", "football", "super bowl", "touchdown", "quarterback",
                "chiefs", "eagles", "cowboys", "49ers", "ravens"],
        "Soccer": ["soccer", "premier league", "champions league", "fifa",
                   "world cup", "la liga", "bundesliga", "serie a", "mls"],
        "MLB": ["mlb", "baseball", "world series", "home run"],
        "NHL": ["nhl", "hockey", "stanley cup"],
        "MMA": ["ufc", "mma", "fight night", "dana white"],
        "Tennis": ["tennis", "wimbledon", "us open tennis", "australian open tennis",
                   "french open tennis", "roland garros"],
        "Golf": ["golf", "pga", "masters", "ryder cup"],
        "F1": ["formula 1", "f1", "grand prix"],
        "Olympics": ["olympics", "olympic"],
    },
    "Crypto": {
        "Bitcoin": ["bitcoin", "btc"],
        "Ethereum": ["ethereum", "eth"],
        "Solana": ["solana", "sol"],
        "Memecoins": ["doge", "dogecoin", "shiba", "memecoin", "pepe", "bonk"],
        "DeFi": ["defi", "uniswap", "aave", "compound"],
        "Regulation": ["sec ", "crypto regulation", "crypto ban", "crypto etf"],
        "NFTs": ["nft", "opensea", "bored ape"],
        "Altcoins": ["xrp", "cardano", "polkadot", "avalanche", "polygon"],
    },
    "Economy": {
        "Trade War": ["tariff", "trade war", "trade deal", "sanctions",
                      "trade policy", "trade deficit"],
        "Fed Rate": ["fed ", "federal reserve", "fomc", "powell",
                     "interest rate", "rate cut", "rate hike", "fed funds"],
        "Inflation": ["inflation", "cpi", "consumer price", "pce",
                      "deflation", "price index"],
        "Macro Indicators": ["consumer confidence", "pmi", "manufacturing",
                             "retail sales", "industrial production",
                             "durable goods", "leading indicators",
                             "economic indicator"],
        "GDP": ["gdp", "economic growth", "recession", "gross domestic"],
        "Global Rates": ["ecb", "bank of england", "bank of japan", "boj",
                         "central bank", "global rates", "rba", "boc"],
        "Taxes": ["tax cut", "tax rate", "tax reform", "corporate tax",
                  "income tax", "capital gains tax", "tax policy"],
        "Treasuries": ["treasury", "treasuries", "10-year", "10 year yield",
                       "bond yield", "yield curve", "t-bill"],
        "TSA": ["tsa checkpoint", "tsa throughput", "tsa traveler",
                "airport throughput"],
        "Housing": ["housing", "home price", "home sales", "mortgage",
                    "existing home", "new home", "housing starts",
                    "case-shiller"],
    },
    "Finance": {
        "Daily": ["daily", "open up or down", "opens up or down",
                  "up or down on", "today"],
        "Weekly": ["weekly", "finish week", "finish the week", "this week",
                   "end of week", "close for the week"],
        "Monthly": ["monthly", "finish month", "finish the month", "this month",
                    "end of month", "close for the month"],
        "Stocks": ["close at", "close above", "close below", "share price",
                   "above $", "dip to $",
                   "(aapl)", "(tsla)", "(nvda)", "(msft)", "(goog)", "(amzn)",
                   "(meta)", "(nflx)", "(pltr)", "(avgo)", "(crwd)", "(cost)",
                   "(adbe)", "(tgt)", "(anf)", "(gtlb)", "(snap)", "(uber)",
                   "(abnb)", "(shop)", "(roku)", "(pypl)", "(intc)", "(amd)",
                   "(smci)", "(arm)", "(mu)"],
        "Earnings": ["beat earnings", "miss earnings", "beat quarterly",
                     "quarterly earnings", "revenue estimate"],
        "Indices": ["s&p 500", "(spx)", "nasdaq 100", "(ndx)", "dow jones",
                    "(djia)", "russell 2000", "(rut)", "nikkei", "(nik)",
                    "(nya)"],
        "Commodities": ["gold (gc)", "silver (si)", "crude oil (cl)",
                        "natural gas (ng)", "copper", "wheat", "corn",
                        "commodity", "commodities"],
        "Forex": ["eur/usd", "usd/jpy", "gbp/usd", "exchange rate",
                  "forex", "dollar index", "dxy", "korean won"],
        "Acquisitions": ["acquisition", "merger", "takeover", "buyout"],
        "Earnings Calendar": ["earnings date", "report date", "reporting on",
                              "earnings on"],
        "Earnings Calls": ["earnings call", "conference call", "investor call"],
        "IPOs": ["ipo", "publicly trading", "direct listing", "spac",
                 "closing market cap"],
        "Fed Rates": ["fed rate", "rate decision", "basis points",
                      "rate probability"],
    },
    "Tech": {
        "AI": ["openai", "chatgpt", "gpt-5", "claude", "gemini", "llm",
               "artificial intelligence", "ai "],
        "Social Media": ["tiktok", "twitter", "x.com", "instagram", "facebook",
                        "social media ban"],
        "Apple": ["apple", "iphone", "wwdc"],
        "Google": ["google", "alphabet", "android"],
        "SpaceX": ["spacex", "starship", "falcon", "starlink"],
        "Tesla": ["tesla", "cybertruck"],
        "Microsoft": ["microsoft", "xbox", "copilot"],
    },
    "Culture": {
        "Movies": ["oscar", "box office", "movie", "film"],
        "Music": ["grammy", "album", "billboard", "concert", "spotify"],
        "TV": ["emmy", "netflix", "streaming", "tv show"],
        "Celebrity": ["celebrity", "kanye", "kardashian", "viral"],
        "Elon Musk": ["elon musk", "musk tweet"],
    },
    "Climate & Science": {
        "Weather": ["hurricane", "tornado", "blizzard", "heatwave", "drought",
                    "wildfire", "flood"],
        "Temperature": ["temperature", "hottest", "coldest", "record high",
                       "record low"],
        "Space": ["nasa", "spacex launch", "asteroid", "mars", "moon"],
        "Earthquakes": ["earthquake", "seismic"],
    },
    "World": {
        "Ukraine/Russia": ["ukraine", "russia", "putin", "zelensky", "crimea"],
        "Middle East": ["israel", "gaza", "palestine", "iran", "saudi",
                       "houthi", "hezbollah", "syria"],
        "China": ["china", "xi jinping", "taiwan", "hong kong"],
        "Asia": ["japan", "korea", "india", "pakistan", "philippines"],
        "Latin America": ["brazil", "mexico", "argentina", "colombia"],
        "Europe": ["eu ", "european union", "nato", "uk ", "france", "germany"],
    },
}


def normalize_category(raw_category: str, title: str = "") -> str:
    """Map raw API category to a clean display category.

    1. Try direct lookup in CATEGORY_MAP (case-insensitive).
    2. Fall back to keyword matching on the market title.
    3. Default to "Other" if nothing matches.
    """
    if raw_category:
        key_lower = raw_category.lower().strip()
        # Exact match first
        normalized = CATEGORY_MAP.get(key_lower)
        if normalized:
            return normalized
        # Prefix match for series slugs (e.g., "aapl-neg-risk-weekly" → Finance)
        # Sort by descending key length so "nflx" matches before "nfl"
        for prefix, cat in sorted(SERIES_PREFIX_MAP.items(), key=lambda x: -len(x[0])):
            if key_lower.startswith(prefix):
                return cat
        # Keyword-in-slug match (e.g., "avgo-earnings" contains "-earnings" → Finance)
        for keyword, cat in SERIES_KEYWORD_MAP.items():
            if keyword in key_lower:
                return cat

    # Title-based fallback
    if title:
        title_lower = title.lower()
        for cat, keywords in _TITLE_CATEGORY_KEYWORDS:
            for kw in keywords:
                if kw in title_lower:
                    return cat

    # If the raw category looks reasonable (capitalized, not a ticker), keep it
    if raw_category and not raw_category.startswith("KX") and raw_category[0:1].isupper():
        return raw_category

    return "Other"


def extract_subcategory(category: str, title: str) -> str:
    """Extract a subcategory from the market title using keyword matching.

    Returns the first matching subcategory for the given category,
    or empty string if none match.
    """
    if not title or category not in SUBCATEGORY_KEYWORDS:
        return ""

    title_lower = title.lower()
    for subcategory, keywords in SUBCATEGORY_KEYWORDS[category].items():
        for kw in keywords:
            if kw in title_lower:
                return subcategory

    return ""
