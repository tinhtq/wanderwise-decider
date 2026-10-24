"""Thin, dependency-light client for a running ``strands-decider serve`` process.

``strands-decider serve <checkpoint>`` exposes ``POST /v1/systemone``. This client
wraps that endpoint with typed helpers for the three question kinds the model
supports: choice, noul (yes/no), and score.

The model is a *decision* model: it never generates text. You give it a ``state``
(whatever the agent is looking at) and one or more typed questions, and it returns
a calibrated answer for each in a single forward pass (~115ms warm).

This module is intentionally free of Strands imports so it can be reused in any
Python agent, not just Strands ones.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


class DeciderError(RuntimeError):
    """Raised when the decider endpoint is unreachable or returns an error."""


@dataclass
class ChoiceResult:
    """Answer to a choice question."""

    choice: str
    probabilities: dict[str, float]
    confidence: float
    latency_ms: float = 0.0
    input_tokens: int = 0

    @property
    def runner_up(self) -> tuple[str, float] | None:
        """The second most probable option and its probability, if any."""
        ranked = sorted(self.probabilities.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[1] if len(ranked) > 1 else None


@dataclass
class NoulResult:
    """Answer to a yes/no question: the probability the statement is true."""

    probability: float
    latency_ms: float = 0.0
    input_tokens: int = 0

    @property
    def is_yes(self) -> bool:
        return self.probability >= 0.5


@dataclass
class ScoreResult:
    """Answer to a score question: the chosen rung on an ordered rubric."""

    index: int
    label: str
    probabilities: dict[str, float]
    confidence: float
    latency_ms: float = 0.0
    input_tokens: int = 0


@dataclass
class DeciderClient:
    """Client for a ``strands-decider serve`` endpoint.

    Args:
        base_url: Where the serve process is listening. Default matches the
            serve default (``127.0.0.1:8000``).
        timeout_s: HTTP timeout per request.
        model: Optional model name echoed back by the server.
    """

    base_url: str = "http://127.0.0.1:8000"
    timeout_s: float = 30.0
    model: str | None = None
    _endpoint: str = field(init=False, default="")

    def __post_init__(self) -> None:
        self._endpoint = self.base_url.rstrip("/") + "/v1/systemone"

    # -- health ------------------------------------------------------------
    def healthy(self) -> bool:
        """Return True if the serve process answers its health check."""
        url = self.base_url.rstrip("/") + "/health"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout_s) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False

    # -- core call ---------------------------------------------------------
    def _post(self, state: Any, questions: dict[str, dict]) -> dict:
        payload: dict[str, Any] = {"state": state, "questions": questions}
        if self.model:
            payload["model"] = self.model
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            body = exc.read().decode("utf-8", "replace")
            raise DeciderError(f"decider HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network
            raise DeciderError(
                f"cannot reach decider at {self._endpoint}: {exc.reason}. "
                "Is `strands-decider serve` running?"
            ) from exc

    # -- typed helpers -----------------------------------------------------
    def choice(
        self,
        state: Any,
        instructions: str,
        options: dict[str, str],
        *,
        question_id: str = "choice",
    ) -> ChoiceResult:
        """Pick one of several named options.

        Args:
            state: What the model is reasoning about (string or structured).
            instructions: The question prompt.
            options: Mapping of option name -> short description of when it applies.
            question_id: Key used internally for the question.
        """
        questions = {
            question_id: {
                "type": "choice",
                "instructions": instructions,
                "criteria": options,
            }
        }
        resp = self._post(state, questions)
        ans = resp["answers"][question_id]
        return ChoiceResult(
            choice=ans["choice"],
            probabilities=ans["probabilities"],
            confidence=ans["confidence"],
            latency_ms=resp.get("latency_ms", 0.0),
            input_tokens=resp.get("usage", {}).get("input_tokens", 0),
        )

    def noul(
        self,
        state: Any,
        instructions: str,
        criteria: dict[str, str] | None = None,
        *,
        question_id: str = "noul",
    ) -> NoulResult:
        """Ask a yes/no question; returns the probability the statement is true."""
        q: dict[str, Any] = {"type": "noul", "instructions": instructions}
        if criteria:
            q["criteria"] = criteria
        resp = self._post(state, {question_id: q})
        ans = resp["answers"][question_id]
        return NoulResult(
            probability=ans["noul"],
            latency_ms=resp.get("latency_ms", 0.0),
            input_tokens=resp.get("usage", {}).get("input_tokens", 0),
        )

    def score(
        self,
        state: Any,
        instructions: str,
        rubric: list[str],
        *,
        question_id: str = "score",
    ) -> ScoreResult:
        """Rate ``state`` against an ascending rubric (index 0 = low end)."""
        resp = self._post(
            state,
            {
                question_id: {
                    "type": "score",
                    "instructions": instructions,
                    "criteria": rubric,
                }
            },
        )
        ans = resp["answers"][question_id]
        probs = ans.get("probabilities", {})
        label = ans.get("score") or ans.get("choice") or rubric[0]
        try:
            index = rubric.index(label)
        except ValueError:
            index = 0
        return ScoreResult(
            index=index,
            label=label,
            probabilities=probs,
            confidence=ans.get("confidence", 0.0),
            latency_ms=resp.get("latency_ms", 0.0),
            input_tokens=resp.get("usage", {}).get("input_tokens", 0),
        )
