"""
Simple token-usage and cost tracker for Bedrock invocations.

Each agent run accumulates a CostTracker instance.  At completion the
totals are logged and can be persisted to the RunEvent table or returned
in the run state for display in the UI.
"""
from dataclasses import dataclass, field
from typing import Optional


# USD per 1,000 input/output tokens (update as AWS pricing changes)
BEDROCK_PRICING: dict[str, dict[str, float]] = {
    "us.anthropic.claude-opus-4-6-v1": {
        "input":  0.005,    # $53.00 per 1M tokens
        "output": 0.025,    # $25.00 per 1M tokens
    },
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": {
        "input":  0.001,   # $1.00 per 1M tokens
        "output": 0.005,    # $5.00 per 1M tokens
    },
    # Default fallback
    "default": {
        "input":  0.003,
        "output": 0.015,
    },
}


@dataclass
class CostTracker:
    """Accumulates token usage and cost for a single agent run."""

    run_id: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    call_count: int = 0
    calls_by_agent: dict[str, int] = field(default_factory=dict)
    cost_by_agent: dict[str, float] = field(default_factory=dict)

    def record(
        self,
        agent: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Record a single LLM invocation and return the cost for that call.
        """
        pricing = BEDROCK_PRICING.get(model_id, BEDROCK_PRICING["default"])
        cost = (
            input_tokens  / 1_000 * pricing["input"]
            + output_tokens / 1_000 * pricing["output"]
        )

        self.total_input_tokens  += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd      += cost
        self.call_count          += 1
        self.calls_by_agent[agent] = self.calls_by_agent.get(agent, 0) + 1
        self.cost_by_agent[agent]  = self.cost_by_agent.get(agent, 0.0) + cost

        return cost

    def summary(self) -> dict:
        return {
            "run_id":              self.run_id,
            "total_input_tokens":  self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens":        self.total_input_tokens + self.total_output_tokens,
            "total_cost_usd":      round(self.total_cost_usd, 6),
            "call_count":          self.call_count,
            "calls_by_agent":      self.calls_by_agent,
            "cost_by_agent": {
                k: round(v, 6) for k, v in self.cost_by_agent.items()
            },
        }
