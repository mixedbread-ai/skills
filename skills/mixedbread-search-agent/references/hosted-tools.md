# Hosted store tools

The Chat Completions and Responses APIs can execute these tools over Mixedbread Stores.
Their configuration and returned fields follow the [API reference](https://www.mixedbread.com/api-reference/endpoints/chat/create-chat-completion).
The public [toast-harness](https://github.com/mixedbread-ai/toast-harness) provides implementation
examples; its internal schemas are not the hosted API contract.

## Tool entries

| `type` | Fields | Defaults and bounds | Runs |
|--------|--------|---------------------|------|
| `search_corpus` | `store_identifiers`, `max_num_results`, `filters`, `score_threshold`, `citations` | 5 chunks (1–30), threshold 0.0 | Semantic search; the primary tool. Results deduplicated across the run, text clipped to ~2,000 tokens |
| `grep` | `store_identifiers`, `max_num_results`, `filters`, `citations` | 10 chunks (1–30) | Regex over the literal chunk text, no embeddings; ~100-token windows around each match, overlapping windows merged |
| `filter_chunks` | `store_identifiers`, `max_num_results`, `filters`, `citations` | 30 chunks (1–30); the model asks for 10 by default | Metadata-filtered listing, optional numeric `rank_by`; a non-numeric field degrades to `rank_by_applied: false` with a count |
| `inspect_metadata` | `store_identifiers`, `filters`, `max_values_per_field` | 8 values per field (1–20) | Field and value overview from 100 sampled chunks, plus `rankable_fields` for `filter_chunks` |
| `get_chunks` | `store_identifiers` | up to 20 IDs per call | Re-fetches known chunks with more context; unavailable IDs return per-ID errors |
| `list_stores` | `limit` | 20 (1–100) | Paginated listing of the stores the key can see |

- `filters` (the Stores filter tree) and `score_threshold` apply to every call of that tool, invisibly to the model; use them for non-negotiable scope such as a tenant.
- `store_identifiers` takes IDs or names. All declared store tools must share one scope; mixed scopes are rejected. Omit it to open the scope: `list_stores` is then required and each store tool gains a required `store` argument the model fills with exactly one store per call — except `get_chunks`, whose known chunk IDs resolve to the store.
- Unknown fields on an entry are ignored; a wrong `type` fails validation with a 422 listing the valid tags. A function tool that duplicates a declared hosted tool's name fails with `duplicate_tool_name`.
- `tool_choice={"type": "search_corpus"}` forces that tool on the first model turn; later turns of the server loop use `auto`. `grep`, `filter_chunks`, `inspect_metadata` and `list_stores` are forceable the same way; `get_chunks` is not.

## Budget, ending, cost

| Knob | Effect |
|------|--------|
| `max_tool_calls` (extension, default 16) | Bounds hosted calls and `prune_context` together; at most 8 server calls run per model turn, extra calls receive a structured error instead of running |
| How a run ends | A plain-text reply or a custom function call returns control to you. At its tool/context limit, the server asks the model to answer from available evidence. Failure to finish produces `finish_reason="length"`; Responses uses `status="incomplete"` with the limiting reason |
| Default instructions | Hosted tools supply default search instructions when no system/developer text is provided. Your instructions replace that default; declared context management and citations can add their own instructions |
| `usage.prompt_tokens` | Sums every hidden round — tens of thousands of tokens for a few searches; `prompt_tokens_details.cached_tokens` is the prefix-cached part |
| `store` | Defaults to `true`; use it for stored continuation, or `False` for an independent request whose conversation content should not be retained |

## What comes back

`hosted_tool_calls` is a response extension (`completion.model_extra["hosted_tool_calls"]` in Python): one item per server-executed call, in execution order. Every item carries `type`, `id`, `status` (`in_progress`, `completed`, `failed`), and on a failure `error` — `{code, message}` with `code` one of `invalid_arguments` (the model's own mistake), `permission_denied`, `server_error`. There is **no `arguments` field**: each item echoes the arguments the model chose under their own names, alongside its payload.

| Item `type` | Echoed arguments | Payload | Returned only with `include` |
|-------------|------------------|---------|------------------------------|
| `search_corpus_call` | `queries[]`, `metadata_filters`, `filter_mode`, `store` | `results` | `search_corpus_call.results` |
| `grep_call` | `pattern`, `targets[]`, `case_sensitive`, `metadata_filters`, `filter_mode`, `store` | `results` | `grep_call.results` |
| `filter_chunks_call` | `metadata_filters`, `filter_mode`, `rank_by`, `direction`, `store` | `results` | `filter_chunks_call.results` |
| `get_chunks_call` | `chunk_ids[]` | `results` | `get_chunks_call.results` |
| `inspect_metadata_call` | `store` | `facets` | always returned |
| `list_stores_call` | `cursor` | `stores[]` (`name`, `description`, `connectors`), `has_more`, `next_cursor` | always returned |

`store` is filled in only when the request left the scope open. When storing, chunk payloads remain available for continuation; `include` controls whether they also come back on the wire. `include: ["transcript"]` returns the full stored conversation.

| In a `results` entry | Meaning |
|----------------------|---------|
| `chunk_id` | `"<file_id>:<chunk_index>"`, stable across requests; the `file_id` resolves against the store files API |
| `document_id` | Shared by all chunks of one document, for grouping |
| `chunk_index`, `filename`, `file_title`, `mime_type`, `external_id` | Locators; each omitted when the store has no value |
| `search_score` | Relevance, rounded to 4 decimals — not `score`; omitted for unscored listings |
| `text` | The chunk itself, clipped to ~2,000 tokens (~100-token windows per match for grep); `context`, `ocr_text`, `transcription`, `summary`, `metadata` ride along when the chunk has them |
| `seen: true` | A compact reference — `chunk_id`, `document_id`, `chunk_index`, sometimes `filename`, no body. `grep` and `filter_chunks` return it in place of a chunk the run already retrieved; `get_chunks` re-fetches the body |

`deduped_existing_or_deleted` (a **count** of chunks skipped as already-seen or deleted), `targets_note`, `rank_by_applied` and `rankable_fields` belong to the payload the *model* reads, not to the wire item — only the result list reaches `hosted_tool_calls[].results`.

The answer itself is the ordinary `content` of the message; `context_management.applied_edits` reports prunes when `context_management` was declared.

## Request examples

With the clients configured as in SKILL.md, Python sends Mixedbread extension fields in `extra_body`:

```python
completion = client.chat.completions.create(
    model="toast-1",
    messages=[{"role": "user", "content": "Which products cost less than 100?"}],
    tools=[{"type": "search_corpus", "store_identifiers": ["product-catalog"]}],
    temperature=0.7, top_p=0.95, store=False,
    extra_body={"max_tool_calls": 8, "include": ["search_corpus_call.results"],
                "context_management": {"edits": [{"type": "prune_context"}]}},
)
if completion.choices[0].finish_reason == "length":
    raise RuntimeError("Search was incomplete; adjust the budget or report the partial result explicitly")
print(completion.choices[0].message.content)
for call in (completion.model_extra or {}).get("hosted_tool_calls") or []:
    print(call["type"], call["status"], call.get("error"), call.get("results"))
```

TypeScript sends extensions inline; the cast allows tool types outside the OpenAI SDK's types:

```typescript
const completion = await client.chat.completions.create({
  model: 'toast-1',
  messages: [{ role: 'user', content: 'Which products cost less than 100?' }],
  tools: [{ type: 'search_corpus', store_identifiers: ['product-catalog'] }],
  include: ['search_corpus_call.results'], max_tool_calls: 8,
  context_management: { edits: [{ type: 'prune_context' }] },
  temperature: 0.7, top_p: 0.95, store: false,
} as never);
if (completion.choices[0].finish_reason === 'length') throw new Error('Search incomplete');
console.log(completion.choices[0].message.content);
const extra = completion as unknown as { hosted_tool_calls?: unknown[] };
console.log(extra.hosted_tool_calls);
```

## Hybrid: hosted retrieval, your terminal

You can declare hosted tools and a custom terminal such as `submit_ranking` together. The model
may call your terminal during exploration; validate that call against your chosen schema and the
retrieved evidence. Other custom calls need matching tool results before continuation.

If hosted search ends in prose and you need a structured payload, a forced follow-up is useful.
Store the search request and include its retrieved results. Assuming `search` has no pending
function calls, and your application defines `SUBMIT_RANKING` and `validate_submission`:

```python
final = client.chat.completions.create(
    model="toast-1",
    messages=[{"role": "user", "content": "Finish by calling submit_ranking with the retrieved evidence."}],
    tools=[SUBMIT_RANKING],
    tool_choice={"type": "function", "function": {"name": "submit_ranking"}},
    parallel_tool_calls=False, store=True,
    extra_body={"previous_completion_id": search.id,
                "context_management": {"edits": [{"type": "prune_context"}]}},
)
choice = final.choices[0]
calls = choice.message.tool_calls or []
if choice.finish_reason != "tool_calls" or len(calls) != 1 or calls[0].function.name != "submit_ranking":
    raise RuntimeError("No complete terminal call; recover with a bounded correction")
submission = validate_submission(calls[0].function.arguments, retrieved_ids)
```

`retrieved_ids` comes from the search's included result payloads. Parse the JSON arguments and
validate the agreed fields, evidence IDs, and score ranges before accepting the submission.
The example terminal shapes are in [tool-contracts.md](tool-contracts.md#terminal-tools).
Stored continuation restores the hosted evidence automatically; a stateless follow-up needs you
to supply the relevant evidence yourself. If desired, deletion is chain-wide:
`client.delete(f"/chat/completions/{search.id}", cast_to=object)`.

## Context management

We recommend enabling server-side pruning for hosted and custom tools alike. See
[SKILL.md § Context management](../SKILL.md#context-management) for configuration, continuation,
and stateless behavior. Read `context_management.applied_edits` for pruning and overflow truncation.

## Streaming

With `stream=True`, each hosted call item arrives on a chunk twice: once with `status: "in_progress"` when dispatched and once finished — on chunks whose `choices` is empty, so never index `choices[0]` unguarded. The answer streams as `delta.content`, and `context_management` rides on the final usage chunk. The consumer loop is in SKILL.md § Streaming.

## Citations

| Mechanism | Behavior |
|-----------|----------|
| `citations: true` on `search_corpus`, `grep`, or `filter_chunks` | Appends a citation instruction to the system prompt, so the answer cites as `<cite i="..."/>`. The `i` refers to a result `index` field that hosted chunk payloads do not carry — to resolve a citation back to a chunk, prompt for the `chunk_id` format below instead |
| Prompted inline format | A system-prompt instruction such as "cite as [chunk_id]" works over hosted results, in prose endings and in a forced terminal alike |
| `stores.question_answering()` | Returns `<cite i="n"/>` tags plus a `sources` list without a completions call; see the `mixedbread-search` skill |

## Gotchas

| Symptom | Cause | Fix |
|---------|-------|-----|
| Hosted search ran although you meant to bring your own backend | A hosted entry was in `tools` | Declare only `function` tools |
| `results` is `null` on every hosted call | No `include` | `extra_body={"include": ["search_corpus_call.results"]}` (inline in Node) |
| Answer says the search limit was reached, or `finish_reason="length"` | `max_tool_calls` or the context window hit | Adjust `max_tool_calls` or `context_management`; report any partial answer as incomplete |
| 422 on `store_identifiers` | Mixed scopes, or an open scope without `list_stores` | One scope for all store tools; add `{"type": "list_stores"}` when omitting `store_identifiers` |
| 422 `duplicate_tool_name` | A function named like a declared hosted tool | Rename it |
| Forced `submit_ranking` cites handles that are not in `results` | The forced turn was stateless | Continue the stored search, or explicitly supply its evidence to a stateless turn |
| Chunk with `choices == []` in a stream | Hosted progress chunk | Read `hosted_tool_calls` from it; do not index `choices[0]` |
