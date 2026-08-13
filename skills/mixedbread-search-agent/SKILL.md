---
name: mixedbread-search-agent
description: >-
  Call Mixedbread's Toast-1 search model through the OpenAI-compatible Chat Completions API.
  Use when authenticating against the Mixedbread completions endpoint, setting request parameters,
  declaring function tools and answering tool calls, forcing a structured terminal, streaming
  responses, continuing stored conversations with previous_completion_id, or debugging completions
  errors such as reserved tool names, context overflow, or SDK extension fields.
---

# Mixedbread Search Agent

Toast-1 is Mixedbread's search model: a deep search and lookup agent that fans out parallel searches, phrases its own queries across languages, recovers from tool errors, and stops when the evidence is sufficient. It is served over an OpenAI-compatible Chat Completions endpoint.

Toast-1 has no retrieval of its own. Every tool is a Chat Completions `function` your application declares, executes, and feeds back, so the corpus can live in Mixedbread Stores, a vector DB, Elasticsearch, SQL, or the filesystem.

Docs: https://www.mixedbread.com/docs/agent/chat-completions
Model card: https://www.mixedbread.com/docs/agent/models
Agent-readable docs: https://www.mixedbread.com/docs/llms.txt

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

The endpoint is `POST https://api.mixedbread.com/v1/chat/completions`, so the base URL keeps the `/v1`. Any Chat Completions-compatible client works if it allows a custom base URL and an escape hatch for extension fields.

## Making a request

```python
completion = client.chat.completions.create(
    model="toast-1",
    messages=[{"role": "user", "content": "Which contract governs the 2019 agreement?"}],
    tools=TOOLS,
    temperature=0.7,
    top_p=0.95,
    parallel_tool_calls=True,
    store=False,
)

message = completion.choices[0].message
if message.tool_calls:
    ...          # execute them, append results, send the next request
else:
    print(message.content)     # finish_reason == "stop": the run is done
```

| Parameter | Send | Notes |
|-----------|------|-------|
| `model` | `"toast-1"` | The served search model |
| `messages` | Full history, every request | The endpoint is stateless |
| `temperature` / `top_p` | `0.7` / `0.95` | Trained defaults; configurable |
| `tools` | Your `function` schemas | No built-in retrieval |
| `tool_choice` | `"auto"`, or a named function | Named forcing is the only route to a structured terminal |
| `parallel_tool_calls` | `true` | The model fans out by design |
| `max_completion_tokens` | `4096` or less | Generation is capped at 4,096 tokens |
| `store` | `false`, or `true` to continue later | Stored completions are retrievable by conversation |
| `previous_completion_id` | Extension field | Python needs `extra_body`; Node takes it inline |
| `stream` | Optional | Deltas carry `content` and `reasoning_content` |

## Reading the response

| Field | Value |
|-------|-------|
| `choices[0].finish_reason` | `"tool_calls"` — execute and continue; `"stop"` — the answer is in `content` |
| `choices[0].message.content` | The answer text, on `"stop"` |
| `choices[0].message.tool_calls[]` | `id`, `function.name`, `function.arguments` (a JSON **string**) |
| `choices[0].message.reasoning_content` | Search narration for display. Not the answer, not a place to hang logic |
| `id` | Pass as `previous_completion_id` on the next request when `store=True` |
| `usage` | Prompt and completion tokens |

Read `reasoning_content` defensively in Python — the SDK may park it in the extras bag:

```python
narration = getattr(message, "reasoning_content", None) or (message.model_extra or {}).get("reasoning_content")
```

## Tool calls

Tools are ordinary `function` schemas. What to declare and how to describe them is in [tool-contracts.md](references/tool-contracts.md); backing them with Mixedbread Stores is in [mixedbread-tools.md](references/mixedbread-tools.md).

`finish_reason="tool_calls"` means the model is waiting on you. Append the assistant message, then exactly one `tool` message per `tool_call_id` — including for calls you rejected or that failed. An assistant tool call with no matching `tool` message makes the next request invalid.

Serialize results as JSON, never prose, and return failures as data: a tool that raises past the executor leaves its call unanswered and breaks the next request, while `{"error": "..."}` lets the model correct itself on the following round.

```python
messages.append(message.model_dump(exclude_none=True))
for call in message.tool_calls:
    try:
        result = IMPLEMENTATIONS[call.function.name](**json.loads(call.function.arguments or "{}"))
    except Exception as exc:            # never let a tool raise past the executor
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
    result = {
      error: error instanceof Error ? error.message : String(error),
      retryable: true,
    };
  }
  messages.push({
    role: 'tool',
    tool_call_id: call.id,
    content: JSON.stringify(result),
  });
}
```

## Structured terminals

The model ends in prose by default. For ranked evidence or a JSON payload, declare a reporting function under any name except the reserved `submit_answer`, and force it by name:

```python
final = client.chat.completions.create(
    model="toast-1",
    messages=[*messages, {"role": "user", "content": "Do not search further. Report the answer now."}],
    tools=[report_evidence],
    tool_choice={"type": "function", "function": {"name": "report_evidence"}},
    parallel_tool_calls=False,
    store=False,
)
submission = json.loads(final.choices[0].message.tool_calls[0].function.arguments)
```

Prompt wording alone loses to a prose ending most of the time, and `tool_choice="required"` produces no visible call.

## Stored conversations

```python
first = client.chat.completions.create(model="toast-1", messages=messages, tools=TOOLS, store=True)
messages.append(first.choices[0].message.model_dump(exclude_none=True))
messages.append({"role": "user", "content": "And when does it expire?"})

second = client.chat.completions.create(
    model="toast-1", messages=messages, tools=TOOLS, store=True,
    extra_body={"previous_completion_id": first.id},
)
```

```typescript
// Node takes extension fields inline — there is no extra_body option.
const second = await client.chat.completions.create({
  model: 'toast-1', messages, tools, store: true,
  previous_completion_id: first.id,
} as never);
```

| Rule | Detail |
|------|--------|
| Send the full history anyway | `previous_completion_id` restores hidden prior context; it does not replace `messages` |
| Requires `store=True` on the prior call | Otherwise there is nothing to restore |
| Only extends unchanged history | A pruned or edited history silently falls back to stateless text-only mode |
| Edits win | If the supplied history contradicts the stored one, the supplied history is used |
| Deletion is chain-wide | Deleting any completion joined by `previous_completion_id` destroys the rest of that thread |

## Streaming

```python
stream = client.chat.completions.create(
    model="toast-1", messages=messages, tools=TOOLS, stream=True, store=False,
)
for chunk in stream:
    for choice in chunk.choices:            # some chunks arrive with choices == []
        narration = getattr(choice.delta, "reasoning_content", None) or (
            getattr(choice.delta, "model_extra", None) or {}
        ).get("reasoning_content")
        if narration:
            show_narration(narration)
        if choice.delta.content:
            show_answer(choice.delta.content)
```

Streamed tool calls arrive as `delta.tool_calls` fragments and must be accumulated by index before execution. Empty `choices` lists are normal, so guard every access rather than dropping the chunk.

## Limits

| Limit | Value | Consequence |
|-------|-------|-------------|
| Sequence length | 131,072 tokens | Keep each request's input under ~130,000 |
| Generation | Capped at 4,096 tokens per completion | Size the terminal payload to fit |
| Overflow | Opaque HTTP 500 | Not a context-length error — clip tool results before appending them |
| Thinking | Disabled | Trained and served without it; `reasoning_content` is display narration only |
| `submit_answer` | Reserved tool name | Declaring it fails with HTTP 422 |
| Context management | None | The API prunes nothing; the history you send is the context |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 401 / invalid API key | Client fell back to `OPENAI_API_KEY` | Pass `api_key`/`apiKey` explicitly |
| 404 on the request | Base URL missing `/v1` | `https://api.mixedbread.com/v1` |
| HTTP 422 `'submit_answer' is reserved` | Declared a tool with the reserved name | Rename your terminal |
| `TypeError: unexpected keyword argument` | Extension passed at the top level in Python | Move it into `extra_body` |
| Opaque HTTP 500 | Input over the sequence length | Keep the input under ~130,000 tokens; clip tool results before appending them |
| `422 status code (no body)` in Node | The SDK discards the error body | Wrap `fetch` and log `response.clone().text()` on failure — it names the field at fault |
| Next request rejected as invalid | An assistant tool call has no matching `tool` message | Emit one per `tool_call_id`, including for rejected calls |
| Terminal returns prose, no structured payload | Relied on the prompt or `tool_choice="required"` | Force the terminal by name |
| Loop never terminates | Termination detected by tool name | Detect `finish_reason="stop"` with content |
| `previous_completion_id` seems ignored | History pruned or edited, or prior call used `store=False` | It only extends unchanged stored history |
| Deleting one turn wiped the thread | Deletion acts on the whole chain | Completions joined by `previous_completion_id` delete together |
| `TypeError` on `function.arguments` | Treated as a dict | It is a JSON string — parse it |

## References

- [tool-contracts.md](references/tool-contracts.md) — read before writing any tool schema: primitives, description patterns, result envelope, stable handles, error envelope, terminal tools. Backend-agnostic.
- [mixedbread-tools.md](references/mixedbread-tools.md) — read when backing tools with Mixedbread Stores: the call behind each primitive, filters, chunk identity, gotchas.
