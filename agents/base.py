"""Base agent framework with lifecycle management.

Mirrors the Analyzer.run() pattern from codex_agent/core.py:
- BaseAgent: abstract class with execute(context) and run(context) lifecycle wrapper
- AgentResult: captures timing, status, data, errors
- AgentStatus: enum for agent states

The run() method wraps execute() with:
1. Status tracking (running -> success/error)
2. Timing (started_at, completed_at, duration)
3. Error capture
4. Database logging via agent_logs table
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class AgentResult:
    agent_name: str
    status: AgentStatus = AgentStatus.IDLE
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    error: Optional[str] = None
    items_processed: int = 0


class BaseAgent(ABC):
    """Abstract base agent with lifecycle management."""

    def __init__(self, name: str, config: Any = None) -> None:
        self.name = name
        self.config = config
        self.status = AgentStatus.IDLE
        self.last_result: Optional[AgentResult] = None

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """Core agent logic — implemented by subclasses."""
        ...

    def run(self, context: Dict[str, Any]) -> AgentResult:
        """Lifecycle wrapper: timing, error capture, status tracking, DB logging."""
        self.status = AgentStatus.RUNNING
        started = datetime.now(timezone.utc)

        result = AgentResult(
            agent_name=self.name,
            status=AgentStatus.RUNNING,
            started_at=started.isoformat(),
        )

        try:
            result = self.execute(context)
            result.status = AgentStatus.SUCCESS
            self.status = AgentStatus.SUCCESS
        except Exception as exc:
            result.status = AgentStatus.ERROR
            result.error = str(exc)
            self.status = AgentStatus.ERROR

        completed = datetime.now(timezone.utc)
        result.started_at = started.isoformat()
        result.completed_at = completed.isoformat()
        result.duration_seconds = (completed - started).total_seconds()
        result.agent_name = self.name

        # Log to database if available
        self._log_to_db(context, result)

        # Store result in context for downstream agents
        context[f"result_{self.name}"] = result
        self.last_result = result

        return result

    def _log_to_db(self, context: Dict[str, Any], result: AgentResult) -> None:
        """Persist agent run to agent_logs table."""
        queries = context.get("queries")
        if not queries:
            return
        try:
            from db.models import AgentLog
            log = AgentLog(
                agent_name=result.agent_name,
                status=result.status.value,
                started_at=result.started_at,
                completed_at=result.completed_at,
                duration_seconds=result.duration_seconds,
                items_processed=result.items_processed,
                summary=result.summary,
                error=result.error,
            )
            queries.insert_agent_log(log)
        except Exception:
            pass  # Don't let logging failures break agent execution
