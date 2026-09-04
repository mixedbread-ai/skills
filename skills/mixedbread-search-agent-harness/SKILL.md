---
name: mixedbread-search-agent-harness
description: >-
  Design, implement, review, or tune a custom harness for Mixedbread's Toast-1 search model over
  the OpenAI-compatible Chat Completions API with your own retrieval tools. Use when building
  bounded search-agent loops, custom retrieval or answer tools, parallel tool execution, evidence
  ranking and reporting, terminal modes (ranking only, ranking plus answer, plain-text answer),
  stable chunk-handle registries, stored-completion continuation with previous_completion_id,
  declared context_management, payload budgets, offline tests with a scripted client, or
  evaluations for the model as a lookup subagent.
---

# Mixedbread Search Agent Harness

Toast-1 is Mixedbread's search model: a deep search and lookup agent trained end-to-end to gather multi-hop evidence and answer from it. This skill is the **bring-your-own-backend** path: you declare `function` tools, execute them, and run the loop. A request without hosted tools is one generation over exactly what you sent, so the loop is your whole harness. If Mixedbread Stores is the corpus and you need no custom tools, the hosted store tools (`search_corpus`, `grep`, `filter_chunks`, `inspect_metadata`, `get_chunks`) run the same loop server-side in one request — use the `mixedbread-search-agent` skill for that, and for the API surface underneath this loop (auth, parameters, extension fields, streaming, stored conversations).

Scope: everything above one request — rounds, concurrency, evidence identity, context, termination. Use the loop as a fast search sub-agent for an orchestrator doing knowledge work, or as a standalone searcher. Orchestration stays outside the harness.

Docs: https://www.mixedbread.com/docs/agent/build-your-own-harness
Model card: https://www.mixedbread.com/docs/agent/models
Reference harness the model was trained in — prompts, tool schemas, budgets: https://github.com/mixedbread-ai/toast-harness
API reference: https://www.mixedbread.com/api-reference/endpoints/chat/create-chat-completion

## What the model actually requires

Everything below separates into three kinds of statement. Read the rest of this skill through them.

| Kind | What |
|------|------|
| **Required** — break these and the run breaks | One tool message per `tool_call_id`; `function` tools only (a hosted entry runs server-side instead); errors returned as data, never raised; stable handles the model can re-reference, and ID-taking tools that accept only handles you emitted; the model ends the run and you enforce the cap |
| **Trained** — not enforced, but the policy expects them | The name `submit_ranking` and its `{chunks, ranking_strategy, answer}` shape; `prune_context` taking `ids`; the terminal alone in its turn; answers grounded only in retrieved evidence |
| **Ours** — everything else here | Round and call budgets, payload sizes, tool sets, component layout, envelope fields. Toast adapts to a different shape — a different tool set, a longer budget, a framework loop like Pi. Change one dimension at a time and measure |

## The loop

Send the prompt plus tool schemas; the model returns text or tool calls. On `finish_reason="tool_calls"`, execute the calls, append **one tool message per call**, and send the next request. Build that exchange to these rules:

- **Continue the stored completion.** Completions are stored by default. Send `previous_completion_id` and only the new messages — the tool results and the round label. The server restores the rest, so do not resend the assistant turn; your tool messages answer its `tool_call_id`s. It stores the conversation, not the request configuration: `tools`, sampling parameters, and `context_management` still go with every request. A loop that must not store anything sends `store=False` and resends the full history instead.
- **Declare `context_management`.** `{"edits": [{"type": "prune_context"}]}` on every request gives the model a `prune_context` tool over your tool results; the response reports what it cleared. See [Context management](#context-management).
- **Budget rounds, terminal included.** State the boundary in the prompt the same way the code enforces it. A 4-round ceiling is three search rounds plus the terminal turn.
- **The model ends the run; you enforce the cap.** Under a ranking mode it calls `submit_ranking` itself once the evidence suffices; under plain text it replies without tool calls. When the round budget runs out, force the terminal turn by name. A prose reply where a ranking was expected means the model considers itself done — force the terminal once rather than correcting and burning rounds.
- **Cap parallel calls, answer all of them.** Execute accepted calls concurrently, emit a tool message for rejected calls too, and keep the model's call order. An unanswered `tool_call_id` makes the next request invalid.
- **Budget payloads.** Clip result text as it enters a tool message and bound the round as a whole. Eight uncapped returns in one round cross the input limit on their own; an oversized request fails with `422 context_length_exceeded_error`.
- **Return every tool result as data.** A tool that raises leaves its call unanswered and breaks the next request; `{"error": "..."}` lets the model correct itself on the following round.

```python
structured = answer_mode != "plain_text"                    # "plain_text" | "submit_ranking" | "none"
require_answer = answer_mode == "submit_ranking"
new = [system(prompt), user(query)]                         # every later request sends only the new messages
for round_index in range(1, MAX_ROUNDS):                    # round MAX_ROUNDS is the terminal turn
    if round_index > 1:
        new.append(user(f"Search round {round_index} of max {MAX_ROUNDS}."))
    terminal = [terminal_schema(evidence.visible_ids(), require_answer=require_answer)] if structured else []
    choice = await complete(client, episode, new, tools=[*search_tools, *terminal], tool_choice="auto")   # + previous_completion_id, context_management
    calls = list(choice.message.tool_calls or [])
    if structured and calls and calls[0].function.name == TERMINAL and len(calls) == 1:
        return validate_terminal(calls[0].function.arguments, evidence, require_answer=require_answer)   # the normal ending
    if not calls:                                            # prose: the model is done
        if not structured:
            return choice.message.content
        new = []
        break                                                # structured: force the terminal now
    new = await execute_round(tools, calls)                  # concurrent; one tool message per call
return await finish(client, episode, new, answer_mode=answer_mode)   # forced terminal or tools-off answer
```

The complete, runnable version — tools, registry, executor, continuation, terminal validation, retries, and an offline self-test — is [python-loop.md](references/python-loop.md). Read it before implementing; the skeleton above omits the correction paths.

## Answer modes

Pick the ending before writing the prompt; [python-loop.md](references/python-loop.md) takes it as `--answer-mode`.

| Mode | Use it for | Prompt rule | Terminal schema | Terminal turn at the cap | Validate |
|------|------------|-------------|-----------------|--------------------------|----------|
| `none` — ranking only | A lookup subagent whose parent synthesizes; ranking evaluation (nDCG, recall) | "call submit_ranking in its own turn as soon as the evidence supports it" | `chunks[{chunk_id, relevance_score}]`, `ranking_strategy` | Only the terminal declared, `tool_choice={"type": "function", "function": {"name": ...}}`, `parallel_tool_calls=False` | Handles in the registry, no duplicates, scores in `[0, 1]` |
| `submit_ranking` — ranking plus answer | An end-user answer delivered with its evidence | Same, "with your answer" | Same, plus a **required** `answer` with the trained description | Same | Same, plus a non-empty `answer` |
| `plain_text` | Chat answers; an orchestrator that reads prose | "every response must contain tool calls until you answer; a plain-text reply with no tool calls ends the run; do not report chunk lists or rankings" | None | `tool_choice="none"` with the search tools still declared; take `content` | Non-empty content, no calls |

- Offer the terminal alongside the search tools from round 1. The model calls it on its own once the evidence suffices; the forced turn is the cap fallback, not the normal path.
- In every mode, tell the model to base the answer only on retrieved evidence and to say so when it is insufficient.
- For a fixed-length ranking (`strict_top_k`), add `minItems`/`maxItems` and tell the model to fill a weak tail with the next-best retrieved chunks.
- Name the terminal `submit_ranking`, the trained name.
- On failure in any mode: a tool-error message per call (a correction message after prose) naming the validation error, retry twice, then fail. Never substitute a harness ranking for the model's.
- `finish_reason="length"` means the payload was cut: correct with "answer more briefly" or fewer chunks, or raise `max_completion_tokens` (4,096 is the default, not a ceiling).

## Prompt

The loop enforces the boundaries; the prompt has to state them too, or the model works against you. Six rules carry it, and they hold over any tool set:

| Rule | Wording that works |
|------|--------------------|
| Name each tool by its mechanism, with one contrasting misuse | "matches literal text, not meaning" next to "for focused semantic search" — the model picks between primitives on stated contrast |
| Publish the call width | "Use at most 8 tool calls in one turn, including retrieval and pruning tools" |
| State the round ceiling as a ceiling | "You have at most 4 rounds (the terminal turn is one of them). It is a ceiling, not a quota" |
| Make ending the model's job | "End the episode yourself: call `submit_ranking` in its own turn as soon as the evidence supports it, at latest in your final round. Never wait to be told to submit" |
| Rank for intent, from emitted handles only | "Rank for the user's intent, not just the search score"; "use only chunk_id values that appeared in your tool results"; an empty list when nothing is relevant |
| Ground the answer | "based only on retrieved evidence; if the evidence is insufficient to answer, say so" |

From round 2 on, mark the round with bare state and nothing else — `Search round 2 of max 4.` A nudge to submit attached to that line teaches the model to wait for the countdown instead of stopping when the evidence is sufficient.

The prompts the model was trained against are in [toast-harness](https://github.com/mixedbread-ai/toast-harness) — `src/agent_harness/searcher_prompts.py`, with the budgets beside them in `config.py` and runnable API examples under `completions/`. Read them for phrasing; their tool set is not a specification, and porting it is not the point.

## Operating envelope

| Knob | Start at | Notes |
|------|----------|-------|
| Rounds | 4 total, terminal included | Soft; the model handles 8, 12, or more |
| Parallel calls per round | 8 | Your cap on function calls; server-side `prune_context` calls never reach you |
| `temperature` / `top_p` | 0.7 / 0.95 | Recommended, not API defaults — the API leaves them unset, so send them |
| `max_completion_tokens` | Omit | Defaults to 4,096; raise it for a large terminal payload |
| `store` | Omit (`true`) | Required for `previous_completion_id`; delete the chain afterwards when retention is not wanted |
| Context window | 131,072 tokens | Input, tool schemas, results, and output share it; overflow is a `422 context_length_exceeded_error` |
| Chunk clip | ~2,000 tokens | 4× that for expansion tools |
| Terminal retries | 2, then fail | Never substitute your own ranking |

Track `usage.prompt_tokens` from each completion to measure how fast the context grows. To grow exploration, **widen the round before deepening the loop**: a round already costs the latency of its slowest call, so parallel width is nearly free, while an extra round costs a generation plus the prompt growth that follows it.

## Components

Something has to own each of these, wherever you put it: the wire (new messages, tool schemas, sampling, `previous_completion_id`, `context_management`), tool dispatch (argument validation, the per-round cap, concurrency, structured errors), evidence identity (handles, seen and visible), payload budgets, and the round loop with its termination and terminal validation. Five objects, one class, or an agent framework you already run — all fine.

## Evidence identity

Assign a short handle (`c12`, not a UUID) at first sight and never reassign it. Accept only handles you actually emitted in expansion and terminal tools. Deduplicate ordinary search results against evidence already shown; the backend does not do cross-call deduplication for you, and diversity improves recall.

Bootstrap is optional and saves a round: seed the prompt with metadata facets and one search on the raw query, fetched concurrently before round 1. Insert both as labeled ordinary context, never as synthetic assistant tool calls or `role="tool"` messages — those roles mean the model spent a turn.

## Parallel execution

| Concern | Approach |
|---------|----------|
| Independent calls | `asyncio.gather` / task groups; sync tools via `asyncio.to_thread` |
| Message ordering | Preserve the model's call order even when completion order differs |
| Payload allocation | Bound the round, and keep one large result from starving its siblings — a floor per item. Any fair split works |
| Shared state | Duplicate suppression and ID assignment must be concurrency-safe |
| Throughput | Track provider QPS separately from model-visible call width |
| Cancellation | Cancel in-flight calls when the episode is cancelled |

## Context management

The API manages it. Declare this on every request and the model gets a `prune_context` tool over your function results; you do not build one:

```python
extra_body={"context_management": {"edits": [{"type": "prune_context"}]},
            "previous_completion_id": episode.completion_id}      # after the first request
```

| Who | Does |
|-----|------|
| The API | Offers the model its `prune_context` tool over every tool result it has read, yours included; prunes only what the model sees, never what is stored; keeps `previous_completion_id` valid; reports `context_management.applied_edits` — one `prune_context` entry with `calls` and `cleared_input_tokens`, plus a `truncate_tool_result` entry per client result it shortened in overflow recovery. A prune that frees nothing is not reported |
| You | Clip results as they enter a tool message, keep handles resolvable so a pruned chunk can still be ranked or re-fetched, and read `applied_edits` into your trace |

- **Pruning compounds only across a continued chain.** Prunes applied in an earlier request stay applied, and each `usage.prompt_tokens` reflects them. A full-history resend rebuilds the context from your messages, and pruned content comes back.
- **Prune, do not summarize.** Inference is optimized for a stable prompt prefix with stale payloads removed. A summary rewrites the prefix and pays generation latency to lose evidence detail.
- **Pruning removes content, not identity.** Keep the envelope and the handle; let an expansion tool restore the text, and let the terminal rank a pruned ID — the model already judged it.
- **Keep the prefix byte-stable.** A clock time or a full-precision score in the prompt changes every request and invalidates the cache on its own.
- **Manage context yourself only when `store=False` and prunes must survive across turns.** Then you resend the pruned history — never with `previous_completion_id` — and follow the trained `prune_context` shape in [tool-contracts.md](references/tool-contracts.md). Signal pressure with a user message that gives the token count, names the tool, says it may run in parallel with searches, and offers finishing as the alternative — and keep that wording identical at every pressure level, or the model learns to wait for the loud version.

## Tool design

Write descriptions as operating instructions: name the matching mechanism (semantic, BM25, RE2 regex, metadata filter, lookup), the preferred input form, and one contrasting misuse. Keep arguments flat, snake_case, and JSON-native; use `Literal`/enum for closed modes; publish bounds in the description. Generate the schema from the docstring and `Annotated` hints rather than hand-writing it — [python-loop.md](references/python-loop.md) ships a `tool_schema` helper. Return JSON objects, never prose.

## Pi as the harness

If the application already uses [Pi](https://github.com/earendil-works/pi), the loop exists: Pi runs the tool-call loop, executes the tools, and manages context. Add Toast as a custom model in `~/.pi/agent/models.json` — an `openai-completions` provider, `baseUrl` `https://api.mixedbread.com/v1`, `MXBAI_API_KEY`, context window `131072`, max output `4096`, `temperature` 0.7 / `top_p` 0.95, thinking off — and register tools with `pi.registerTool({name, description, parameters, execute})`, `parameters` being the JSON schema. Every rule in [tool-contracts.md](references/tool-contracts.md) applies unchanged. One caveat: Pi's built-in compaction summarizes the history rather than dropping it; budget it against the input limit and prefer prune-style removal of stale tool results.

## Testing

Spend no completions on the loop's logic. `python-loop.md` ships a `Scripted` client that stands in for `chat.completions.create`, records every request and response, and plays back responses — a plain object, or a callable of the request for responses that need a handle minted at runtime:

```python
client = Scripted([
    fake_response(calls=[("bm25_search", {"query": "firmware modbus"}), ("grep", {"pattern": "ETH-1"})]),
    lambda request: fake_response(calls=[(TERMINAL, {"chunks": [{"chunk_id": first_handle(request), "relevance_score": 0.9}],
                                                     "ranking_strategy": "top hit", "answer": "Firmware 3.2"})]),
])
result = await run_episode(client, "Which firmware adds Modbus TCP?", corpus=corpus, answer_mode="submit_ranking")
assert client.requests[1]["extra_body"]["previous_completion_id"] == client.responses[0].id
assert [m["role"] for m in client.requests[1]["messages"]] == ["tool", "tool", "user"]   # only the new messages
```

Assert on `client.requests`: each request continues the previous completion and carries `context_management`; only the new messages are sent; one tool message per emitted call; rejected calls answered with `parallel_call_limit_exceeded`; invalid arguments returned as data; the terminal forced by name at the cap with `answer` required only under `submit_ranking`; corrections after an invalid payload. Keep a fixed corpus of a dozen short documents with distractors and five queries whose relevant chunks you know; record one live run per query as fixtures for regression, and re-run live only when the prompt or tools change.

## Evaluation

Three measures carry most of the signal: ranking quality on fixed queries (nDCG, recall), `usage.prompt_tokens` growth per round, and how often a run needed the forced terminal. Add what your own failure modes call for — invalid arguments, unresolved handles, per-tool latency, tokens cleared by `applied_edits`.

Compare on fixed queries and fixed corpus snapshots. Raise depth, width, or payload limits one dimension at a time.

## Don't

- Don't declare a hosted store tool (`{"type": "search_corpus", ...}`) in a bring-your-own-backend loop — it runs server-side. List only `function` tools.
- Don't expect anything but the prompt, the terminal, and your round cap to end the run.
- Don't send `previous_completion_id` with a history you edited yourself; resend all of it without it.
- Don't send `store=False` on a completion you mean to continue.
- Don't let expansion tools return as little text as search — if they return no more than a search hit, the model has no reason to call them.
- Don't let the model filter on unconfirmed metadata, or rank on fields not confirmed numeric.
- Don't force the model to consume every round after it has enough evidence.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Loop exhausts its round budget every episode | Termination detected by tool name, or the terminal not offered until the last round | Accept `submit_ranking` as the sole call on any round; treat `finish_reason="stop"` with content as the ending |
| Every episode needs the forced turn | Prompt never says when to call `submit_ranking`, or the terminal is missing from `tools` on search rounds | Offer it alongside the retrieval tools and say "call submit_ranking in its own turn as soon as the evidence supports it" |
| `hosted_tool_calls` non-empty, `usage.prompt_tokens` huge | A hosted tool entry is in `tools` | Declare only `function` tools |
| Next request rejected as invalid | An assistant tool call has no matching `tool` message, or the new messages do not extend the stored history | One tool message per `tool_call_id`, including rejected calls; send only what follows the previous completion |
| `previous_completion_id` seems ignored | The completion it names was sent with `store=False`, or the history was edited client-side | Store the completion you continue; after your own edits resend everything without it |
| Model treats bootstrap as a completed search round | Bootstrap encoded as tool protocol messages | Send labeled ordinary pre-round context; do not synthesize assistant calls or `role="tool"` results |
| `422 context_length_exceeded_error` mid-episode | The request no longer fits | Declare `context_management`; clip results harder; in a stateless loop prune and retry |
| Terminal returns prose at the cap | Not forced by name | `tool_choice={"type": "function", "function": {"name": ...}}` with only the terminal declared |
| Terminal arguments are truncated JSON | `finish_reason="length"` | Correct with "fewer chunks", or raise `max_completion_tokens` |
| `applied_edits` never appears | Nothing prunable has accumulated yet, or `context_management` is not on the request | Declare it on every request; it is a no-op until tool results pile up |
| Latency spikes with no quality gain | Serial execution, or depth added instead of width | Run calls concurrently; raise parallel calls before rounds |
| Prefix cache hit rate collapses | Timestamp, full-precision score, or summarized history in the prompt | UTC date only, round scores, prune instead of summarizing |
| Context full after 2-3 rounds | Uncapped tool payloads | Clip to ~2,000 tokens per result and bound the round |
| Model re-searches ground it covered | Results carry no stable handles | Assign short handles at first sight and never reassign |
| Model re-requests pruned evidence | Prune semantics never stated | Say whether pruned chunks can resurface and which tool restores them |
| One large payload starves the round | No per-call budget | Spread-truncate in presentation order with a per-item floor |

## References

- [python-loop.md](references/python-loop.md) — read before implementing: the complete runnable loop with local tools, registry, stored-completion continuation, declared `context_management`, the three answer modes, terminal validation, retries, and an offline self-test.
- [tool-contracts.md](references/tool-contracts.md) — read before defining tool schemas or result envelopes; includes the docstring-to-schema generator and the terminal modes.
