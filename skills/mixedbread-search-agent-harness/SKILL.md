---
name: mixedbread-search-agent-harness
description: >-
  Design, implement, review, or tune a custom harness for Mixedbread's Toast-1 search model through
  the OpenAI-compatible Completions API. Use when building bounded search-agent loops, custom
  retrieval or answer tools, parallel tool execution, evidence ranking and reporting, stable
  chunk-handle registries, context pruning, payload budgets, or evaluations for the model as a
  lookup subagent.
---

# Mixedbread Search Agent Harness

Toast-1 is Mixedbread's search model: a deep search and lookup agent trained to gather multi-hop evidence and submit ranked results. Build the harness for exploration, tool clarity, stable evidence identity, and bounded context — not for free-form general reasoning.

Scope: everything above one request — rounds, concurrency, evidence identity, context, termination. Use the loop as a fast search sub-agent for an orchestrator doing knowledge work, or as a standalone searcher. Orchestration remains outside this harness. For the API surface underneath (auth, request parameters, response shape, streaming, stored conversations, SDK extension fields), use the `mixedbread-search-agent` skill.

Docs: https://www.mixedbread.com/docs/agent/build-your-own-harness
Model card: https://www.mixedbread.com/docs/agent/models
Agent-readable docs: https://www.mixedbread.com/docs/llms.txt

## The loop

The API is stateless. Send a messages list plus tool schemas; the model returns text or tool calls. On `finish_reason="tool_calls"`, execute the calls, append **one tool message per call**, and resend the whole history. Build that exchange to these rules:

- **Budget rounds, terminal included.** The model is trained to work within a bounded number of turns, so state the boundary in the prompt instead of only enforcing it in code. On the final round, narrow the tool list to the terminal and force it by name; otherwise the model ends in prose and returns no structured payload. Count the terminal round: 4 rounds gives the model three searches.
- **Cap parallel calls, answer all of them.** The model fans out by design, and a round costs only the latency of its slowest call. Execute accepted calls concurrently, and emit a tool message for *rejected* calls too — an unanswered `tool_call_id` makes the next request invalid.
- **Budget payloads.** Clip result text as it enters the history, and bound the round as a whole. Eight uncapped returns in one round cross the input limit on their own.
- **Manage context in the harness.** Nothing prunes for you. Prune the message list you resend rather than summarizing it, and tell the model when it is over budget — see [Context management](#context-management).
- **Return every tool result as data.** A tool that raises leaves its call unanswered and breaks the next request; return `{"error": "..."}` so the model corrects itself on the following round.

```python
import asyncio
import json


async def run_episode(client, query: str) -> dict | str | None:
    messages = [{"role": "user", "content": query}]

    for round_index in range(MAX_ROUNDS):           # the terminal round is one of these
        final_round = round_index == MAX_ROUNDS - 1
        completion = await client.chat.completions.create(
            model="toast-1",
            messages=messages,
            tools=[TERMINAL] if final_round else TOOLS,
            tool_choice=(
                {"type": "function", "function": {"name": TERMINAL_NAME}}
                if final_round
                else "auto"
            ),
            parallel_tool_calls=not final_round,
            temperature=0.7,
            top_p=0.95,
            max_completion_tokens=4096,
            store=False,
        )
        message = completion.choices[0].message
        if not message.tool_calls:
            return message.content                  # finish_reason="stop": the run is done
        if final_round:
            if (
                len(message.tool_calls) != 1
                or message.tool_calls[0].function.name != TERMINAL_NAME
            ):
                raise RuntimeError("final round did not return exactly one terminal call")
            return validate_terminal(message.tool_calls[0])

        messages.append(message.model_dump(exclude_none=True))

        accepted = message.tool_calls[:MAX_PARALLEL_CALLS]
        results = await asyncio.gather(*(execute(call) for call in accepted))
        rejected = [over_cap_error(call) for call in message.tool_calls[MAX_PARALLEL_CALLS:]]

        # One tool message per emitted call, in the model's original call order.
        for call, result in zip(message.tool_calls, [*results, *rejected]):
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(clip(result))}
            )

        messages = prune_if_over_budget(messages)   # edit the list you resend

    raise RuntimeError("round budget exhausted without a terminal")
```

Bootstrap the episode: fetch metadata facets and one seed search concurrently before round 1 and inject both as tool results, so the model starts oriented without spending a round on it. Read [architecture.md](references/architecture.md) for round-by-round mechanics and [python-loop.md](references/python-loop.md) for the full implementation.

## Operating envelope

| Knob | Start at | Notes |
|------|----------|-------|
| Rounds | 4 total, terminal included | Soft; the model handles 8, 12, or more |
| Parallel calls per round | 8 | Pruning counts toward the cap |
| `temperature` / `top_p` | 0.7 / 0.95 | Trained defaults |
| Thinking | Disabled | Trained and served without it; not optional |
| Sequence length | 131,072 tokens | Keep every request's input under ~130,000 |
| Generation | Capped at 4,096 tokens | Size `max_completion_tokens` to the terminal payload |
| Prune trigger | ~50,000 prompt tokens | Budget notice fires every round past it |
| Hard prompt ceiling | ~100,000 tokens | Headroom, so a growing round cannot overshoot |
| Chunk clip | ~2,000 tokens | 4× that for expansion tools |
| Terminal retries | 2, then fail | Never substitute your own ranking |

Hold a ceiling with real headroom instead of aiming at the limit: overflow returns an opaque HTTP 500, not a context-length error, so no reactive recovery is possible. Track `usage.prompt_tokens` from each completion to measure how fast the history grows.

To grow exploration, **widen the round before deepening the loop**. A round already costs the latency of its slowest call, so parallel width is nearly free; an extra round costs a generation plus the prompt growth that follows it.

## Components

| Component | Owns |
|-----------|------|
| Generation adapter | Messages, tool schemas, sampling, final-turn flag. Keeps harness-only settings off the wire |
| Tool registry / executor | Name → schema + implementation, argument validation, per-round cap, concurrent execution, structured errors |
| Evidence registry | Identity → stable `chunk_id` / `document_id`; tracks seen, visible, pruned, restored |
| Context budgeter | Token counting, clipping, per-call and per-round budgets, redaction of pruned payloads |
| Episode controller | Bootstrap, round loop, termination, terminal validation and retry |

## Evidence identity

Assign a short handle (`c12`, not a UUID) at first sight and never reassign it. For better search diversity, consider deduplicating ordinary search results against evidence already shown to the agent; the backend does not do cross-call deduplication for you.

Accept only handles you actually emitted in expansion, pruning, and terminal tools. Validate the final submission against the registry rather than trusting the enum, and never silently substitute a harness ranking for the model's.

## Context management

- **Prune, do not summarize.** Inference is optimized for a stable prompt prefix with stale payloads removed. A summary rewrites the prefix and pays generation latency to lose evidence detail.
- **Tell the model.** State the pruning contract in the system prompt, then append a budget notice every round past the trigger: the estimated token count, the tool to call, that pruning may run **in parallel** with searches, and that finishing is the other valid answer. Copy the exact message from [reference-harness.md](references/reference-harness.md).
- **Preserve handles after pruning.** Remove content, not identity.
- **Keep the prefix byte-stable.** A clock time or a full-precision score in the prompt changes every request and invalidates the cache on its own.
- **Never combine pruning with `previous_completion_id` in one turn.** That field restores context only while the messages extend the stored history unchanged; a pruned history silently falls back to text-only.

## Tool design

Write descriptions as operating instructions: name the matching mechanism (semantic, BM25, RE2 regex, metadata filter, lookup), the preferred input form, and one contrasting misuse. Keep arguments flat, snake_case, and JSON-native; use `Literal`/enum for closed modes; publish bounds in the description. In Python, docstrings become tool descriptions and `Annotated` strings become parameter descriptions.

Return JSON objects carrying the echoed query, candidate count, and results — never prose. Read [tool-contracts.md](references/tool-contracts.md) for the full contracts.

## Evaluation

Record per episode: rounds and calls per round; prompt, completion, and peak input tokens as reported by `usage`; per-tool latency and the slowest call per round; queries, result counts, duplicate suppression, clipping, truncation, pruning; rounds that passed the budget trigger without pruning or submitting; invalid arguments, structured recoveries, forced-terminal attempts, unresolved IDs; final ranked IDs, scores, and nDCG/recall.

Compare on fixed queries and fixed corpus snapshots. Raise depth, width, or payload limits one dimension at a time.

## Don't

- Don't name a harness tool `submit_answer`. Reserved — HTTP 422.
- Don't detect termination by tool name. A finished run is `finish_reason="stop"` with content; a harness terminal only appears when forced by name.
- Don't let a tool exception escape the executor, or leave an assistant tool call without a matching tool message.
- Don't substitute a harness ranking for the model's submission. Validate against the registry, retry bounded, then fail.
- Don't enable thinking, or build logic on `reasoning_content`.
- Don't reach for the terminal with prompt wording alone. `tool_choice="required"` produces no visible call either — force it by name.
- Don't prune silently, and don't wait for the ceiling. A budget notice missing "this may run in parallel" costs a whole search round.
- Don't execute independent calls serially.
- Don't leave payloads uncapped. Eight uncapped returns in one round fill the context before the third.
- Don't count the terminal turn outside the round budget. At 3 rounds a searcher gets two searches.
- Don't attach an instruction to the round label. "Search round 2 of max 4" as bare state; a nudge to submit teaches the model to wait for the countdown.
- Don't let expansion tools return as little text as search. At ~4× the clip they are worth calling; below that they are not.
- Don't let the model filter on unconfirmed metadata, or rank on fields not confirmed numeric.
- Don't reorder tool messages relative to the model's call order, even when execution finishes out of order.
- Don't force the model to consume every round after it has enough evidence.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Loop exhausts its round budget every episode | Termination detected by tool name | Treat `finish_reason="stop"` with content as the ending |
| Opaque HTTP 500 mid-episode | Input over the sequence length | Hold a hard ceiling near 100,000 and clip round payloads into it |
| Terminal returns prose | Not forced by name | `tool_choice={"type": "function", "function": {"name": ...}}` |
| Model ignores the context limit | No budget signal reaches it | Contract in the system prompt + a per-round notice naming the token count |
| A budget notice costs a whole search round | Notice does not say pruning can run in parallel | Say it explicitly, and note that pruning counts toward the call cap |
| Latency spikes with no quality gain | Serial execution, or depth added instead of width | Run calls concurrently; raise parallel calls before rounds |
| Prefix cache hit rate collapses | Timestamp, full-precision score, or summarized history in the prompt | UTC date only, round scores, prune instead of summarizing |
| Context full after 2-3 rounds | Uncapped tool payloads | Clip to ~2,000 tokens per result and bound the round |
| Model re-searches ground it covered | Results carry no stable handles | Assign short handles at first sight and never reassign |
| Model re-requests pruned evidence | Prune semantics never stated | Say whether pruned chunks can resurface and which tool restores them |
| One large payload starves the round | No per-call budget | Spread-truncate in presentation order with a per-item floor |

## References

- [architecture.md](references/architecture.md) — read before designing or reviewing a loop: round choreography, parallel execution, context management, and evidence identity.
- [tool-contracts.md](references/tool-contracts.md) — read before defining tool schemas or result envelopes.
- [python-loop.md](references/python-loop.md) — read when implementing the loop with the OpenAI Python client.
- [reference-harness.md](references/reference-harness.md) — read when choosing budgets, prompts, or pruning policy, or when a run burns rounds, clips evidence, or ignores the context limit. What Mixedbread's production harness does, and why.
