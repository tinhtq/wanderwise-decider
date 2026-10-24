"""WanderWise command-line entry point.

``wanderwise``            -> interactive chat (Bedrock + Decider routing)
``wanderwise "..."``      -> single turn
``wanderwise --route-only "..."`` -> show only the Decider 2B routing decision
"""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv
from rich.console import Console

console = Console()


def main() -> int:
    parser = argparse.ArgumentParser(prog="wanderwise", description="WanderWise travel planner")
    parser.add_argument("prompt", nargs="*", help="Your travel request.")
    parser.add_argument(
        "--route-only",
        action="store_true",
        help="Only show the Decider 2B tool-selection decision (no Bedrock).",
    )
    parser.add_argument("--decider-url", default=os.getenv("DECIDER_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--threshold", type=float, default=0.85)
    args = parser.parse_args()

    load_dotenv(".env")
    load_dotenv("/opt/wanderwise/.env")

    text = " ".join(args.prompt).strip()

    if args.route_only:
        from wanderwise.decider_client import DeciderClient
        from wanderwise.tool_router import ROUTING_INSTRUCTIONS
        from wanderwise.tools import TOOL_DESCRIPTIONS

        client = DeciderClient(args.decider_url)
        if not client.healthy():
            console.print(f"[red]Decider not reachable at {args.decider_url}[/red]")
            return 1
        if not text:
            text = "find me a cheap flight to Osaka"
        r = client.choice(text, ROUTING_INSTRUCTIONS, TOOL_DESCRIPTIONS, question_id="route")
        console.print(
            f"[cyan]{text}[/cyan]\n-> [green bold]{r.choice}[/] "
            f"(confidence {r.confidence:.3f}, {r.latency_ms:.0f} ms)"
        )
        return 0

    from wanderwise.agent import build_agent

    agent, router = build_agent(decider_url=args.decider_url, confidence_threshold=args.threshold)

    if text:
        console.print(str(agent(text)))
        if router.decisions:
            d = router.decisions[-1]
            console.print(
                f"[dim](Decider 2B routed -> {d.chosen_tool}, "
                f"conf {d.confidence:.3f}, {d.latency_ms:.0f} ms)[/dim]"
            )
        return 0

    console.print("[bold cyan]WanderWise[/bold cyan] - type 'exit' to quit.")
    while True:
        try:
            msg = console.input("[bold]you > [/bold]").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if msg.lower() in {"exit", "quit"}:
            break
        if msg:
            console.print(str(agent(msg)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
