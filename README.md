# WanderWise 🧭

A travel-planner agent where **Amazon Bedrock** does the talking and **Strands
Decider 2B** decides which tool to call.

> **Hackathon:** Agent Experience Hackathon — Strands Decider
> **Decision pattern:** Tool selection
> **Tags:** `#strands-decider-2b` `#tool-selection`

---

## The idea in one sentence

A frontier LLM is great at writing a travel itinerary but expensive and
*uncalibrated* when it decides *which tool to call*. WanderWise moves that one
decision onto **Strands Decider 2B** — a 2B open decision model that returns a
**calibrated** tool choice in **~92 ms** on a single GPU — and keeps Bedrock for
the part it's actually good at: talking to the user.

```
User: "Where should I stay in Kyoto for 4 nights?"
        │
        ▼
  Amazon Bedrock (Nova Pro)  ──▶ proposes a tool call
        │
        ▼
  Strands Decider 2B  ──▶  "find_hotels, confidence 0.962, 92 ms"
        │                   (if it disagrees with Bedrock, it redirects)
        ▼
  find_hotels() runs ──▶ Bedrock writes the friendly answer
```

## The reusable asset: `DeciderToolRouter`

The heart of this project — and the thing you can drop into **your own** Strands
agent — is [`src/wanderwise/tool_router.py`](src/wanderwise/tool_router.py): a
Strands `InterventionHandler` that validates every tool call against Decider 2B
before it runs.

```python
from strands import Agent
from wanderwise.decider_client import DeciderClient
from wanderwise.tool_router import DeciderToolRouter

router = DeciderToolRouter(
    client=DeciderClient("http://127.0.0.1:8000"),   # a running `strands-decider serve`
    tools={                                           # one line per tool
        "search_flights": "the user wants to find or book flights",
        "find_hotels":    "the user wants lodging or accommodation",
        "estimate_budget":"the user wants trip costs or a budget estimate",
    },
    confidence_threshold=0.85,   # only override the LLM above this confidence
)

agent = Agent(model=..., tools=[...], interventions=[router])
```

That's the whole integration. You supply (1) a running decider endpoint and
(2) a one-line description per tool. The typed question, the wiring into the
agent's path, and the confidence thresholding are all handled for you.

**What it decides, and how it behaves:**

| Situation | Action |
|---|---|
| Decider agrees with the LLM's tool | `Proceed` |
| Decider confidently picks a *different* tool (≥ threshold) | `Guide` the agent to the right tool |
| Decider leans another way but below threshold | `Proceed` (trust the LLM) |
| Decider endpoint unreachable | `Proceed` (fail-open, configurable) |

The typed question handed to Decider 2B is a **choice** question: `state` = the
user's latest message, `criteria` = your `{tool: description}` map. Decider
returns the best option plus a calibrated probability for *every* option.

## Why a decision model here (not just the LLM)

- **Calibrated confidence.** Bedrock's tool pick is a byproduct of generation
  with no trustworthy confidence number. Decider 2B returns one you can
  threshold on — so you *know* when to override and when to defer.
- **Cheap enough for the hot path.** ~92 ms, no tokens generated. You can afford
  to check *every* tool call, which you could never justify with a second LLM
  call.
- **A guardrail against confident-but-wrong routing.** When the LLM reaches for
  the wrong tool, the router catches it and redirects (see the redirect test).

## Repository layout

```
src/wanderwise/
  tool_router.py      ← THE reusable asset (DeciderToolRouter InterventionHandler)
  decider_client.py   ← dependency-light client for `strands-decider serve`
  tools.py            ← 5 travel tools (flights, hotels, activities, weather, budget)
  bedrock_provider.py ← Amazon Bedrock model (with cross-account AssumeRole support)
  agent.py            ← wires Bedrock + tools + router into a Strands Agent
  cli.py              ← `wanderwise` command
examples/
  decider_only_demo.py ← the routing decision alone (no Bedrock needed)
  full_agent_demo.py   ← full agent end-to-end (Bedrock + Decider)
tests/
  test_tool_router.py  ← proceed / redirect / low-confidence / fail-open
infra/                 ← Terraform: GPU EC2 that hosts Decider 2B + the agent
```

## Running it

### 1. Start the decision model (local GPU or CPU)

```bash
pip install strands-decider
strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 \
  --host 127.0.0.1 --port 8000
```

### 2a. See the routing decision alone (no AWS needed)

```bash
pip install -e .
python -m examples.decider_only_demo
```

```
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━┓
┃ User request        ┃ Routed tool        ┃ Conf. ┃ ms ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━┩
│ cheap flight to…    │ search_flights     │ 0.984 │ 96 │
│ where to stay in…   │ find_hotels        │ 0.972 │ 93 │
│ things to do in…    │ suggest_activities │ 0.898 │ 92 │
│ will it rain in…    │ check_weather      │ 0.977 │ 92 │
│ budget for 5 days…  │ estimate_budget    │ 0.958 │ 92 │
│ somewhere to sleep… │ find_hotels        │ 0.965 │ 92 │
└─────────────────────┴────────────────────┴───────┴────┘
6 decisions, avg latency 92 ms. No LLM tokens generated.
```

### 2b. Run the full agent (needs Amazon Bedrock)

Set these (see `.env`):

```bash
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0      # any Bedrock text model
BEDROCK_ASSUME_ROLE_ARN=                      # optional: cross-account role to assume
```

```bash
python -m examples.full_agent_demo "Recommend hotels in Kyoto for 3 nights"
#   ● Decider 2B: llm=find_hotels -> chose find_hotels (conf 0.962, 92 ms)
```

## Infrastructure (how the demo was run)

`infra/` provisions a single GPU EC2 (`g5.2xlarge`, NVIDIA A10G) that hosts
**both** halves: Decider 2B runs locally as a persistent `serve` process, and the
agent calls Amazon Bedrock. Because the compute account denies
`bedrock:InvokeModel` via an SCP, the instance **assumes a cross-account IAM
role** in a Bedrock-enabled account — see `bedrock_provider.py`. This is a
realistic pattern: run the cheap decision model on your own hardware, call the
managed LLM over the account boundary.

```bash
cd infra
terraform init
terraform apply   # auto-detects your IP, uses ~/.ssh/id_rsa.pub
```

## Notes on the experimental model

Decider 2B is an experimentation starter, not a production product. The questions,
the 0.85 threshold, and the fail-open policy here were chosen by hand for a
travel-planning demo — tune them for your own domain. On short classification
tasks, answers at ≥ 0.9 confidence are right ~95% of the time; below that,
WanderWise defers to the LLM.

## License

MIT — see [LICENSE](LICENSE).
