"""WanderWise: a Strands + Amazon Bedrock travel planner whose tool routing is
decided by Strands Decider 2B.

Reusable asset: :class:`~wanderwise.tool_router.DeciderToolRouter`, a Strands
InterventionHandler implementing the *tool-selection* decision pattern.
"""

from .decider_client import (
    ChoiceResult,
    DeciderClient,
    DeciderError,
    NoulResult,
    ScoreResult,
)
from .tool_router import DeciderToolRouter, RouteDecision

__all__ = [
    "ChoiceResult",
    "DeciderClient",
    "DeciderError",
    "DeciderToolRouter",
    "NoulResult",
    "RouteDecision",
    "ScoreResult",
]

__version__ = "0.1.0"
