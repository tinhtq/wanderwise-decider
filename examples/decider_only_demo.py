"""Decider-only demo: show Strands Decider 2B routing travel requests to tools.

This runs the *decision* half of WanderWise with no Bedrock/LLM involved, so it
works anywhere a ``strands-decider serve`` endpoint is reachable. It demonstrates
the exact tool-selection decision the agent relies on, with calibrated
confidence and latency for each request.

Usage:
    # 1) In one shell, start the model server:
    strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 \
        --host 127.0.0.1 --port 8000
    # 2) In another:
    python -m examples.decider_only_demo
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from rich.console import Console
from rich.table import Table

from wanderwise.decider_client import DeciderClient
from wanderwise.tool_router import ROUTING_INSTRUCTIONS
from wanderwise.tools import TOOL_DESCRIPTIONS

SAMPLE_REQUESTS = [
    "I need a cheap flight from Hanoi to Tokyo next Friday",
    "Where should I stay in Kyoto for 4 nights?",
    "What's there to do in Lisbon if I love food?",
    "Will it rain in Bali next week?",
    "How much should I budget for 5 days in Reykjavik?",
    "Find me somewhere to sleep near Shibuya station",
]


def main() -> int:
    console = Console()
    url = os.getenv("DECIDER_URL", "http://127.0.0.1:8000")
    client = DeciderClient(url)

    if not client.healthy():
        console.print(
            f"[red]Decider endpoint not reachable at {url}.[/red]\n"
            "Start it with:\n"
            "  strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 "
            "--host 127.0.0.1 --port 8000"
        )
        return 1

    console.print(
        f"[bold cyan]WanderWise - Decider 2B tool selection[/bold cyan]  "
        f"([dim]{url}[/dim])\n"
    )

    table = Table(show_lines=True)
    table.add_column("User request", style="white", max_width=42)
    table.add_column("Routed tool", style="green bold")
    table.add_column("Conf.", justify="right")
    table.add_column("Runner-up", style="dim")
    table.add_column("ms", justify="right", style="dim")

    total_ms = 0.0
    for text in SAMPLE_REQUESTS:
        r = client.choice(
            state=text,
            instructions=ROUTING_INSTRUCTIONS,
            options=TOOL_DESCRIPTIONS,
            question_id="route",
        )
        total_ms += r.latency_ms
        runner = r.runner_up
        runner_str = f"{runner[0]} ({runner[1]:.2f})" if runner else "-"
        table.add_row(
            text,
            r.choice,
            f"{r.confidence:.3f}",
            runner_str,
            f"{r.latency_ms:.0f}",
        )

    console.print(table)
    console.print(
        f"\n[bold]{len(SAMPLE_REQUESTS)} decisions[/bold], "
        f"avg latency [bold]{total_ms / len(SAMPLE_REQUESTS):.0f} ms[/bold]. "
        "No LLM tokens generated - this is the System One decision model only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
