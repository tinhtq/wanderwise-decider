"""WanderWise agent: Amazon Bedrock (generation) + Strands Decider 2B (routing).

This wires the three pieces together:
  * a Bedrock LLM for conversation + itinerary writing,
  * the travel tools,
  * the :class:`DeciderToolRouter` intervention that checks every tool call
    against Strands Decider 2B before it runs.
"""

from __future__ import annotations

import os

from strands import Agent

from .bedrock_provider import build_bedrock_model
from .decider_client import DeciderClient
from .tool_router import DeciderToolRouter
from .tools import ALL_TOOLS, TOOL_DESCRIPTIONS

SYSTEM_PROMPT = (
    "You are WanderWise, a friendly, concise travel planner. You help users "
    "with flights, hotels, activities, weather, and budgets. When a user asks "
    "for something, call the single most relevant tool, then summarize the "
    "result in a warm, helpful sentence or two. Do not invent details the "
    "tools did not return."
)


def build_agent(
    decider_url: str | None = None,
    confidence_threshold: float = 0.85,
    on_decision=None,
) -> tuple[Agent, DeciderToolRouter]:
    """Build the WanderWise agent and return it with its router (for inspection).

    Args:
        decider_url: Base URL of the running ``strands-decider serve`` endpoint.
        confidence_threshold: Minimum confidence to override the LLM's choice.
        on_decision: Optional callback receiving each RouteDecision.
    """
    decider_url = decider_url or os.getenv("DECIDER_URL", "http://127.0.0.1:8000")

    router = DeciderToolRouter(
        client=DeciderClient(decider_url),
        tools=TOOL_DESCRIPTIONS,
        confidence_threshold=confidence_threshold,
        on_decision=on_decision,
    )

    model = build_bedrock_model()

    agent = Agent(
        model=model,
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        interventions=[router],
    )
    return agent, router
