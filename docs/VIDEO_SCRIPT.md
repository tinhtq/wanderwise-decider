# WanderWise — demo video script (target: 2:40, hard cap 3:00)

Format: screen recording of a terminal SSH'd into the GPU EC2, with voiceover.
Keep the terminal font large. Have the `strands-decider serve` process already
running in another pane (so latency is warm ~92 ms, not the ~46 s cold load).

Pre-roll setup (not recorded):
```bash
ssh -i ~/.ssh/id_rsa ubuntu@<EC2_IP>
cd /opt/wanderwise && source .venv/bin/activate
# confirm server is warm:
curl -s http://127.0.0.1:8000/health
```

---

## [0:00–0:20] Hook + what this is

**On screen:** the README diagram (User → Bedrock → Decider 2B → tool).

**Say:**
> "This is WanderWise, a travel agent. Amazon Bedrock writes the answers — but
> the decision of *which tool to call* doesn't go to Bedrock. It goes to Strands
> Decider 2B, a 2-billion-parameter decision model that answers in about ninety
> milliseconds, with a calibrated confidence. Let me show you."

## [0:20–1:00] The decision, alone

**Do:**
```bash
python -m examples.decider_only_demo
```

**Say (while the table renders):**
> "No LLM here — just the decision model. Six travel requests, and it routes
> every one to the right tool: flights, hotels, activities, weather, budget.
> Average ninety-two milliseconds, zero tokens generated. Look at the last row —
> 'somewhere to sleep near Shibuya station.' No word like 'hotel' anywhere, and
> it still picks find_hotels at 0.96. It's reading intent, not keywords."

**On screen:** cursor-highlight the Shibuya row and the "avg latency 92 ms" line.

## [1:00–1:50] The full agent (Bedrock + Decider together)

**Do:**
```bash
python -m examples.full_agent_demo "Recommend hotels in Kyoto for 3 nights"
```

**Say:**
> "Now the whole agent. Bedrock — Amazon Nova Pro — proposes a tool call. Before
> it runs, my intervention asks Decider 2B to check it."

**On screen:** highlight the line:
`● Decider 2B: llm=find_hotels -> chose find_hotels (conf 0.962, 92 ms)`

**Say:**
> "Decider agrees — find_hotels at 0.96 — so it proceeds, the tool runs, and
> Bedrock writes the friendly reply. Every tool call in this agent passes through
> that ninety-millisecond check. You could never afford that with a second LLM
> call."

## [1:50–2:25] The money shot — the redirect

**Say:**
> "The point isn't when they agree. It's when the big model is confidently
> wrong."

**Do:** (run the redirect unit scenario / a crafted prompt)
```bash
python -m pytest tests/test_tool_router.py::test_redirect_when_decider_confidently_disagrees -q
# or show the live snippet that prints the Guide feedback
```

**On screen:** show the printed feedback:
> *"Do not call search_flights for this request. Strands Decider 2B routed this
> to find_hotels with 97% confidence. Call find_hotels instead."*

**Say:**
> "Here the LLM reached for search_flights on a lodging question. Decider caught
> it at 97% confidence and guided the agent back to find_hotels — before the
> wrong call ever ran. That's a calibrated guardrail sitting in the hot path."

## [2:25–2:40] The reusable asset + close

**On screen:** scroll `src/wanderwise/tool_router.py` to the 3-line usage block.

**Say:**
> "And it's reusable. Drop this DeciderToolRouter into any Strands agent: give it
> a decider endpoint and one line per tool, and you've moved tool selection off
> the LLM. Repo and write-up are linked below. That's WanderWise — small model
> for the decision, Bedrock for the conversation."

**End card:** repo URL + `#strands-decider-2b #tool-selection`.

---

### Shot checklist
- [ ] Decider server warm before recording (health check returns ok)
- [ ] `decider_only_demo` table fully visible, Shibuya row highlighted
- [ ] `full_agent_demo` shows the green `● Decider 2B` proceed line
- [ ] redirect feedback text clearly readable
- [ ] tool_router.py usage snippet on screen
- [ ] total runtime under 3:00
