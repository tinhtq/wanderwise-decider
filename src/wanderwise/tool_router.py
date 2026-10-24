"""DeciderToolRouter: a reusable Strands tool-selection decision pattern.

**Pattern:** tool selection (``#tool-selection``).

**What it does.** Before a Strands agent runs a tool, this intervention asks
Strands Decider 2B a single typed *choice* question: "given what the user said,
which tool is the right one?" If the model is confident that a *different* tool
fits better than the one the LLM picked, the handler ``Guide``s the agent to the
right tool instead of letting the wrong call run. If the decision is low
confidence, it gets out of the way and lets the LLM proceed.

**Why a decision model.** A frontier LLM already "chose" a tool, but that choice
is an expensive, uncalibrated byproduct of generation. Decider 2B re-checks the
routing in ~115ms with a *calibrated* confidence number you can threshold on.
That makes it cheap enough to sit in the hot path of every tool call.

**How to reuse it in your own agent (3 steps):**

    from strands import Agent
    from wanderwise.decider_client import DeciderClient
    from wanderwise.tool_router import DeciderToolRouter

    router = DeciderToolRouter(
        client=DeciderClient("http://127.0.0.1:8000"),
        tools={
            "search_flights": "the user wants to find or book flights",
            "find_hotels": "the user wants lodging or accommodation",
            # ... one line per tool: name -> when it applies
        },
        confidence_threshold=0.85,
    )
    agent = Agent(model=..., tools=[...], interventions=[router])

The only things you supply are (1) a running ``strands-decider serve`` endpoint
and (2) a one-line description of each tool. Everything else — the typed
question, the wiring, the thresholding — is handled here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from strands.hooks.events import BeforeToolCallEvent
from strands.interventions import Guide, InterventionHandler, Proceed

from .decider_client import ChoiceResult, DeciderClient, DeciderError

logger = logging.getLogger("wanderwise.tool_router")

# The typed question handed to Decider 2B. Kept as a module constant so it is
# easy to read, audit, and reuse. `{criteria}` (the tool -> description map) is
# supplied per-agent; the instruction text is the reusable part.
ROUTING_INSTRUCTIONS = (
    "A user is talking to a travel assistant. Based only on what the user "
    "actually asked for, which single tool should handle this request?"
)


@dataclass
class RouteDecision:
    """Record of one routing decision, for logging / demo output."""

    user_text: str
    llm_tool: str | None
    chosen_tool: str
    confidence: float
    probabilities: dict[str, float]
    latency_ms: float
    action: str  # "proceed", "redirect", or "low-confidence-proceed"


@dataclass
class DeciderToolRouter(InterventionHandler):
    """Route tool calls through Strands Decider 2B before they execute.

    Args:
        client: A :class:`DeciderClient` pointing at a running serve endpoint.
        tools: Mapping of tool name -> one-line description of when it applies.
            These become the choice options handed to the decision model.
        confidence_threshold: Minimum confidence required to *override* the
            LLM's tool choice. Below this, the LLM proceeds unchanged.
        instructions: The routing question text (defaults to a travel-agent
            phrasing; override for your own domain).
        on_decision: Optional callback invoked with each :class:`RouteDecision`
            (handy for demos, metrics, or tracing).
        fail_open: If the decider endpoint is unreachable, proceed with the
            LLM's choice (True) instead of raising (False).
    """

    client: DeciderClient
    tools: dict[str, str]
    confidence_threshold: float = 0.85
    instructions: str = ROUTING_INSTRUCTIONS
    on_decision: Any = None
    fail_open: bool = True
    decisions: list[RouteDecision] = field(default_factory=list)

    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        """Unique name identifying this intervention handler (required by Strands)."""
        return "decider-tool-router"

    # ------------------------------------------------------------------
    def _latest_user_text(self, event: BeforeToolCallEvent) -> str:
        """Pull the most recent user utterance from the agent's messages."""
        try:
            messages = event.agent.messages
        except Exception:
            return ""
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            parts = []
            for block in msg.get("content", []):
                if isinstance(block, dict) and "text" in block:
                    parts.append(block["text"])
                elif isinstance(block, str):
                    parts.append(block)
            if parts:
                return " ".join(parts).strip()
        return ""

    def _tool_name(self, event: BeforeToolCallEvent) -> str | None:
        try:
            return event.tool_use.get("name")
        except Exception:
            return None

    # ------------------------------------------------------------------
    def before_tool_call(self, event: BeforeToolCallEvent, **kwargs: Any):
        llm_tool = self._tool_name(event)

        # Only arbitrate among tools we have descriptions for.
        if llm_tool is not None and llm_tool not in self.tools:
            return Proceed()

        user_text = self._latest_user_text(event)
        if not user_text:
            return Proceed(reason="no user text to route on")

        try:
            result: ChoiceResult = self.client.choice(
                state=user_text,
                instructions=self.instructions,
                options=self.tools,
                question_id="route",
            )
        except DeciderError:
            if self.fail_open:
                return Proceed(reason="decider unavailable; failing open")
            raise

        chosen = result.choice
        conf = result.confidence

        if chosen == llm_tool:
            action = "proceed"
            self._record(event, user_text, llm_tool, result, action)
            return Proceed(
                reason=f"decider agrees: {chosen} (confidence {conf:.3f})"
            )

        if conf < self.confidence_threshold:
            action = "low-confidence-proceed"
            self._record(event, user_text, llm_tool, result, action)
            return Proceed(
                reason=(
                    f"decider leans {chosen} ({conf:.3f}) but below threshold "
                    f"{self.confidence_threshold}; keeping {llm_tool}"
                )
            )

        # Confident the LLM picked the wrong tool -> guide it to the right one.
        action = "redirect"
        self._record(event, user_text, llm_tool, result, action)
        return Guide(
            feedback=(
                f"Do not call `{llm_tool}` for this request. Strands Decider 2B "
                f"routed this to `{chosen}` with {conf:.0%} confidence. "
                f"Call `{chosen}` instead."
            ),
            reason=f"decider redirect {llm_tool} -> {chosen} ({conf:.3f})",
        )

    # ------------------------------------------------------------------
    def _record(
        self,
        event: BeforeToolCallEvent,
        user_text: str,
        llm_tool: str | None,
        result: ChoiceResult,
        action: str,
    ) -> RouteDecision:
        decision = RouteDecision(
            user_text=user_text,
            llm_tool=llm_tool,
            chosen_tool=result.choice,
            confidence=result.confidence,
            probabilities=result.probabilities,
            latency_ms=result.latency_ms,
            action=action,
        )
        self.decisions.append(decision)
        if self.on_decision is not None:
            try:
                self.on_decision(decision)
            except Exception:
                # A user-supplied callback must never break tool routing.
                logger.debug("on_decision callback raised; ignoring", exc_info=True)
        return decision
