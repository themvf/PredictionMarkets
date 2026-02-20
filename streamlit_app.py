"""PredictionMarkets — Streamlit Dashboard Entry Point.

Multi-page Streamlit app for prediction market monitoring and analysis.
Initializes database, API clients, and agent registry on startup.
"""

import streamlit as st
from pathlib import Path
import sys

# Add project root to path
PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from config import load_config, AppConfig
from db.database import DatabaseManager
from db.queries import MarketQueries

st.set_page_config(
    page_title="Prediction Markets Intelligence",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def init_database(config: AppConfig) -> DatabaseManager:
    return DatabaseManager(config.db_path)


@st.cache_resource
def init_queries(_db: DatabaseManager) -> MarketQueries:
    return MarketQueries(_db)


@st.cache_resource
def init_config() -> AppConfig:
    return load_config()


def init_clients(config: AppConfig) -> dict:
    """Initialize API clients (cached in session state)."""
    clients = {}

    # Kalshi client
    if config.kalshi.api_key_id and config.kalshi.private_key_path:
        try:
            from clients.kalshi_client import KalshiClient
            clients["kalshi_client"] = KalshiClient(config.kalshi)
        except Exception as e:
            clients["kalshi_error"] = str(e)

    # Polymarket client
    try:
        from clients.polymarket_client import PolymarketClient
        clients["polymarket_client"] = PolymarketClient(config.polymarket)
    except Exception as e:
        clients["polymarket_error"] = str(e)

    # OpenAI client
    if config.openai.api_key:
        try:
            from llm.openai_client import OpenAIClient
            clients["openai_client"] = OpenAIClient(config.openai)
        except Exception as e:
            clients["openai_error"] = str(e)

    return clients


def init_registry():
    """Initialize the agent registry with all agents."""
    from agents.registry import AgentRegistry
    from agents.discovery_agent import DiscoveryAgent
    from agents.collection_agent import CollectionAgent
    from agents.analyzer_agent import AnalyzerAgent
    from agents.alert_agent import AlertAgent
    from agents.insight_agent import InsightAgent

    registry = AgentRegistry()
    registry.register(DiscoveryAgent())
    registry.register(CollectionAgent())
    registry.register(AnalyzerAgent())
    registry.register(AlertAgent())
    registry.register(InsightAgent())
    return registry


def get_context() -> dict:
    """Build shared context dict for agent execution."""
    config = init_config()
    db = init_database(config)
    queries = init_queries(db)
    clients = init_clients(config)

    context = {
        "config": config,
        "db": db,
        "queries": queries,
        "alert_rules": config.alerts,
        **clients,
    }
    return context


# ── Main Page ────────────────────────────────────────────────

def main():
    config = init_config()
    db = init_database(config)
    queries = init_queries(db)

    # Sidebar
    with st.sidebar:
        st.title("Prediction Markets")
        st.caption("Agentic AI Intelligence Platform")
        st.divider()

        # Connection status
        st.subheader("Status")
        clients = init_clients(config)

        kalshi_ok = "kalshi_client" in clients
        poly_ok = "polymarket_client" in clients
        openai_ok = "openai_client" in clients

        col1, col2, col3 = st.columns(3)
        col1.metric("Kalshi", "OK" if kalshi_ok else "OFF")
        col2.metric("Poly", "OK" if poly_ok else "OFF")
        col3.metric("GPT-4o", "OK" if openai_ok else "OFF")

        if not kalshi_ok:
            st.warning(f"Kalshi: {clients.get('kalshi_error', 'Not configured')}")
        if not openai_ok:
            st.warning(f"OpenAI: {clients.get('openai_error', 'Not configured')}")

        st.divider()
        market_counts = queries.get_market_counts()
        total = sum(market_counts.values())
        st.metric("Total Markets Tracked", total)
        for platform, count in market_counts.items():
            st.caption(f"  {platform.title()}: {count}")

    # Main content
    st.title("Prediction Markets Intelligence Dashboard")
    st.markdown("Cross-platform monitoring, analysis, and AI-powered insights for **Kalshi** and **Polymarket**.")

    # Quick stats
    col1, col2, col3, col4 = st.columns(4)
    market_counts = queries.get_market_counts()
    pairs = queries.get_all_pairs()
    alerts = queries.get_alerts(acknowledged=False, limit=100)

    col1.metric("Kalshi Markets", market_counts.get("kalshi", 0))
    col2.metric("Polymarket Markets", market_counts.get("polymarket", 0))
    col3.metric("Cross-Platform Pairs", len(pairs))
    col4.metric("Active Alerts", len(alerts))

    st.divider()

    # Recent activity
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Top Markets by Volume")
        markets = queries.get_all_markets()[:10]
        if markets:
            for m in markets:
                price = m.get("yes_price")
                vol = m.get("volume", 0) or 0
                price_str = f"${price:.2f}" if price else "N/A"
                platform_badge = "K" if m["platform"] == "kalshi" else "P"
                st.markdown(f"**[{platform_badge}]** {m['title']}  \n"
                           f"Price: {price_str} | Volume: {vol:,.0f}")
        else:
            st.info("No markets discovered yet. Run the Discovery Agent to get started.")

    with col_right:
        st.subheader("Recent Alerts")
        if alerts:
            for a in alerts[:8]:
                severity_color = {
                    "critical": "red",
                    "warning": "orange",
                    "info": "blue",
                }.get(a["severity"], "gray")
                st.markdown(f":{severity_color}[**{a['severity'].upper()}**] {a['title']}  \n"
                           f"{a['message'][:100]}")
        else:
            st.info("No alerts yet. Alerts will appear after agents run.")

    st.divider()
    st.caption("Navigate using the sidebar to explore Market Overview, Cross-Platform Analysis, Price Charts, Alerts, AI Insights, and Agent Status.")


if __name__ == "__main__":
    main()
