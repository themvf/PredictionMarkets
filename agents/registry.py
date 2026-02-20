"""Agent registry for orchestration.

Manages agent registration and sequential execution.
Each agent's result is stored in the shared context dict
for downstream agents to consume.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Optional

from .base import AgentResult, BaseAgent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: OrderedDict[str, BaseAgent] = OrderedDict()

    def register(self, agent: BaseAgent) -> None:
        """Register an agent by its name."""
        self._agents[agent.name] = agent

    def get(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)

    @property
    def agents(self) -> List[BaseAgent]:
        return list(self._agents.values())

    @property
    def agent_names(self) -> List[str]:
        return list(self._agents.keys())

    def run_all(self, context: Dict[str, Any]) -> List[AgentResult]:
        """Execute all agents sequentially in registration order."""
        results: List[AgentResult] = []
        for agent in self._agents.values():
            result = agent.run(context)
            results.append(result)
        return results

    def run_one(self, name: str, context: Dict[str, Any]) -> AgentResult:
        """Execute a single agent by name."""
        agent = self._agents.get(name)
        if not agent:
            raise KeyError(f"Agent '{name}' not registered.")
        return agent.run(context)
