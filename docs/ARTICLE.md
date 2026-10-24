# WanderWise: letting a 2B decision model pick the tool, so Bedrock can do the talking

**Tags:** `#strands-decider-2b` `#tool-selection`

## The itch

I kept noticing the same thing building agents: the big model is wonderful at
*writing* — a warm travel itinerary, a tactful follow-up question — and
weirdly shaky at a tiny, mechanical decision buried inside the loop: *which tool
do I call?* It usually gets it right, but when it's wrong it's **confidently**
wrong, and it hands you no honest number to tell the two apart. A tool call is a
one-word decision wearing an expensive, uncalibrated, full-generation costume.

So for the Agent Experience Hackathon I built **WanderWise**, a travel planner
that keeps Amazon Bedrock for the talking and hands that one routing decision to
**Strands Decider 2B** — a small, open decision model that doesn't generate text
at all. It reads the user's message and a typed question and returns a *calibrated*
choice in about 92 milliseconds on a single GPU.

## What the agent does

Ask it normal travel things — "find me a cheap flight to Osaka", "where should I
stay in Kyoto for 4 nights?", "how much for 5 days in Reykjavik?" — and it calls
the right one of five tools (`search_flights`, `find_hotels`,
`suggest_activities`, `check_weather`, `estimate_budget`) and Bedrock (Amazon
Nova Pro) writes the reply. Ordinary on the surface. The interesting part is
underneath.

## The decision I handed to Decider 2B

**Pattern: tool selection.** Before any tool runs, Decider 2B answers one typed
*choice* question:

- **state:** the user's latest message
- **criteria:** `{ "search_flights": "the user wants to find or book flights",
  "find_hotels": "the user wants lodging…", … }` — one line per tool
- **answer:** the best tool **plus a probability for every option**

That last part is the whole point. Bedrock also "chooses" a tool, but its choice
is a byproduct of generation with no trustworthy confidence attached. Decider 2B
gives me a calibrated number I can threshold on. So the policy writes itself:

| Decider says… | WanderWise does… |
|---|---|
| same tool the LLM picked | **Proceed** |
| a *different* tool, ≥ 0.85 confidence | **Guide** the agent to the right tool |
| a different tool, but below 0.85 | **Proceed** — trust the LLM |
| (endpoint unreachable) | **Proceed** — fail open |

## The reusable asset: `DeciderToolRouter`

The hackathon asks for a decision pattern other builders can reuse, so I packaged
the whole thing as a Strands `InterventionHandler`. Dropping it into *any* Strands
agent is three lines plus a tool map:

```python
router = DeciderToolRouter(
    client=DeciderClient("http://127.0.0.1:8000"),
    tools={
        "search_flights": "the user wants to find or book flights",
        "find_hotels":    "the user wants lodging or accommodation",
        "estimate_budget":"the user wants trip costs or a budget estimate",
    },
    confidence_threshold=0.85,
)
agent = Agent(model=..., tools=[...], interventions=[router])
```

You bring a running `strands-decider serve` endpoint and a one-line description
per tool. The typed question, the `before_tool_call` wiring, the thresholding,
and a fail-open guard are all inside. When Decider disagrees confidently, the
handler returns Strands' `Guide` action with feedback like:

> *Do not call `search_flights` for this request. Strands Decider 2B routed this
> to `find_hotels` with 97% confidence. Call `find_hotels` instead.*

…and the agent corrects itself instead of running the wrong call.

## Does it actually work? (numbers)

Running the decision alone across six varied requests, on an NVIDIA A10G:

```
User request                     Routed tool          Conf.   ms
cheap flight to Tokyo            search_flights        0.984   96
where to stay in Kyoto           find_hotels           0.972   93
things to do in Lisbon (food)    suggest_activities    0.898   92
will it rain in Bali             check_weather         0.977   92
budget for 5 days in Reykjavik   estimate_budget       0.958   92
somewhere to sleep near Shibuya  find_hotels           0.965   92
```

Six for six, **~92 ms average, zero LLM tokens generated.** My favorite is the
last one — "somewhere to sleep near Shibuya station" has no word like "hotel" in
it, and the decision model still routes it to `find_hotels` at 0.965. It's
reading intent, not keywords.

And the redirect path, verified with a unit test that feeds the router a
deliberately wrong tool pick: user asks where to stay, the "LLM" reaches for
`search_flights`, and Decider overrides it to `find_hotels` at 0.972 — a `Guide`,
not a crash.

## How it's wired on AWS

One `g5.2xlarge` GPU instance hosts *both* halves: Decider 2B runs locally as a
persistent `serve` process (that's where the 92 ms comes from — load the weights
once, not per call), and the agent calls Amazon Bedrock. My build account denies
`bedrock:InvokeModel` via an SCP, so the instance **assumes a cross-account IAM
role** in a Bedrock-enabled account to make the call. That turned out to be a
realistic pattern worth sharing: run the cheap decision model on hardware you
control, reach the managed frontier model across an account boundary. All of it
is Terraform in the repo.

## What I learned

- **A calibrated confidence changes your architecture.** Once a decision is 92 ms
  and comes with an honest probability, you stop treating "which tool?" as
  something only the big model can do. You can afford to check *every* call.
- **Decision models read intent well at tiny cost.** The Shibuya example sold me.
- **Keep it fail-open.** A decision model in the hot path must never be able to
  break the agent — if the endpoint hiccups, WanderWise defers to the LLM and
  moves on.
- **The threshold is a product decision, not a default.** 0.85 felt right for
  travel routing; a safety-critical tool would want it higher.

Decider 2B is explicitly an experimentation starter, and that's exactly how it
felt — like getting a new, very fast primitive and figuring out where it belongs.
For WanderWise it belongs right in front of every tool call.

**Repo:** https://github.com/tinhtq/wanderwise-decider · **Demo video (under 3 min):** https://youtube.com/shorts/UfrEp9OFilI
