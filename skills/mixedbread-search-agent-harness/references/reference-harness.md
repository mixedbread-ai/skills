# What Mixedbread's own harness does

Behaviors from the harness Mixedbread runs in production against this model. Numbers are tuned starting points, not limits of the model.

## Signal context pressure to the model

The harness never prunes silently and never waits for the ceiling. The system prompt sets the contract before any pressure exists:

> Call prune_context to remove chunk content irrelevant to your assigned aspect. Keep the context window small; you have a limited token budget.

Every round past the trigger then carries a user message:

> Context budget notice: your current prompt is estimated at 63400 tokens, over your context budget. Include prune_context among your tool calls this round to remove content you no longer need -- it may run in parallel with other tools -- or call submit_ranking if you are done.

| Clause | Why it is there |
|--------|-----------------|
| A concrete token count | The model weighs a number against the evidence it holds; "running low" gives it nothing |
| The tool named | No inference required |
| "May run in parallel with other tools" | Without it the model burns a whole turn pruning and searching nothing |
| "Or call submit_ranking if you are done" | Finishing is the other correct response to pressure |
| Identical at every pressure level | Escalating wording teaches the model to wait for the loud version |

Also: pruning counts toward the parallel-call cap, so say so in the system prompt or the model plans a round that gets rejected. And a round past the trigger with neither a prune nor a submission is recorded and scored — signaling pressure is worth nothing if nothing measures the response.

State the persistence rule, which differs by harness shape:

| Shape | Rule |
|-------|------|
| One-shot searcher | Pruned chunks stay in the seen index, never return from normal search; only expansion restores content |
| Multi-turn conversation | The prune list clears on the next user message, so pruned chunks may resurface as fresh results |

## Label rounds without instructing

From round 2 on, a bare marker follows the previous round's tool results:

```
Search round 2 of max 4.
```

"of max", not "of" — a bound the model may stop short of, not a quota. No instruction attached: a per-round nudge to submit teaches it to wait for the countdown instead of stopping when the evidence is sufficient.

## Other behaviors

| Behavior | Detail |
|----------|--------|
| Bootstrap | Metadata facets + one seed search on the original query, fetched concurrently before round 1 and injected as tool results in stable facets-then-search order |
| Spread truncation | Oversized calls truncate in presentation order, earlier results keep more, every item keeps a 512-token floor, nothing is deferred |
| Grep windows | ±100 tokens around **every** match, not a head clip |
| Expansion clip | 4× the search clip, so expansion is worth calling |
| Published bounds | "maximum 20 chunk ids" in the description; without it the model guesses and the call is rejected |
| Prefix stability | Runtime date is a UTC date, never a clock time (tested: 00:00:01 and 23:59:59 of one day produce identical strings); prompt-rendered scores rounded to 2 significant figures without mutating the results |
| Width over depth | Raise parallel calls before rounds — a round already costs its slowest call |
| Terminal failure | Append the assistant message, a tool error, and a correction naming the validation error; retry twice, then return no ranking |
| Metadata gating | Filters only from bootstrap facets, an inspection result, or metadata on retrieved results; numeric ranking only on confirmed numeric fields |
| Score comparison | Scores from different tools are not comparable — rank by intent and evidence, not raw score |

## Numbers at a glance

| Knob | Value | Note |
|------|------:|------|
| Searcher rounds | 4 | Submit turn included |
| Parallel calls per round | 8 | Pruning counts toward it |
| Chunk clip, search tools | 2,000 tokens | |
| Chunk clip, expansion tools | 8,000 tokens | 4× search |
| Grep match window | ±100 tokens | Around every match |
| Per-call payload ceiling | 30,000 / 40,000 / 32,000 | Semantic / metadata listing / expansion; sized so a default-shaped call never clips |
| Prune trigger | 50,000 | Notice fires every round past it |
| Hard prompt ceiling | 100,000 tokens | Round payloads truncate to stay under |
| Per-round payload ceiling | 96,000 tokens | Effective bound is usually headroom |
| Minimum item allocation | 512 tokens | Floor under spread truncation |
| Terminal retries | 2 | Then fail explicitly |
