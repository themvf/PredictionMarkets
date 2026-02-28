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
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from agents.registry import AgentRegistry
from config import SchedulerConfig
from notifications.slack import SlackNotifier

logger = logging.getLogger(__name__)


class SchedulerRunner:
    def __init__(self, registry: AgentRegistry,
                 context_factory: Callable[[], Dict[str, Any]],
                 config: Optional[SchedulerConfig] = None,
                 slack_notifier: Optional[SlackNotifier] = None) -> None:
        self.registry = registry
        self.context_factory = context_factory
        self.config = config or SchedulerConfig()
        self.slack_notifier = slack_notifier
        self.scheduler = BackgroundScheduler()
        self._running = False

    def _run_agent(self, agent_name: str) -> None:
        """Execute a single agent with fresh context, then send Slack notification."""
        try:
            context = self.context_factory()

            # Capture alert count before run so we can find new ones
            queries = context.get("queries")
            pre_run_time = datetime.now(timezone.utc).isoformat()

            result = self.registry.run_one(agent_name, context)
            logger.info(
                "Agent '%s' completed: %s (%d items in %.1fs)",
                agent_name, result.status.value,
                result.items_processed, result.duration_seconds,
            )
            if result.error:
                logger.error("Agent '%s' error: %s", agent_name, result.error)

            # Send Slack notification
            if self.slack_notifier and self.slack_notifier.enabled:
                recent_alerts = None
                if queries:
                    try:
                        all_recent = queries.get_alerts(limit=50)
                        recent_alerts = [
                            a for a in all_recent
                            if (a.get("triggered_at") or "") >= pre_run_time
                        ]
                    except Exception:
                        pass
                try:
                    self.slack_notifier.notify_agent_run(result, recent_alerts)
                except Exception:
                    logger.exception("Slack notification failed for '%s'", agent_name)

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
