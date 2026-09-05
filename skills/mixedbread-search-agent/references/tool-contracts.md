# Designing function tools

These are design preferences for custom tools, independent of the retrieval backend.
Names, schemas, result envelopes, and output formats can differ from the public
[training harness](https://github.com/mixedbread-ai/toast-harness).
For API field constraints, use the [Chat Completions reference](https://www.mixedbread.com/api-reference/endpoints/chat/create-chat-completion)
or [Responses reference](https://www.mixedbread.com/api-reference/endpoints/responses/create-response).

## Describe the actual backend

Explain what a tool matches, when it is useful, how to formulate input, and any limits.
Prefer simple JSON-native arguments and enums for closed choices. Handwritten JSON Schema,
docstring helpers, and your framework's schema generation are all suitable.

A custom semantic search function might be declared as follows in Chat Completions:

```json
{
  "type": "function",
  "function": {
    "name": "search_corpus",
    "description": "Search the corpus by meaning. Use a focused natural-language question for each aspect. Returns evidence with stable IDs; if a literal lookup tool is available, prefer it for exact patterns.",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {"type": "string"},
        "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5}
      },
      "required": ["query"]
    }
  }
}
```

This is your function, not the hosted `{"type": "search_corpus"}` tool. A function name
cannot collide with a hosted tool declared in the same request. Adapt the name and description
to your implementation; changing only the backend can leave misleading query instructions.

For additional capabilities, describe the regex dialect of a pattern tool, the available
fields of a metadata tool, or the references accepted by an expansion tool. Discover metadata
before using unfamiliar filters, and preserve access restrictions in the backend. When clipping,
retain relevant match windows; expansion should provide useful additional context.

## Evidence and errors

JSON envelopes are convenient for consistent parsing, but their shape is your choice:

```json
{"query": "When does the agreement expire?", "results": [
  {"chunk_id": "c12", "text": "The agreement expires in 2027.", "source": "agreement.pdf"}
]}
```

Keep identities stable across tools and retain provenance. Deduplicating previously shown
results can improve coverage; coordinate it across concurrent retrieval. Register only evidence
kept after payload trimming. Previously seen evidence can remain resolvable after its text is
pruned; evidence discarded before presentation should remain eligible for later retrieval.
Scores from different tools need not be comparable: rank for intent and evidence.

Catch tool failures at the executor boundary and return an informative result, for example
`{"error": "Unknown metadata field: publication_date", "retryable": true}`. When continuing,
the protocol requires one tool result per call ID, including failed or rejected calls.

For context pressure, we recommend the API's server-side `context_management`, including for
custom tools. See the API skill's Context management section or the
[API reference](https://www.mixedbread.com/api-reference/endpoints/chat/create-chat-completion).

## Terminal tools

The public harness illustrates three endings. Choose one or adapt it to your application's output:

| Deliverable | Example ending |
|-------------|----------------|
| Ranked evidence | `submit_ranking` with `chunks[{chunk_id, relevance_score}]`; optionally `ranking_strategy` |
| Evidence and answer | The same payload with a required `answer` string |
| Prose | No terminal function; accept non-empty content with `finish_reason="stop"` and no calls |

`submit_ranking` is a familiar starting name, not a required name. If using this ranking shape,
validate known IDs and finite scores in `[0, 1]`; allow an empty list when nothing is relevant.
Choose whether duplicates are rejected or collapsed, and make the schema, validator, and prompt
agree. Require a fixed item count only when the task needs one. A handle enum can help small
registries; runtime validation works without enumerating all evidence in the tool schema.

Offer the terminal during exploration and explain when to use it. Asking for it as the sole call
in a turn simplifies orchestration. At the cap, forcing the chosen function by name is a useful
fallback. Check completion status before accepting content or arguments: `length` is incomplete.
Return validation errors for a bounded correction attempt and report exhausted recovery explicitly.
Ground answers in retrieved evidence and acknowledge insufficient evidence.
