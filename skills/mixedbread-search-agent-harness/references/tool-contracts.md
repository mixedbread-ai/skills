# Tool contracts for the search model

The contracts the model was trained against, expressed against no particular retrieval engine. They apply to the `function` tools you declare and execute yourself. The API's hosted store tools (`search_corpus`, `grep`, `filter_chunks`, `inspect_metadata`, `get_chunks`) are these same contracts executed server-side and need none from you; they are covered by `hosted-tools.md` in the `mixedbread-search-agent` skill. Wiring these contracts to Mixedbread Stores is `mixedbread-tools.md` in the same skill; running them in a bounded loop is `python-loop.md` in the `mixedbread-search-agent-harness` skill.

Every tool name here is illustrative — name tools for your domain. A function tool may not share the name of a hosted tool declared in the same request (`duplicate_tool_name`). `submit_ranking` is the terminal the model was trained on, and `prune_context` its pruning tool.

The argument sets and envelopes below are illustrative, and the model adapts to yours. What it does depend on: JSON results rather than prose, stable handles it can re-reference, ID-taking tools that accept only handles you emitted, and errors returned as data.

## How the model reads a tool

| Write | Because |
|-------|---------|
| The matching mechanism, named explicitly | The model picks between primitives on stated contrast, not implied |
| The preferred input form | "Human-style question" and "keyword-heavy, not questions" produce different queries |
| One contrasting misuse + the tool to use instead | Redirects the failure rather than just forbidding it |
| Bounds, in the description | Without a published max the model guesses and the whole call is rejected |
| What comes back | Handles it can reference later |

Names must match `^[a-zA-Z0-9_-]{1,64}$`, and must not collide with a declared hosted tool. Arguments: flat, snake_case, JSON-native (`str`, `float`, `bool`, `list[str]`, at most one level of typed dict). `Literal`/enum for closed choices. Only essentials required, defaults for the rest.

The API always takes explicit JSON schema. In Python you can generate it from a function's docstring and `Annotated` hints instead of hand-writing it — `python-loop.md` in the `mixedbread-search-agent-harness` skill ships a `tool_schema` helper that does.

## Semantic search

```json
{
  "type": "function",
  "function": {
    "name": "semantic_search",
    "description": "Execute a meaning-based semantic search query over the corpus and return the most relevant chunks. Use natural language; phrase queries as human-style questions. Do not use for keyword, regex, or literal-string matching. Returns up to top_k chunks with stable chunk_id handles.",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {"type": "string", "description": "Natural-language query for a single search aspect; avoid Boolean syntax, regex, and keyword dumps."},
        "top_k": {"type": "integer", "description": "Number of chunks to return, max 20.", "default": 5}
      },
      "required": ["query"]
    }
  }
}
```

The description is the instruction: it names the mechanism, states the input form, forbids one misuse, and publishes the bound. The model writes human-style questions here, one aspect per query, and fans several out in parallel. Back it with the strongest retrieval available — late-interaction suits the model best, and a reranker materially improves what it sees.

## The other primitives

The pattern above is the whole of it; what changes is what must reach the description.

| Family | The description must say | Arguments that matter |
|--------|--------------------------|-----------------------|
| Lexical / BM25 | Keyword matching only, keyword-heavy input rather than questions, and which tool to use for meaning instead. Never label BM25 or any lexical retrieval as semantic | `query` ("space-separated keywords, no natural-language questions, no boolean operators"), bounded `top_k` |
| Regex | The dialect by name (RE2, PCRE, Python `re`) and that it matches literally: exact tokens, codes, identifiers, function names, SKUs, quoted phrases | `pattern`, `targets` over every stored text field when OCR or transcription is separate, `case_sensitive = False`, optional filters |
| Metadata facets | That sample values are representative, not exhaustive enums | none, or a field list |
| Metadata listing | Which fields are filterable, and which are confirmed numeric | flat `filter_by` conditions (`key`, enum `operator`, JSON-native `value`), `filter_mode`, `rank_by`, `direction`, bounded `top_k` |
| Expansion | The exact previously emitted handles it takes, and a published max list size | `chunk_ids: list[str]`, or one `chunk_id` with `before`/`after` for a neighbor window |

- Expose facets before any filtering tool. A filter on a key that does not exist returns nothing rather than erroring, and the model cannot tell the two apart.
- Apply non-negotiable scope — tenant, permissions, collection — as a filter the model never sees and cannot override.
- Return a short window around **every** regex match, not a head clip: the matched token is why the chunk came back.
- Expansion must return meaningfully more text than search (~4× the clip), or the model has no reason to call it.
- Report a requested numeric sort that could not be applied, and how many values were non-numeric; never let a bad sort field end the episode.
- ID-taking tools reject unknown handles as structured data and preserve the ones they were given.

## Prune tool

Do not build one. Declare `context_management={"edits": [{"type": "prune_context"}]}` on the request and the API gives the model its `prune_context` tool over every tool result, yours included. Prune-style removal also beats summarizing compaction, which invalidates the stable prefix and loses evidence detail.

Build your own only for a stateless loop (`store=False`) whose prunes must survive across turns. `prune_context` is a trained name with a trained shape: one `ids` argument addressing transcript results and spans, never retrieval handles — a same-named tool taking `chunk_ids` fights the policy. Pruning removes content, not identity: keep handles resolvable so the model can still rank or restore that evidence.

## Terminal tool

The model was trained on three terminal modes; the prompt and the declared tools decide which one a run uses:

| Mode | Declare | Ends with |
|------|---------|-----------|
| Ranking only | `submit_ranking` with `chunks` and `ranking_strategy` | The model calls `submit_ranking` itself once the evidence suffices |
| Ranking plus answer | The same, with a required `answer` | One call carrying evidence and answer |
| Plain-text answer | No reporting tool, `tool_choice="auto"`; instruct that every response must contain tool calls until it answers, and that a plain-text reply with no tool calls ends the run ("Do not report chunk lists or rankings; deliver the answer itself.") | `finish_reason="stop"` with content |

In every mode, tell the model to base the answer only on retrieved evidence and to say so when the evidence is insufficient. The trained shape:

```json
{
  "chunks": [
    {"chunk_id": "c12", "relevance_score": 0.97},
    {"chunk_id": "c4", "relevance_score": 0.82}
  ],
  "ranking_strategy": "How relevance and constraints determined the order",
  "answer": "Complete answer grounded in the retrieved evidence"
}
```

| Field | Trained shape |
|-------|---------------|
| `chunks[].chunk_id` | Enum of currently visible IDs; validate against the registry anyway |
| `chunks[].relevance_score` | `[0, 1]`, ranked most relevant first |
| `chunks` | May be empty when nothing is relevant; duplicate IDs are collapsed, not rejected |
| `ranking_strategy` | Optional: "Briefly state how you interpreted the query, which hard constraints you applied, and how you ordered the final chunks" |
| `answer` | Absent for ranking only. For ranking plus answer, required, with the trained description: "Your final answer to the original user query, based only on retrieved evidence. Required on every submit_ranking call: give your single best answer even when uncertain; if the evidence is insufficient to answer, say so." |
| Placement | The only call in its turn |

When the round budget runs out, force the terminal turn with a short user message ("You have reached the search limit. Do NOT search further. Call submit_ranking now.") and `tool_choice` by name, with only the terminal declared:

```python
tool_choice={"type": "function", "function": {"name": "submit_ranking"}}
```

## Result envelope and stable handles

Every retrieval tool returns a dict, never prose. The handles are the required part; the rest of the envelope is yours to change:

```json
{
  "query": "Which contract governed the 2019 distribution agreement?",
  "candidate_count": 5,
  "results": [
    {"chunk_id": "c12", "document_id": "d4", "score": 0.8123,
     "text": "clipped evidence", "metadata": {"year": 2019}}
  ]
}
```

Sort in presentation order and clip text as it enters the tool message (~2,000 tokens works well). Echoing the query and a candidate count costs little and helps the model judge coverage.

| Handle rule | Why |
|-------------|-----|
| Map real identity → short handle (`c12`) at first sight, never reassign | The model ranks and re-references short handles far more reliably than UUIDs |
| Any tool taking IDs accepts exactly the IDs you emitted | Otherwise it invents plausible ones |
| Deduplicate against what the agent has seen | Nothing does cross-call dedup for you |
| Keep full identity application-side, keyed by handle | That mapping is your provenance and your terminal validator |

## Error envelope

Return errors as data, never raise — validation, backend, timeout, permission, and unknown-ID failures alike:

```json
{"error": "date must be ISO format, got '3/5/24'", "code": "invalid_arguments", "retryable": true}
```

Return it as the tool message for the same `tool_call_id`. The model recovers on the next round when the error names the exact field that was wrong, and never recovers from an exception that escapes the executor.
