"""APScheduler integration for periodic agent execution.

Runs agents on configurable schedules:
- Discovery: every 30 min
- Collection: every 5 min
- Analyzer: every 15 min
- Alert: every 5 min
- Insight: every 60 min
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from agents.registry import AgentRegistry
from config import SchedulerConfig

logger = logging.getLogger(__name__)


class SchedulerRunner:
    def __init__(self, registry: AgentRegistry,
                 context_factory: Callable[[], Dict[str, Any]],
                 config: Optional[SchedulerConfig] = None) -> None:
        self.registry = registry
        self.context_factory = context_factory
        self.config = config or SchedulerConfig()
        self.scheduler = BackgroundScheduler()
        self._running = False

    def _run_agent(self, agent_name: str) -> None:
        """Execute a single agent with fresh context."""
        try:
            context = self.context_factory()
            result = self.registry.run_one(agent_name, context)
            logger.info(
                "Agent '%s' completed: %s (%d items in %.1fs)",
                agent_name, result.status.value,
                result.items_processed, result.duration_seconds,
            )
            if result.error:
                logger.error("Agent '%s' error: %s", agent_name, result.error)
        except Exception:
            logger.exception("Failed to run agent '%s'", agent_name)

    def setup(self) -> None:
        """Configure scheduled jobs for each agent."""
        schedule_map = {
            "discovery": self.config.discovery_interval_minutes,
            "collection": self.config.collection_interval_minutes,
            "analyzer": self.config.analyzer_interval_minutes,
            "alert": self.config.alert_interval_minutes,
            "insight": self.config.insight_interval_minutes,
            "trader": self.config.trader_interval_minutes,
            "whale": self.config.whale_interval_minutes,
        }

        for agent_name, interval in schedule_map.items():
            if self.registry.get(agent_name):
                self.scheduler.add_job(
                    self._run_agent,
                    "interval",
                    minutes=interval,
                    args=[agent_name],
                    id=f"agent_{agent_name}",
                    name=f"{agent_name.title()} Agent",
                    replace_existing=True,
                )
                logger.info(
                    "Scheduled '%s' agent every %d minutes",
                    agent_name, interval,
                )

    def start(self) -> None:
        """Start the scheduler."""
        if not self._running:
            self.setup()
            self.scheduler.start()
            self._running = True
            logger.info("Scheduler started.")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Scheduler stopped.")

    @property
    def is_running(self) -> bool:
        return self._running

    def get_jobs(self) -> list:
        """Return list of scheduled jobs."""
        return self.scheduler.get_jobs()
