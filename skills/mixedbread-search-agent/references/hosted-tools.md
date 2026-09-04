# Hosted store tools

The six tools the Chat Completions and Responses APIs can run server-side over your Mixedbread Stores. Declare them in `tools` and the model searches for as many rounds as it needs inside one request; only your own `function` tools ever come back as `tool_calls`. They share names, schemas, defaults, and truncation behavior with the open-source [toast-harness](https://github.com/mixedbread-ai/toast-harness), the reference for exact schemas; its `completions/hosted_tools.py` is the runnable version of the example below. Contract: https://www.mixedbread.com/docs/agent/responses#search-your-stores-with-hosted-tools and the API reference.

## Tool entries

| `type` | Fields | Defaults and bounds | Runs |
|--------|--------|---------------------|------|
| `search_corpus` | `store_identifiers`, `max_num_results`, `filters`, `score_threshold`, `citations` | 5 chunks (1–30), threshold 0.0 | Semantic search; the primary tool. Results deduplicated across the run, text clipped to ~2,000 tokens |
| `grep` | `store_identifiers`, `max_num_results`, `filters`, `citations` | 10 chunks (1–30) | Regex over the literal chunk text, no embeddings; ~100-token windows around each match, overlapping windows merged |
| `filter_chunks` | `store_identifiers`, `max_num_results`, `filters`, `citations` | 30 chunks (1–30); the model asks for 10 by default | Metadata-filtered listing, optional numeric `rank_by`; a non-numeric field degrades to `rank_by_applied: false` with a count |
| `inspect_metadata` | `store_identifiers`, `filters`, `max_values_per_field` | 8 values per field (1–20) | Field and value overview from 100 sampled chunks, plus `rankable_fields` for `filter_chunks` |
| `get_chunks` | `store_identifiers` | up to 20 IDs per call | Re-fetches chunks the run has seen, ~8,000 tokens each (4× the search clip); unknown or pruned IDs come back as per-ID errors |
| `list_stores` | `limit` | 20 (1–100) | Paginated listing of the stores the key can see |

- `filters` (the Stores filter tree) and `score_threshold` apply to every call of that tool, invisibly to the model; use them for non-negotiable scope such as a tenant.
- `store_identifiers` takes IDs or names. All declared store tools must share one scope; mixed scopes are rejected. Omit it to open the scope: `list_stores` is then required and each store tool gains a required `store` argument the model fills with exactly one store per call — except `get_chunks`, whose chunk IDs already carry the store.
- Unknown fields on an entry are ignored; a wrong `type` fails validation with a 422 listing the valid tags. A function tool that duplicates a declared hosted tool's name fails with `duplicate_tool_name`.
- `tool_choice={"type": "search_corpus"}` forces that tool on the first model turn; later turns of the server loop use `auto`. `grep`, `filter_chunks`, `inspect_metadata` and `list_stores` are forceable the same way; `get_chunks` is not.

## Budget, ending, cost

| Knob | Effect |
|------|--------|
| `max_tool_calls` (extension, default 16) | Bounds hosted calls and `prune_context` together; at most 8 server calls run per model turn, extra calls receive a structured error instead of running |
| How a run ends | On a plain-text reply, or a call to one of your function tools. When `max_tool_calls` or the context window is reached, the model receives once: "You have reached the search limit. Do NOT search further. You must now reply with your final answer to the user query as plain text, with NO tool calls. Base it only on retrieved evidence; if the evidence is insufficient to answer, say so." If it does neither, the completion ends with `finish_reason="length"` (Responses: `status: "incomplete"`, `incomplete_details.reason` = `max_tool_calls` or `context_window`) carrying the text produced so far |
| Default instructions | With a hosted tool declared and no system or developer text: "You are a search agent over the user's connected stores. Use the search tools you were given to explore the corpus regarding the user's query." Any instruction text you send replaces it entirely. The harness still appends its own sections to the system prompt: the context-management contract when `context_management` is declared, and the citation instruction when a declared tool sets `citations` |
| `usage.prompt_tokens` | Sums every hidden round — tens of thousands of tokens for a few searches; `prompt_tokens_details.cached_tokens` is the prefix-cached part |
| `store` | Defaults to `true`; send `False` unless a later turn continues this one. `false` retains no conversation content — operational model and token metadata is still recorded |

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

`store` is filled in only when the request left the scope open. Chunk payloads are kept in the stored completion either way; the `include` key decides only whether they come back on the wire. `include: ["transcript"]` returns the full stored conversation.

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

## Complete example

Python (`pip install openai`):

```python
import os
from openai import OpenAI

client = OpenAI(base_url="https://api.mixedbread.com/v1", api_key=os.environ["MXBAI_API_KEY"])


def ask(query: str, *, store: str) -> dict:
    """One request: the answer, every hosted call the API ran, the chunks it retrieved, what it pruned."""
    completion = client.chat.completions.create(
        model="toast-1",
        messages=[{"role": "user", "content": query}],
        tools=[
            {"type": "search_corpus", "store_identifiers": [store]},
            {"type": "grep", "store_identifiers": [store]},
        ],
        temperature=0.7,
        top_p=0.95,
        store=False,                                   # nothing continues this completion
        extra_body={                                   # extension fields ride in extra_body
            "max_tool_calls": 8,
            "include": ["search_corpus_call.results", "grep_call.results"],
            "context_management": {"edits": [{"type": "prune_context"}]},
        },
    )
    extra = completion.model_extra or {}
    return {
        "answer": completion.choices[0].message.content or "",
        "finish_reason": completion.choices[0].finish_reason,      # "length": budget spent, no answer
        "evidence": [
            {"call": call["type"], "status": call["status"], "error": call.get("error"),
             "chunks": [c["chunk_id"] for c in call.get("results") or []]}
            for call in extra.get("hosted_tool_calls") or []
        ],
        "context_edits": (extra.get("context_management") or {}).get("applied_edits") or [],
        "prompt_tokens": completion.usage.prompt_tokens,
    }
```

TypeScript (`npm install openai`):

```typescript
import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: 'https://api.mixedbread.com/v1',
  apiKey: process.env.MXBAI_API_KEY!,
});

// Hosted tool types, include, max_tool_calls, and context_management are not in
// the OpenAI types, so the request is cast; the SDK sends the fields unchanged.
const completion = await client.chat.completions.create({
  model: 'toast-1',
  messages: [{ role: 'user', content: 'Which products cost less than 100, and what are their prices?' }],
  tools: [{ type: 'search_corpus', store_identifiers: ['product-catalog'] }],
  include: ['search_corpus_call.results'],
  max_tool_calls: 8,
  context_management: { edits: [{ type: 'prune_context' }] },
  store: false,
} as never);

type HostedCall = {
  type: string;
  status: string;
  error?: { code: string; message: string } | null;
  // Each item also echoes its own arguments, e.g. `queries` on search_corpus_call.
  results?: { chunk_id: string; document_id: string; search_score?: number; text?: string }[] | null;
};
type AppliedEdit = { type: string; calls?: number; cleared_input_tokens?: number };
const extra = completion as unknown as {
  hosted_tool_calls?: HostedCall[];
  context_management?: { applied_edits?: AppliedEdit[] };
};

console.log(completion.choices[0].message.content);
for (const call of extra.hosted_tool_calls ?? []) {
  console.log(call.type, call.status, call.error, (call.results ?? []).map((c) => c.chunk_id));
}
for (const edit of extra.context_management?.applied_edits ?? []) {
  console.log(edit.type, edit.calls, 'calls cleared', edit.cleared_input_tokens, 'input tokens');
}
```

## Hybrid: hosted retrieval, your terminal

Declare hosted tools and your own `submit_ranking` function together. The model may call `submit_ranking` before its budget runs out — that call comes back to you like any function call. At the search limit, though, the server asks for a plain-text answer, so a hosted run that spends its budget ends in prose. The structured payload then takes one forced turn, and that turn can only cite hosted evidence if it continues the stored completion:

```python
SUBMIT_RANKING = {"type": "function", "function": {
    "name": "submit_ranking",
    "description": "Submit the ranked chunks that answer the question and end the search. Call it alone.",
    "parameters": {"type": "object", "properties": {
        "chunks": {"type": "array", "items": {"type": "object", "properties": {
            "chunk_id": {"type": "string", "description": "chunk_id of a retrieved chunk"},
            "relevance_score": {"type": "number", "minimum": 0, "maximum": 1}},
            "required": ["chunk_id", "relevance_score"]}},
        "ranking_strategy": {"type": "string"},
        "answer": {"type": "string"}},
        "required": ["chunks", "ranking_strategy", "answer"]}}}

search = client.chat.completions.create(
    model="toast-1",
    messages=[
        {"role": "system", "content": "Search the store, then end by calling submit_ranking with the "
                                      "chunks that answer the question and your answer."},
        {"role": "user", "content": query},
    ],
    tools=[{"type": "search_corpus", "store_identifiers": [store]}, SUBMIT_RANKING],
    store=True,                                     # the forced turn continues this completion
    extra_body={"max_tool_calls": 8, "include": ["search_corpus_call.results"]},
)
message = search.choices[0].message
if message.tool_calls and message.tool_calls[0].function.name == "submit_ranking":
    submission = json.loads(message.tool_calls[0].function.arguments)
else:                                               # prose at the search limit
    final = client.chat.completions.create(
        model="toast-1",
        messages=[{"role": "user", "content": "You have reached the search limit. Do NOT search further. Call submit_ranking now."}],
        tools=[SUBMIT_RANKING],
        tool_choice={"type": "function", "function": {"name": "submit_ranking"}},
        parallel_tool_calls=False,
        store=True,
        extra_body={"previous_completion_id": search.id},
    )
    submission = json.loads(final.choices[0].message.tool_calls[0].function.arguments)
```

Validate `submission["chunks"][*]["chunk_id"]` against the `chunk_id`s in the `include`d results. The forced turn sees the hosted results only through `previous_completion_id`; sent stateless it has nothing to cite. For a ranking-only terminal drop `answer` from `properties` and `required`; for a prose answer over hosted retrieval no terminal is needed. Delete the chain afterwards when retention is not wanted: `client.delete(f"/chat/completions/{search.id}", cast_to=object)`.

## Context management

```python
extra_body={"context_management": {"edits": [{"type": "prune_context"}]}}
```

The model gets a `prune_context` tool over hosted results and your function results alike and clears what it considers stale as the run approaches the window; prune calls count against `max_tool_calls`. `context_management.applied_edits` reports one `prune_context` entry per response (`{"type": "prune_context", "calls": 2, "cleared_input_tokens": 5400}`) plus a `truncate_tool_result` entry (with `tool_call_id`) per client tool result shortened in overflow recovery. A hosted run that ends with `finish_reason="length"` for the context window is the signal to declare it. Semantics shared with function-tool loops are in SKILL.md § Context management.

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
| Answer says the search limit was reached, or `finish_reason="length"` | `max_tool_calls` or the context window hit | Raise `max_tool_calls`, declare `context_management`, or accept the answer built so far |
| 422 on `store_identifiers` | Mixed scopes, or an open scope without `list_stores` | One scope for all store tools; add `{"type": "list_stores"}` when omitting `store_identifiers` |
| 422 `duplicate_tool_name` | A function named like a declared hosted tool | Rename it |
| Forced `submit_ranking` cites handles that are not in `results` | The forced turn was stateless | `store=True` on the search request, `previous_completion_id` on the forced turn |
| Chunk with `choices == []` in a stream | Hosted progress chunk | Read `hosted_tool_calls` from it; do not index `choices[0]` |
