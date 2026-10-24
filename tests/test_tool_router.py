"""Tests for the DeciderToolRouter — the reusable tool-selection pattern.

These use a fake decider client so they run without model weights or a server.
The one live/integration check lives in the demos.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wanderwise.decider_client import ChoiceResult, DeciderError
from wanderwise.tool_router import DeciderToolRouter

TOOLS = {
    "search_flights": "flights",
    "find_hotels": "lodging",
    "estimate_budget": "costs",
}


class _FakeAgent:
    def __init__(self, text: str):
        self.messages = [{"role": "user", "content": [{"text": text}]}]


class _FakeEvent:
    def __init__(self, text: str, llm_tool: str):
        self.agent = _FakeAgent(text)
        self.tool_use = {"name": llm_tool}


class _StubClient:
    """Returns a fixed ChoiceResult; optionally raises to test fail-open."""

    def __init__(self, choice, confidence, raise_err=False):
        self._choice = choice
        self._conf = confidence
        self._raise = raise_err

    def choice(self, state, instructions, options, question_id="route"):
        if self._raise:
            raise DeciderError("boom")
        probs = {k: 0.01 for k in options}
        probs[self._choice] = self._conf
        return ChoiceResult(self._choice, probs, self._conf, latency_ms=90.0)


def test_proceed_when_decider_agrees():
    router = DeciderToolRouter(
        client=_StubClient("search_flights", 0.98), tools=TOOLS
    )
    action = router.before_tool_call(_FakeEvent("cheap flight to Osaka", "search_flights"))
    assert type(action).__name__ == "Proceed"
    assert router.decisions[-1].action == "proceed"


def test_redirect_when_decider_confidently_disagrees():
    router = DeciderToolRouter(
        client=_StubClient("find_hotels", 0.97), tools=TOOLS, confidence_threshold=0.85
    )
    action = router.before_tool_call(_FakeEvent("where to stay in Kyoto", "search_flights"))
    assert type(action).__name__ == "Guide"
    assert "find_hotels" in action.feedback
    assert router.decisions[-1].action == "redirect"


def test_low_confidence_keeps_llm_choice():
    router = DeciderToolRouter(
        client=_StubClient("find_hotels", 0.60), tools=TOOLS, confidence_threshold=0.85
    )
    action = router.before_tool_call(_FakeEvent("ambiguous", "search_flights"))
    assert type(action).__name__ == "Proceed"
    assert router.decisions[-1].action == "low-confidence-proceed"


def test_fail_open_when_decider_unavailable():
    router = DeciderToolRouter(
        client=_StubClient("x", 0.9, raise_err=True), tools=TOOLS, fail_open=True
    )
    action = router.before_tool_call(_FakeEvent("anything", "search_flights"))
    assert type(action).__name__ == "Proceed"


def test_untracked_tool_proceeds():
    router = DeciderToolRouter(client=_StubClient("x", 0.9), tools=TOOLS)
    action = router.before_tool_call(_FakeEvent("hi", "some_other_tool"))
    assert type(action).__name__ == "Proceed"
