---
name: mixedbread-search-agent-harness
description: >-
  Design, implement, review, or tune a custom harness for Mixedbread's Toast-1 search model
  with your own retrieval backend or agent framework. Use for exploration strategy,
  parallel execution, evidence identity, context budgets, termination, and retrieval evaluation.
  For endpoint parameters or hosted Stores tools, use mixedbread-search-agent.
---

# Mixedbread Search Agent Harness

Docs: https://www.mixedbread.com/docs/agent/build-your-own-harness
API: https://www.mixedbread.com/api-reference/endpoints/chat/create-chat-completion
Model: https://www.mixedbread.com/docs/agent/models
Public training harness: https://github.com/mixedbread-ai/toast-harness

Toast gathers evidence through tools and returns a ranking, an answer, or both. It can work
with different retrieval backends, tool sets, output formats, budgets, and agent frameworks.
The public harness is a useful implementation reference; reproducing it is not a condition
for good performance. The design guidance below describes preferences to evaluate on your task.

## API constraints and design choices

The API's accepted schemas and fixed model behavior are constraints: use `toast-1`, keep thinking
disabled, and stay within the context window and supported parameter ranges. The hosted model
already disables thinking; `chat_template_kwargs` is not an API setting. When continuing a
Chat Completions tool turn, supply one result per `tool_call_id`, including failed or rejected
calls. Stored continuation requires that the preceding completion was stored.

Tool names such as `search_corpus` and `submit_ranking`, short handles, JSON result envelopes,
prompt wording, round limits, storage strategy, and component layout are design choices.
Use the `mixedbread-search-agent` skill or the API reference above for wire contracts.

If your corpus is in Mixedbread Stores, hosted retrieval can run the search loop for you.
For your own backend, declare client `function` tools and execute them in your application.
A function **named** `search_corpus` calls your implementation; the hosted entry
`{"type": "search_corpus"}` calls Mixedbread Stores. Hybrid applications can combine hosted
and custom tools, provided their declared names do not collide.

## Exploration and tool design

- Encourage parallel searches for independent aspects, entities, and alternative wording.
  Use later rounds for questions that depend on earlier evidence. Wider exploration can reduce
  latency, but still costs backend capacity and context; choose width and depth together.
- Describe what each tool actually matches and how to phrase its input. Semantic retrieval
  benefits from focused natural-language questions; literal lookup needs exact terms or patterns.
  Adapt descriptions whenever you change the backend.
- Prefer a small, clear tool surface. Add metadata discovery, filtering, or expansion when the
  task benefits from them; the training harness's individual tools are not a required checklist.
- Confirm available metadata before filtering or sorting on it. Keep application access scope
  enforced by the backend. If a requested sort cannot be applied, report that fact in the result.
- Optional bootstrap context, such as a seed search or metadata overview, can save exploration.
  Labeled ordinary context is a simple way to provide it without simulating a model tool turn.

Descriptions and example result shapes are in [tool-contracts.md](references/tool-contracts.md).
The public [prompts](https://github.com/mixedbread-ai/toast-harness/blob/main/src/agent_harness/searcher_prompts.py)
and [implementation](https://github.com/mixedbread-ai/toast-harness/tree/main/src/agent_harness)
provide detail when you want to inspect a particular design.

## Evidence identity and context

Keep evidence references stable across tools and rounds, with provenance available to the
application. Short handles can help, but existing backend IDs also work. Validate cited or
ranked references against evidence presented to the model.

Deduplicating ordinary retrieval results across calls often improves coverage and saves context.
Coordinate deduplication after parallel retrieval, or synchronize shared state. Repeated exact
lookups can instead return compact references, and expansion can restore previously seen text.
Deduplication and pruning are separate policies: state whether suppressed evidence can resurface.

Distinguish evidence that was **presented**, **discarded before presentation**, and **pruned after
presentation**. Register results as seen after payload trimming; discarded results remain eligible
for retrieval. Pruning can remove text while preserving identity and a route to re-fetch it.

We recommend the API's server-side pruning even for a fully custom harness. Enable
`context_management={"edits": [{"type": "prune_context"}]}` on each request. It works over both
hosted and custom tool responses; you do not need to implement the public harness's pruning tool.
Stored continuation carries these context edits forward. The API skill's Context management
section explains continuation and stateless alternatives.

Also bound result payloads and their combined size before sending them. Allocate enough space
across concurrent calls to avoid one large result consuming the whole round. Under context pressure,
prefer fewer useful passages over many unreadably short fragments; leave discarded hits eligible
for later retrieval. Expansion should provide useful additional context; pattern searches should
retain the matching passage when clipped.
Prefer pruning stale payloads and keeping stable prompt prefixes where practical. Summarization
is another option; evaluate its evidence loss, latency, and reference-restoration behavior.

## Ending and budgets

Choose an ending the application can consume. A terminal function such as `submit_ranking` is
convenient for structured evidence; an ordinary answer can finish a prose workflow. The public
harness's three modes are examples in [tool-contracts.md](references/tool-contracts.md#terminal-tools).
Other names and payloads are valid choices.

Offer the chosen terminal during exploration so the model can finish when evidence suffices.
Tell it to ground answers in retrieved evidence and acknowledge gaps. For rankings, compare
evidence against the user's intent: scores from different retrieval tools are not directly
comparable, and metric-order requests may need ordering by a value in the evidence.

Pick round, call, payload, and correction budgets for your latency and quality needs, and explain
the chosen limits in the prompt. Count the final answer turn explicitly; any correction allowance
should also be explicit. A short round marker can make the remaining budget clear. For a structured
ending at the cap, forcing its function by name is a useful fallback. Validate the payload and
return clear errors for bounded correction; expose failure if recovery is exhausted.

The public harness's defaults are starting points, not model limits. Likewise, `temperature=0.7`
and `top_p=0.95` are recommended sampling values, not fixed requirements. Tool schemas, input,
results, and output share the context window; leave headroom for the next generation.

## Examples and evaluation

Use [python-loop.md](references/python-loop.md) when you want a small runnable Python example.
It is optional: keep your existing framework or build a different loop when that fits your application.
The upstream [API examples](https://github.com/mixedbread-ai/toast-harness/tree/main/completions)
show other arrangements of retrieval and orchestration; check API fields against current docs.

Use scripted responses to check protocol handling, terminal validation, parallel deduplication,
payload limits, and unseen versus pruned evidence. Then compare prompts and tools on fixed queries
and corpus snapshots. Track retrieval quality (recall/nDCG), answer grounding when relevant,
end-to-end and per-tool latency, input/output tokens, duplicates, clipping/truncation, context edits,
and forced endings. Choose improvements from measured task performance.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Repeated searches yield the same evidence | Stable identity and deduplication across calls, including concurrent ones |
| Irrelevant results after a backend change | Tool descriptions and query guidance match the new retrieval mechanism |
| Relevant matches disappear from results | Clipping retains the useful passage; discarded results are not registered as seen |
| Context grows too quickly | Aggregate payload limits, server-side pruning, and duplicate content |
| Every run needs a forced ending | The terminal is available during exploration and the prompt explains when to finish |
| Partial answer is treated as final | Check `finish_reason`; `length` is incomplete even when content is non-empty |
| Invalid tool turn on continuation | One result for every emitted call ID; only new messages with stored continuation |
| More calls add cost without quality | Measure overlap, independent coverage, and whether another sequential hop is needed |
