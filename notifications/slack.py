"""Slack webhook notifications for agent runs and alerts.

Sends a formatted message to a Slack channel after each agent execution,
including run summary and any new alerts generated during the run.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import requests

from agents.base import AgentResult, AgentStatus

logger = logging.getLogger(__name__)

# Emoji map for agent names
_AGENT_EMOJI = {
    "discovery": ":mag:",
    "collection": ":bar_chart:",
    "analyzer": ":scales:",
    "alert": ":bell:",
    "insight": ":brain:",
    "trader": ":trophy:",
    "whale": ":whale:",
}

# Emoji map for alert severity
_SEVERITY_EMOJI = {
    "critical": ":rotating_light:",
    "warning": ":warning:",
    "info": ":information_source:",
}

# Emoji map for alert types
_ALERT_TYPE_EMOJI = {
    "price_move": ":chart_with_upwards_trend:",
    "volume_spike": ":fire:",
    "arbitrage": ":moneybag:",
    "closing_soon": ":hourglass_flowing_sand:",
    "keyword": ":key:",
    "whale_trade": ":whale:",
}


class SlackNotifier:
    """Sends agent run summaries to Slack via Incoming Webhook."""

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    @property
    def enabled(self) -> bool:
        return bool(self.webhook_url)

    def notify_agent_run(self, result: AgentResult,
                         recent_alerts: Optional[List[Dict[str, Any]]] = None) -> bool:
        """Send a Slack notification for an agent run.

        Returns True if the message was sent successfully.
        """
        if not self.enabled:
            return False

        blocks = self._build_message(result, recent_alerts)

        try:
            resp = self.session.post(
                self.webhook_url,
                data=json.dumps({"blocks": blocks}),
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning("Slack webhook returned %d: %s", resp.status_code, resp.text)
                return False
            return True
        except Exception:
            logger.exception("Failed to send Slack notification")
            return False

    def _build_message(self, result: AgentResult,
                       recent_alerts: Optional[List[Dict[str, Any]]] = None) -> list:
        """Build Slack Block Kit message."""
        emoji = _AGENT_EMOJI.get(result.agent_name, ":robot_face:")
        status_emoji = ":white_check_mark:" if result.status == AgentStatus.SUCCESS else ":x:"

        blocks: list = []

        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{result.agent_name.title()} Agent Run",
                "emoji": True,
            },
        })

        # Summary section
        duration = f"{result.duration_seconds:.1f}s" if result.duration_seconds else "N/A"
        summary_lines = [
            f"{emoji} *Agent:* {result.agent_name.title()}",
            f"{status_emoji} *Status:* {result.status.value}",
            f":stopwatch: *Duration:* {duration}",
            f":package: *Items Processed:* {result.items_processed}",
        ]
        if result.summary:
            summary_lines.append(f":memo: *Summary:* {result.summary}")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(summary_lines),
            },
        })

        # Error section
        if result.error:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":x: *Error:* ```{result.error[:500]}```",
                },
            })

        # Alerts section
        if recent_alerts:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":bell: *Alerts Generated ({len(recent_alerts)}):*",
                },
            })

            # Show up to 5 alerts to keep message readable
            for alert in recent_alerts[:5]:
                severity = alert.get("severity", "info")
                alert_type = alert.get("alert_type", "unknown")
                sev_emoji = _SEVERITY_EMOJI.get(severity, ":grey_question:")
                type_emoji = _ALERT_TYPE_EMOJI.get(alert_type, ":bell:")

                title = alert.get("title", "Alert")
                message = alert.get("message", "")
                # Truncate long messages
                if len(message) > 200:
                    message = message[:197] + "..."

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{sev_emoji} {type_emoji} *{title}*\n{message}",
                    },
                })

            if len(recent_alerts) > 5:
                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": f"_...and {len(recent_alerts) - 5} more alerts_",
                    }],
                })

        # Footer with timestamp
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f":clock1: {result.completed_at or 'N/A'} UTC | PredictionMarkets Agent",
            }],
        })

        return blocks
