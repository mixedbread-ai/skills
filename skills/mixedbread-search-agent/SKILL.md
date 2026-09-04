---
name: mixedbread-search-agent
description: >-
  Call Mixedbread's Toast-1 search model through the OpenAI-compatible Chat Completions and
  Responses APIs. Use when choosing between the hosted store tools (search_corpus, grep,
  filter_chunks, inspect_metadata, get_chunks, list_stores) and your own function tools,
  authenticating against the completions endpoint, setting request parameters and Mixedbread
  extension fields (include, max_tool_calls, context_management), answering function tool calls,
  choosing a terminal mode, streaming, continuing stored conversations with previous_completion_id
  or previous_response_id, or debugging completions errors such as duplicate_tool_name,
  store scope validation, context_length_exceeded, or SDK extension fields.
---

# Mixedbread Search Agent

Toast-1 is Mixedbread's search model: a deep search and lookup agent trained end-to-end to gather evidence and answer from it — as a ranked evidence list, ranked evidence plus an answer, or a plain-text answer. It is served over two OpenAI-compatible endpoints, Chat Completions and Responses, and takes two kinds of tools:

- **Hosted store tools** — `search_corpus`, `grep`, `filter_chunks`, `inspect_metadata`, `get_chunks`, `list_stores`. Opt-in per request; the server runs the whole search loop over your Mixedbread Stores and the request returns with the answer. They share names, schemas, and behavior with the open-source [toast-harness](https://github.com/mixedbread-ai/toast-harness).
- **Function tools** — ordinary `function` schemas your application executes and feeds back, so the corpus can live anywhere: Stores, a vector DB, Elasticsearch, SQL, or the filesystem.

A request without hosted tools is one generation over exactly what you sent.

Docs: https://www.mixedbread.com/docs/agent/chat-completions and https://www.mixedbread.com/docs/agent/responses
Harness guide: https://www.mixedbread.com/docs/agent/build-your-own-harness
API reference: https://www.mixedbread.com/api-reference/endpoints/chat/create-chat-completion and https://www.mixedbread.com/api-reference/endpoints/responses/create-response
Model card: https://www.mixedbread.com/docs/agent/models
Agent-readable docs: https://www.mixedbread.com/docs/llms.txt

## Choose a path

| You want | Do | Read |
|----------|----|------|
| Search-grounded answers over Stores, no retrieval code | One request with hosted tools in `tools`; the answer is the text | [Hosted store tools](#hosted-store-tools), [hosted-tools.md](references/hosted-tools.md) |
| Hosted retrieval plus your own functions or a structured ending | Hosted tools and `function` tools in one request; force the terminal on a follow-up turn with `previous_completion_id` | [hosted-tools.md § Hybrid](references/hosted-tools.md#hybrid-hosted-retrieval-your-terminal) |
| Your own backend and your own loop | Declare only `function` tools and run a bounded loop | `mixedbread-search-agent-harness` skill, [tool-contracts.md](references/tool-contracts.md) |
| Your own loop with Stores as the backend | Function tools wired to the Stores API | [mixedbread-tools.md](references/mixedbread-tools.md) |
| A ranked chunk list or a cited answer with no completions call | `stores.search(search_options={"agentic": True})` or `stores.question_answering()` | `mixedbread-search` skill |

Both endpoints take the same tools and extensions. The Responses API is the primary surface for hosted tools and stored conversations; Chat Completions is the message-based surface and the one to bring your own harness to. This skill is written against Chat Completions; [Responses API](#responses-api) maps the differences.

## Authentication

Get an API key at https://platform.mixedbread.com/platform?next=api-keys, then:

```bash
export MXBAI_API_KEY=mxb_xxxxx
```

**Pass the key explicitly.** The OpenAI SDKs default to `OPENAI_API_KEY` and know nothing about `MXBAI_API_KEY`; without an explicit `api_key`/`apiKey` the client either sends the wrong key or raises a missing-credentials error at construction.

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://api.mixedbread.com/v1",
    api_key=os.environ["MXBAI_API_KEY"],
)
```

```typescript
import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: 'https://api.mixedbread.com/v1',
  apiKey: process.env.MXBAI_API_KEY!,
});
```

The endpoints are `POST https://api.mixedbread.com/v1/chat/completions` and `POST https://api.mixedbread.com/v1/responses`, so the base URL keeps the `/v1`. A scope-restricted key needs the Completions scope. Any OpenAI-compatible client works if it allows a custom base URL and an escape hatch for extension fields.

## Making a request

```python
completion = client.chat.completions.create(
    model="toast-1",
    messages=[{"role": "user", "content": "Which contract governs the 2019 agreement?"}],
    tools=TOOLS,            # hosted tool entries, function schemas, or both
    temperature=0.7,
    top_p=0.95,
    store=False,            # completions are stored by default
)

message = completion.choices[0].message
if message.tool_calls:
    ...                     # your function calls: execute, append results, send the next request
else:
    print(message.content)  # finish_reason == "stop": the run is done
```

| Parameter | Send | Notes |
|-----------|------|-------|
| `model` | `"toast-1"` | Also the default when omitted |
| `messages` | Full history, or only the new suffix with `previous_completion_id` | Sent as-is: nothing is added or removed. Roles: `system`, `developer` (handled as system instructions), `user`, `assistant`, `tool` |
| `tools` | Hosted entries such as `{"type": "search_corpus", ...}`, `function` schemas, or both | No tools: one generation from the prompt alone |
| `tool_choice` | `"auto"` (default), `"none"`, `"required"`, `{"type": "function", "function": {"name": ...}}`, or a hosted type: `search_corpus`, `grep`, `filter_chunks`, `inspect_metadata`, `list_stores` (**not** `get_chunks`) | With hosted tools it applies to the first model turn; later turns of the server loop use `auto` |
| `parallel_tool_calls` | `true` (default) | The model fans out by design; `false` on a forced terminal turn |
| `temperature` / `top_p` | `0.7` / `0.95` | Recommended, not API defaults — send them explicitly. Ranges 0–2 and 0–1 |
| `max_completion_tokens` | Omit | Generation defaults to 4,096, minimum 16; raise it when you need more. `max_tokens` is a deprecated alias, honored only when this is absent |
| `store` | `false` to retain no conversation content | **Defaults to `true`.** Must be `true` on any completion you continue later. Operational model and token metadata is recorded either way |
| `stream` | Optional | See [Streaming](#streaming) |
| `metadata` | Optional | Up to 16 string key-value pairs (keys ≤64 chars, values ≤512), echoed back on the response |

Mixedbread extension fields go in `extra_body` in Python and inline with a cast in Node (the SDK forwards them unchanged):

| Field | Purpose |
|-------|---------|
| `previous_completion_id` | Continue a stored completion; restores its full model context — hosted calls and server-side context edits included |
| `max_tool_calls` | Cap on server-executed calls (hosted tools and `prune_context`) in one completion; default 16, minimum 1; ignored when none are declared |
| `context_management` | `{"edits": [{"type": "prune_context"}]}` opts into server-side context editing; see [Context management](#context-management) |
| `include` | Chunk payloads on hosted call items: `search_corpus_call.results`, `grep_call.results`, `filter_chunks_call.results`, `get_chunks_call.results`, plus `transcript` for the full stored conversation. `inspect_metadata_call.facets` and `list_stores_call.stores` always come back. Unsupported values are ignored |

Unknown fields are ignored; `chat_template_kwargs` is not a parameter.

```python
second = client.chat.completions.create(
    model="toast-1",
    messages=[{"role": "user", "content": "And when does it expire?"}],
    tools=TOOLS, store=True,
    extra_body={"previous_completion_id": first.id, "include": ["search_corpus_call.results"]},
)
```

```typescript
// Node takes extension fields inline; there is no extra_body option.
const second = await client.chat.completions.create({
  model: 'toast-1',
  messages: [{ role: 'user', content: 'And when does it expire?' }],
  tools, store: true,
  previous_completion_id: first.id, include: ['search_corpus_call.results'],
} as never);
```

## Reading the response

| Field | Value |
|-------|-------|
| `choices[0].finish_reason` | `"tool_calls"` — execute your functions and continue; `"stop"` — the answer is in `content`; `"length"` — cut by the output limit, or a hosted run that spent its tool-call or context budget without a plain-text answer |
| `choices[0].message.content` | The answer text on `"stop"` |
| `choices[0].message.tool_calls[]` | Your function calls only: `id`, `function.name`, `function.arguments` (a JSON **string**). Hosted calls never appear here |
| `choices[0].message.reasoning_content` | Always `null`: toast-1 runs with thinking disabled. Nothing to display, strip, or replay |
| `hosted_tool_calls[]` | One item per server-executed call, in order: `type` (`search_corpus_call`, …), `id`, `status` (`in_progress`, `completed`, `failed`), `error` `{code, message}` when it failed. There is no `arguments` field — each type echoes its own arguments (`queries`, `pattern`, `chunk_ids`, …) and carries `results` (or `facets`/`stores`); see [hosted-tools.md](references/hosted-tools.md) |
| `context_management.applied_edits[]` | Present only when an edit was applied: a `prune_context` entry aggregating the model's prunes, and a `truncate_tool_result` entry per client tool result the server shortened in overflow recovery |
| `usage` | `prompt_tokens` sums every hidden hosted round; `prompt_tokens_details.cached_tokens` counts prefix-cache hits; `completion_tokens_details.reasoning_tokens` is always `0` |
| `id`, `title` | `id` is the next turn's `previous_completion_id`; `title` is a display title derived from the first words of the conversation's first user message |

The Python SDK parks extension fields in `model_extra`:

```python
hosted = (completion.model_extra or {}).get("hosted_tool_calls") or []
edits = ((completion.model_extra or {}).get("context_management") or {}).get("applied_edits") or []
```

## Hosted store tools

```python
completion = client.chat.completions.create(
    model="toast-1",
    messages=[{"role": "user", "content": "Which products cost less than 100, and what are their prices?"}],
    tools=[
        {"type": "search_corpus", "store_identifiers": ["product-catalog"]},
        {"type": "grep", "store_identifiers": ["product-catalog"]},
    ],
    store=False,
    extra_body={"max_tool_calls": 8, "include": ["search_corpus_call.results"]},
)
print(completion.choices[0].message.content)
for call in (completion.model_extra or {}).get("hosted_tool_calls") or []:
    print(call["type"], call["status"], call.get("error"),
          [c["chunk_id"] for c in call.get("results") or []])
```

| Rule | Detail |
|------|--------|
| Opt-in per request | A hosted tool runs only when its entry is in `tools`. To bring your own backend, list none of them |
| One scope | Every store-scoped tool takes `store_identifiers`, and all declared store tools must share one scope; mixed scopes are rejected. Omit it to open the scope: `list_stores` becomes required, and each store tool takes a required `store` argument the model fills per call |
| Budget | `max_tool_calls` (default 16) bounds the server-executed calls; at most 8 run per model turn, extra calls get a structured error |
| How a run ends | On a plain-text reply, or a call to one of your function tools (returned to you). At the budget the model is told once to answer in plain text from what it has; if it does neither, the completion ends with `finish_reason="length"` and the text produced so far. The API never writes an answer for the model |
| Default instructions | With a hosted tool declared and no system text, the model gets a two-sentence default system message; any instruction text you send replaces it entirely |
| Chunk references | `chunk_id = "<file_id>:<chunk_index>"`, stable across requests; every chunk also carries a `document_id`. The `file_id` resolves against the store files API |
| Name collisions | A function tool may not share the name of a declared hosted tool (`duplicate_tool_name`) |

Per-tool fields and defaults, result shapes, streaming, citations, and complete examples in Python and TypeScript are in [hosted-tools.md](references/hosted-tools.md).

## Function tools

Tools are ordinary `function` schemas. What to declare and how to describe them is in [tool-contracts.md](references/tool-contracts.md); backing them with Mixedbread Stores is in [mixedbread-tools.md](references/mixedbread-tools.md).

`finish_reason="tool_calls"` means the model is waiting on you. Send exactly one `tool` message per `tool_call_id` — including for calls you rejected or that failed; an assistant tool call with no matching `tool` message makes the next request invalid. Continuing with `previous_completion_id`, the tool messages are the whole next request; resending the history yourself, append the assistant turn first.

Serialize results as JSON, never prose, and return failures as data: a tool that raises past the executor leaves its call unanswered and breaks the next request, while `{"error": "..."}` lets the model correct itself on the following round.

```python
messages.append(message.model_dump(exclude_none=True))
for call in message.tool_calls:
    try:
        result = IMPLEMENTATIONS[call.function.name](**json.loads(call.function.arguments or "{}"))
    except Exception as exc:                  # never let a tool raise past the executor
        result = {"error": str(exc), "retryable": True}
    messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
```

```typescript
messages.push(message);
for (const call of message.tool_calls ?? []) {
  let result;
  try {
    result = await run(call);
  } catch (error) {
    result = { error: error instanceof Error ? error.message : String(error), retryable: true };
  }
  messages.push({ role: 'tool', tool_call_id: call.id, content: JSON.stringify(result) });
}
```

## Terminal modes

The model was trained on three ways to end a run. Pick the one your application consumes and say so in the prompt:

| Mode | Declare | The run ends with |
|------|---------|-------------------|
| Ranking only | A `submit_ranking` function with `chunks[{chunk_id, relevance_score}]` and `ranking_strategy` | The model calls `submit_ranking` itself once the evidence suffices; your application answers from the ranked chunks |
| Ranking plus answer | The same function with a required `answer` string | One structured call carrying evidence and answer |
| Plain-text answer | No reporting tool; `tool_choice="auto"`; instruct that every response must contain tool calls until it answers and that a plain-text reply ends the run | `content` with `finish_reason="stop"` |

When the round budget runs out, force the terminal with a short user message and `tool_choice` by name, continuing the stored completion:

```python
final = client.chat.completions.create(
    model="toast-1",
    messages=[{"role": "user", "content": "You have reached the search limit. Do NOT search further. Call submit_ranking now."}],
    tools=[SUBMIT_RANKING],
    tool_choice={"type": "function", "function": {"name": "submit_ranking"}},
    parallel_tool_calls=False,
    extra_body={"previous_completion_id": last.id},
)
submission = json.loads(final.choices[0].message.tool_calls[0].function.arguments)
```

The schema and the trained wording are in [tool-contracts.md](references/tool-contracts.md#terminal-tool). A hosted run ends in plain text at its search limit, so over hosted retrieval this forced turn is the normal way to get the structured payload — recipe in [hosted-tools.md](references/hosted-tools.md#hybrid-hosted-retrieval-your-terminal).

## Context management

```python
extra_body={"context_management": {"edits": [{"type": "prune_context"}]}}
```

| Declared | Not declared |
|----------|--------------|
| The model gets a `prune_context` tool over every tool result it has read, server or client, and clears stale results as the conversation approaches the window. Accepted with any tool set, a no-op until something prunable accumulates; prune calls count against `max_tool_calls`. `context_management.applied_edits` reports what was cleared; the stored conversation keeps every tool result as sent, and `previous_completion_id` stays valid | Nothing is edited. An oversized request fails with `422 context_length_exceeded_error`, never a silent truncation; a stateless loop prunes the history it resends, and after such edits must resend the full history without `previous_completion_id` |

Declaring it is the answer to context pressure in every shape: a hosted run manages its own results, and a bring-your-own-backend loop gets the same tool over its function results. Managing context yourself is only for a stateless loop (`store=False`) whose prunes must survive across turns.

## Stored conversations

```python
first = client.chat.completions.create(model="toast-1", messages=messages, tools=TOOLS, store=True)

second = client.chat.completions.create(
    model="toast-1",
    messages=[{"role": "user", "content": "And when does it expire?"}],   # only the new suffix
    tools=TOOLS, store=True,
    extra_body={"previous_completion_id": first.id},
)
```

| Rule | Detail |
|------|--------|
| `store` defaults to `true` | Every completion is retrievable unless you send `store=False` |
| Send only the new suffix | The stored context is restored from `previous_completion_id`; do not resend the assistant turn it already holds |
| Configuration is not stored | Only the conversation is. `tools`, sampling parameters, and `context_management` go with every request |
| Hosted context comes back | Hosted calls, their results, and server-side context edits are restored — the only way a later turn can cite hosted evidence |
| Edited the history yourself? | Resend all of it without `previous_completion_id`; the request is honored exactly as sent |
| One chain, one conversation | Completions joined by `previous_completion_id` group into one conversation for listing, and `DELETE /v1/chat/completions/{id}` removes every turn in it |

## Streaming

```python
stream = client.chat.completions.create(
    model="toast-1", messages=messages, tools=TOOLS, stream=True, store=False,
)
for chunk in stream:
    for call in (chunk.model_extra or {}).get("hosted_tool_calls") or []:   # once in_progress, once finished
        show_progress(call["type"], call["status"], call.get("error"))
    for choice in chunk.choices:            # hosted-progress chunks arrive with choices == []
        if choice.delta.content:
            show_answer(choice.delta.content)
```

Streamed function calls arrive as `delta.tool_calls` fragments and must be accumulated by index before execution. `context_management` arrives on the final usage chunk. Non-streaming and streaming report identical final content.

## Responses API

The same model, tools, and extensions over `POST /v1/responses`, and the primary documentation surface for the hosted tools:

```python
response = client.responses.create(
    model="toast-1",
    input="Which suppliers had recalls in 2023?",
    tools=[{"type": "search_corpus", "store_identifiers": ["my-store"]}],
    include=["search_corpus_call.results"],
    extra_body={"context_management": {"edits": [{"type": "prune_context"}]}},
)
print(response.output_text)
```

| Responses | Chat Completions |
|-----------|------------------|
| `input` (a string or items) and `instructions` | `messages` |
| Flat function tools `{"type": "function", "name", "description", "parameters", "strict"}`; calls arrive as `function_call` output items; reply with `function_call_output` items carrying the `call_id` | `tools[].function`, `message.tool_calls`, `tool` messages |
| `previous_response_id` (the chain needs `store: true`); new `instructions` replace the previous response's | `previous_completion_id` |
| `hosted_tool_calls` beside `output` | `hosted_tool_calls` beside `choices` |
| `status: "incomplete"` with `incomplete_details.reason` in `max_output_tokens`, `max_tool_calls`, `context_window` | `finish_reason: "length"` |
| `max_output_tokens` | `max_completion_tokens` |
| `GET /v1/responses/{id}` (also `stream`, `starting_after`), `GET /v1/responses/{id}/input_items`, `DELETE /v1/responses/{id}` — deleting also deletes the persisted conversation chain | `GET`/`DELETE /v1/chat/completions/{id}` |
| Unsupported options fail validation: `background: true`, `truncation: "auto"`, structured `text.format`, and multimodal input | Unknown fields are ignored |

Streaming emits the standard semantic events plus `response.output_item.added`/`done` for each hosted call; a terminal `response.completed` or `response.incomplete` carries the full response. Hosted items are an extension: they claim an `output_index` in the shared item order but land in `hosted_tool_calls`, not `output`, so do not index `output` by `output_index`.

## Limits

| Limit | Value | Consequence |
|-------|-------|-------------|
| Context window | 131,072 tokens | Input, tool definitions, tool results, and output share it; an oversized request fails with `422 context_length_exceeded_error` |
| Output | 4,096 tokens by default; larger `max_completion_tokens` accepted | `finish_reason="length"` when hit |
| Server-executed calls | `max_tool_calls` (default 16), at most 8 per turn | Extra calls get a structured error; at the cap the model is asked for a plain-text answer |
| Thinking | Disabled at the chat template | `reasoning_content` is always `null`, `reasoning_tokens` always `0`; `chat_template_kwargs` is not a parameter |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 401 / invalid API key | Client fell back to `OPENAI_API_KEY` | Pass `api_key`/`apiKey` explicitly |
| 404 on the request | Base URL missing `/v1` | `https://api.mixedbread.com/v1` |
| 422 naming the tool entry `type` | Unknown `type` on a tool entry | Use `function` or one of the six hosted types |
| 422 `duplicate_tool_name` | A function tool shares a declared hosted tool's name | Rename the function, or drop the hosted entry |
| 422 on `store_identifiers` | Store tools with different scopes, or an open scope without `list_stores` | One scope for all store tools; add `{"type": "list_stores"}` when omitting `store_identifiers` |
| 422 `context_length_exceeded_error` | The request does not fit the context window | Prune or clip the history and retry, or declare `context_management` |
| `TypeError: unexpected keyword argument` | Extension passed at the top level in Python | Move it into `extra_body` |
| Own backend, but `hosted_tool_calls` is non-empty | A hosted entry is in `tools` | List only `function` tools |
| `422 status code (no body)` in Node | The SDK discards the error body | Wrap `fetch` and log `response.clone().text()` on failure — it names the field at fault |
| Next request rejected as invalid | An assistant tool call has no matching `tool` message | Emit one per `tool_call_id`, including for rejected calls |
| Hosted run ends in prose although `submit_ranking` was declared | The search limit asks for a plain-text answer | Force the terminal on a follow-up turn with `previous_completion_id` |
| Forced terminal cites handles that do not exist | The forced turn was sent stateless after hosted retrieval | `store=True` on the search request, `previous_completion_id` on the forced turn |
| `finish_reason="length"` with truncated JSON | Terminal payload exceeded the output limit | Ask for fewer chunks or raise `max_completion_tokens`, then retry the forced turn |
| `finish_reason="length"` on a hosted run, no answer | Tool-call or context budget spent without a plain-text reply | Raise `max_tool_calls`, or declare `context_management` |
| `previous_completion_id` seems ignored | Prior call used `store=False`, or the resent history was edited | Store the completion you continue; after your own edits resend everything without it |
| `TypeError` on `function.arguments` | Treated as a dict | It is a JSON string — parse it |

## References

- [hosted-tools.md](references/hosted-tools.md) — read when declaring hosted store tools: per-tool fields and defaults, call item and result shapes, `include`, streaming, citations, the hybrid recipe, complete Python and TypeScript examples.
- [tool-contracts.md](references/tool-contracts.md) — read before writing any function tool schema: primitives, description patterns, the schema generator, result envelope, stable handles, error envelope, the terminal tool and its three modes. Backend-agnostic.
- [mixedbread-tools.md](references/mixedbread-tools.md) — read when backing function tools with Mixedbread Stores yourself: the call behind each primitive, filters, chunk identity, gotchas.
