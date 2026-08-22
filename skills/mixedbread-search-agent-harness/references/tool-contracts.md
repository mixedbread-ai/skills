# Tool contracts for the search model

The contracts the model was trained against, expressed against no particular retrieval engine — wire them to whatever backend the harness sits in front of. For the loop that calls these tools, see [python-loop.md](python-loop.md); for the API surface underneath, use the `mixedbread-search-agent` skill.

Every tool name here is illustrative — the harness owns its tool namespace and should name tools for its domain. The one exception is `submit_answer`, which Mixedbread reserves: declaring it fails with HTTP 422.

## How the model reads a tool

| Write | Because |
|-------|---------|
| The matching mechanism, named explicitly | The model picks between primitives on stated contrast, not implied |
| The preferred input form | "Human-style question" and "keyword-heavy, not questions" produce different queries |
| One contrasting misuse + the tool to use instead | Redirects the failure rather than just forbidding it |
| Bounds, in the description | Without a published max the model guesses and the whole call is rejected |
| What comes back | Handles it can reference later |

Arguments: flat, snake_case, JSON-native (`str`, `float`, `bool`, `list[str]`, at most one level of typed dict). `Literal`/enum for closed choices. Only essentials required, defaults for the rest.

In Python the docstring becomes the tool description and `Annotated` strings become parameter descriptions. The raw API always takes explicit JSON schema.

## Semantic search

```python
from typing import Annotated


def semantic_search(
    query: Annotated[str, "Natural-language query for a single search aspect; "
                          "avoid Boolean syntax, regex, and keyword dumps."],
    top_k: Annotated[int, "Number of chunks to return, max 20."] = 5,
) -> dict:
    """Execute a meaning-based semantic search query over the corpus and return the
    most relevant chunks. Use natural language; phrase queries as human-style
    questions. Do not use for keyword, regex, or literal-string matching.
    Returns up to top_k chunks with stable chunk_id handles."""
    hits = my_search_backend(query, top_k=top_k)  # your implementation
    return {
        "query": query,
        "candidate_count": len(hits),
        "results": [
            {"chunk_id": h.id,               # short stable handle, e.g. "c12"
             "score": round(h.score, 4),
             "text": h.text,                 # clipped, not the whole document
             "metadata": h.metadata}
            for h in hits
        ],
    }
```

As explicit schema for the raw API:

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
      "required": ["query"],
      "additionalProperties": false
    }
  }
}
```

The model writes human-style questions here, one aspect per query, and fans several out in parallel. Back it with the strongest retrieval available — late-interaction suits the model best, and a reranker materially improves what it sees.

## BM25 keyword search

```python
def bm25_search(
    query: Annotated[str, "Space-separated keywords, no natural-language questions, "
                          "no boolean operators. Example: 'jordan international goals caps'"],
    top_k: Annotated[int, "Number of chunks to return, max 20."] = 10,
    mode: Literal["chunks", "documents"] = "chunks",
) -> dict:
    """Keyword-based BM25 search over the corpus. This tool matches keywords only —
    send keyword-heavy queries, not questions. Use for rare terms, names, codes,
    and exact vocabulary; use the semantic search tool for meaning-based queries.
    Returns up to top_k chunks with stable chunk_id handles."""
```

Never label BM25 or any lexical retrieval as semantic.

## Regex grep

| Argument | Type | Notes |
|----------|------|-------|
| `pattern` | `str` | Name the actual dialect (RE2, PCRE) in the description |
| `targets` | `list[Literal["text", "generated"]]` | Default both when OCR/transcription is stored separately |
| `case_sensitive` | `bool = False` | |
| Filters | optional | Verified fields only |

Description: "Literal regular-expression matching; no embeddings, semantic match, or reranker. Use for exact tokens, codes, identifiers, function names, SKUs, and quoted phrases."

Return a short window around **every** match, not a head clip — the matched token is why the chunk came back.

## Metadata facets and listing

Facets return real field paths, representative values, value types, and counts. State in the description that samples are representative, not exhaustive enums. Expose facets before any filtering tool: filters on non-existent keys return nothing rather than erroring.

Listing arguments:

| Argument | Type | Notes |
|----------|------|-------|
| `filter_by` | flat conditions: `key`, enum `operator`, JSON-native `value` | Build any nested tree yourself |
| `filter_mode` | `Literal["all", "any"] = "all"` | |
| `rank_by` | `str \| None` | Confirmed numeric fields only |
| `direction` | `Literal["asc", "desc"] = "desc"` | |
| `top_k` | bounded int | |

Apply non-negotiable scope — tenant, permissions, collection — as a filter the model cannot see or override. Report whether numeric ranking was applied and how many values were non-numeric; never let a bad sort field crash the episode.

## Expansion tools

| Tool | Arguments | Contract |
|------|-----------|----------|
| Chunk expansion | `chunk_ids: list[str]` | Exact previously emitted handles; publish a max list size |
| Neighbor window | `chunk_id: str, before: int, after: int` | Bounded window around one result |

Both reject unknown IDs as structured data and preserve the original handles. Return meaningfully more text than search (~4× the clip) or the model has no reason to call them.

## Prune tool

Nothing prunes for you. Prune-style removal beats summarizing compaction, which invalidates the stable prefix and loses evidence detail. Exposing pruning as a tool lets the model shed evidence it has judged irrelevant; instruct it to call the tool as it approaches the limit.

```json
{"name": "prune_context", "arguments": {"chunk_ids": ["c2", "c9"], "document_ids": ["d7"]}}
```

Require at least one emitted ID. Return what was pruned and which IDs were invalid. Pruning removes content, not identity — keep handles resolvable so the model can still rank or restore that evidence.

## Terminal tool

By default the model ends by answering: `finish_reason="stop"` with assistant content and no tool call. When prose is the deliverable, that is the whole terminal contract.

For structured output, define your own terminal under any name except `submit_answer`. Offer it alongside retrieval tools on non-final rounds and accept it early when it is the only call; on the final fallback, offer only the terminal and force it by name. The trained shape is chunk IDs your tools emitted, a relevance score each, and short reasoning:

```json
{
  "answer": "Complete answer grounded in the retrieved evidence",
  "ranking_strategy": "How relevance and constraints determined the order",
  "chunks": [
    {"chunk_id": "c12", "relevance_score": 0.97},
    {"chunk_id": "c4", "relevance_score": 0.82}
  ]
}
```

| Requirement | Detail |
|-------------|--------|
| `answer` | Complete user-ready text, grounded in retrieved evidence only |
| `relevance_score` | `[0, 1]` when ranked chunks are part of the task |
| `chunk_id` | Enum of currently visible IDs; validate against the registry anyway |
| Count | `minItems`/`maxItems` for strict top-k, plus how to fill a weak tail; otherwise let the model choose and avoid padding |
| Placement | The only call in its turn; deduplicate IDs |

```python
tool_choice={"type": "function", "function": {"name": "report_evidence"}}
```

Without named forcing the model usually just answers in prose. `tool_choice="required"` does not fix it.

For a lookup subagent, the same tool carries a short rationale plus ranked chunks — the parent already has the evidence, so the rationale explains why those chunks answer the assigned aspect.

## Result envelope and stable handles

Every retrieval tool returns a dict, never prose:

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

Echo the query or pattern, report candidates remaining after deduplication, sort in presentation order, clip text to ~2,000 tokens.

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
