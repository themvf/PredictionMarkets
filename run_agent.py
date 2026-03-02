#!/usr/bin/env python3
"""Standalone CLI to run prediction-market agents without Streamlit.

Usage:
    python run_agent.py <agent_name> [agent_name ...]
    python run_agent.py collection alert whale
    python run_agent.py --all

Designed for GitHub Actions, cron jobs, or manual CLI execution.
"""

import sys
import logging

from config import load_config
from db.database import DatabaseManager
from db.queries import MarketQueries
from agents.registry import AgentRegistry
from agents.discovery_agent import DiscoveryAgent
from agents.collection_agent import CollectionAgent
from agents.analyzer_agent import AnalyzerAgent
from agents.alert_agent import AlertAgent
from agents.insight_agent import InsightAgent
from agents.trader_agent import TraderAgent
from agents.whale_agent import WhaleAgent
from notifications.slack import SlackNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

AGENT_CLASSES = {
    "discovery": DiscoveryAgent,
    "collection": CollectionAgent,
    "analyzer": AnalyzerAgent,
    "alert": AlertAgent,
    "insight": InsightAgent,
    "trader": TraderAgent,
    "whale": WhaleAgent,
}


def build_context(config):
    """Build the shared context dict that agents expect (mirrors streamlit_app.get_context)."""
    db = DatabaseManager(db_path=config.db_path, database_url=config.database_url)
    queries = MarketQueries(db)
    clients = {}

    # Polymarket client
    try:
        from clients.polymarket_client import PolymarketClient
        clients["polymarket_client"] = PolymarketClient(config.polymarket)
    except Exception as e:
        logger.warning("Polymarket client init failed: %s", e)

    # OpenAI client
    if config.openai.api_key:
        try:
            from llm.openai_client import OpenAIClient
            clients["openai_client"] = OpenAIClient(config.openai)
        except Exception as e:
            logger.warning("OpenAI client init failed: %s", e)

    slack = SlackNotifier(config.slack.webhook_url)

    return {
        "config": config,
        "db": db,
        "queries": queries,
        "alert_rules": config.alerts,
        "slack_notifier": slack,
        **clients,
    }


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python run_agent.py <agent_name> [agent_name ...]")
        print(f"       python run_agent.py --all")
        print(f"Available agents: {', '.join(AGENT_CLASSES.keys())}")
        sys.exit(1)

    # Determine which agents to run
    if "--all" in sys.argv:
        agent_names = list(AGENT_CLASSES.keys())
    else:
        agent_names = sys.argv[1:]

    # Validate agent names
    for name in agent_names:
        if name not in AGENT_CLASSES:
            print(f"Unknown agent: {name}")
            print(f"Available: {', '.join(AGENT_CLASSES.keys())}")
            sys.exit(1)

    config = load_config()
    context = build_context(config)

    # Register only the requested agents
    registry = AgentRegistry()
    for name in agent_names:
        registry.register(AGENT_CLASSES[name]())

    # Run each agent sequentially
    failed = False
    for name in agent_names:
        logger.info("Running agent: %s", name)
        try:
            result = registry.run_one(name, context)
            logger.info(
                "Agent '%s' completed: %s (%d items in %.1fs)",
                name, result.status.value,
                result.items_processed, result.duration_seconds,
            )
            if result.error:
                logger.error("Agent '%s' error: %s", name, result.error)
                failed = True
        except Exception:
            logger.exception("Agent '%s' failed", name)
            failed = True

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
