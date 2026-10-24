"""Full WanderWise demo: Amazon Bedrock generation + Decider 2B tool routing.

Requires:
  * a running ``strands-decider serve`` endpoint (DECIDER_URL, default :8000), and
  * Bedrock access (BEDROCK_MODEL_ID, BEDROCK_ASSUME_ROLE_ARN in the env/.env).

Each tool call the LLM attempts is first checked by Strands Decider 2B. When the
decider is confident a different tool fits better, it guides the agent to the
right one. Every decision is printed with its calibrated confidence and latency.

Usage:
    python -m examples.full_agent_demo "Find me a cheap flight to Osaka"
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv
from rich.console import Console

from wanderwise.agent import build_agent
from wanderwise.tool_router import RouteDecision

console = Console()


def _print_decision(d: RouteDecision) -> None:
    color = {"proceed": "green", "redirect": "yellow", "low-confidence-proceed": "dim"}[
        d.action
    ]
    console.print(
        f"  [{color}]● Decider 2B[/]: llm={d.llm_tool} -> chose "
        f"[bold]{d.chosen_tool}[/] "
        f"(conf {d.confidence:.3f}, {d.latency_ms:.0f} ms, action={d.action})"
    )


def main() -> int:
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    load_dotenv("/opt/wanderwise/.env")  # EC2 default

    prompt = (
        " ".join(sys.argv[1:])
        or "I'm going to Osaka for 4 days. Find me a cheap flight there."
    )

    console.print(f"[bold cyan]WanderWise[/bold cyan]\nUser: {prompt}\n")

    try:
        agent, router = build_agent(on_decision=_print_decision)
    except Exception as exc:  # pragma: no cover
        console.print(f"[red]Failed to build agent:[/red] {exc}")
        console.print(
            "[dim]Check Bedrock env (BEDROCK_MODEL_ID / BEDROCK_ASSUME_ROLE_ARN) "
            "and that the decider server is running.[/dim]"
        )
        return 1

    result = agent(prompt)

    console.print("\n[bold green]WanderWise:[/bold green]")
    console.print(str(result))

    console.print(
        f"\n[dim]Routing decisions made: {len(router.decisions)}; "
        f"redirects: {sum(1 for d in router.decisions if d.action == 'redirect')}[/dim]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
