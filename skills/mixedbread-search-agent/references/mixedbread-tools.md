# Backing the tools with Mixedbread Stores

Stores are a natural backend for this model: the semantic endpoint is late-interaction retrieval with an optional reranker, and grep, listing, facets, and chunk retrieval cover the remaining primitives.

Read [tool-contracts.md](tool-contracts.md) for the schemas, envelopes, and descriptions; SKILL.md for the API. This is only the wiring. For building the Stores themselves, use the `mixedbread-search` skill.

## Which call backs which tool

| Tool you define | Backing call | Matches on |
| --- | --- | --- |
| `semantic_search` | `stores.search()` | Meaning and paraphrase |
| `grep_search` | `POST /v1/stores/grep` | RE2 regex, literal tokens |
| `list_chunks` | `POST /v1/stores/list-chunks` | Metadata filters, numeric order |
| `metadata_facets` | `stores.metadata_facets()` | Nothing — it describes the corpus |
| `expand_chunks` | `stores.files.retrieve()` | Known chunk identity |

Pin `store_identifiers` inside the implementation from application config. Leaving it out of the tool schema entirely removes hallucinated store names as a failure mode; expose a store argument only when the model genuinely must choose, and pair it with `stores.list()` so it can discover real names.

## Client setup

The `mixedbread` SDK is a second client alongside the OpenAI-compatible one; it runs inside your tool implementations, not in the loop.

```bash
pip install mixedbread          # Python
npm install @mixedbread/sdk     # TypeScript
```

```python
from mixedbread import Mixedbread

mxbai = Mixedbread()                       # reads MXBAI_API_KEY
STORE_IDENTIFIERS = ["contracts"]
```

```ts
import { Mixedbread } from '@mixedbread/sdk';

const mxbai = new Mixedbread();
const STORE_IDENTIFIERS = ['contracts'];
```

## Semantic search

```python
def semantic_search(query: str, top_k: int = 5) -> dict:
    response = mxbai.stores.search(
        query=query,
        store_identifiers=STORE_IDENTIFIERS,
        top_k=min(top_k, 20),
        search_options={"rerank": True},
    )
    return envelope(query, [chunk.model_dump() for chunk in response.data])
```

```ts
const response = await mxbai.stores.search({
  query,
  store_identifiers: STORE_IDENTIFIERS,
  top_k: Math.min(topK, 20),
  search_options: { rerank: true },
});
```

Keep `rerank` on for production retrieval; it materially improves what the model sees.

Do not combine it with `search_options={"agentic": True}`. Agentic search runs Mixedbread's own Toast-1 harness inside the Search API — it is an alternative to building this loop, not a component of it. Reach for it when you want the model's search behavior with no harness of your own, and for the completions loop when you need control over tools, rounds, or output shape.

## Grep

`POST /v1/stores/grep` has no dedicated SDK method yet. Call it through the SDK's generic `post`, which keeps auth, retries, and base URL handling:

```python
def grep_search(pattern: str, top_k: int = 10) -> dict:
    response = mxbai.post(
        "/v1/stores/grep",
        body={
            "pattern": pattern,
            "store_identifiers": STORE_IDENTIFIERS,  # exactly one store per call
            "targets": ["text", "generated"],
            "case_sensitive": False,
            "top_k": top_k,
        },
        cast_to=object,
    )
    return envelope(pattern, response.get("data", []))
```

```ts
const response = await mxbai.post<{ data: Chunk[] }>('/v1/stores/grep', {
  body: { pattern, store_identifiers: STORE_IDENTIFIERS, top_k: topK },
});
```

- `pattern` is RE2, up to 1024 characters. Say so in the tool description.
- `targets` defaults to both `text` and `generated`. Keep both unless deliberately excluding ingestion-derived OCR, transcription, and summary fields.
- One store per call, and no pagination — raise `top_k` for more matches.

## Chunk listing

`POST /v1/stores/list-chunks` selects by metadata instead of by query:

```python
body = {
    "store_identifiers": STORE_IDENTIFIERS,  # single store
    "filters": filters,
    "top_k": top_k,
}
if rank_by:
    body["sort_by"] = [rank_by, direction == "asc"]
response = mxbai.post("/v1/stores/list-chunks", body=body, cast_to=object)
```

`sort_by` takes a field name or `[field, ascending]`. Unprefixed paths target file metadata; `generated_metadata.*` targets chunk metadata. Only sort on numeric fields, and report back how many values were non-numeric or missing rather than failing the call.

## Metadata facets

```python
facets = mxbai.stores.metadata_facets(store_identifiers=STORE_IDENTIFIERS)
# {"year": {"2023": 1, "2024": 1}, "author": {"Dana Lee": 1, "Joe Smith": 1}}
```

Expose this before any filtering tool. Filter keys that do not exist return nothing silently, so facet discovery is what stops a plausible-looking guess from quietly returning zero results.

## Chunk expansion

```python
file = mxbai.stores.files.retrieve(
    file_identifier,                    # positional
    store_identifier=STORE_IDENTIFIERS[0],  # this endpoint accepts one store
    return_chunks=[3, 4, 5],            # or True for every chunk
)
```

Resolve the model's handles to `(file_id, chunk_index)` yourself and validate the range: an index past the end of the file fails with HTTP 422 (`Invalid chunk indices: [0, 1], but must be between 0 and 0`). Clamp and return a structured error instead of letting that reach the model as an exception.

Chunks from this endpoint carry `chunk_index`, `text`, `offset`, and `generated_metadata` but not `file_id` or `filename` — those live on the parent file object, so re-attach them from your registry.

## Filters

Stores filters are a tree with `all` / `any` / `none` combinators:

```python
filters = {
    "all": [
        {"key": "author", "operator": "eq", "value": "Joe Smith"},
        {"key": "year", "operator": "gte", "value": 2024},
    ]
}
```

Operators: `eq`, `not_eq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `like`, `not_like`, `contains`, `starts_with`, `regex`.

Give the model a flat condition list plus a `filter_mode: "all" | "any"` and build the tree yourself. Apply non-negotiable application scope as a filter the model cannot see or override, and merge it with whatever the model supplies.

## Chunk identity and available fields

`stores.search`, grep, and list-chunks all return the same chunk shape, so one envelope serves all three. Chunk identity is `(store_id, file_id, chunk_index)` on every retrieval endpoint — map it once to a short handle and keep the mapping on the application side.

Fields available for the envelope: `text`, `score`, `filename`, `file_id`, `store_id`, `chunk_index`, `offset`, `metadata`, `generated_metadata`, `summary`, `context`, `type`, and `mime_type`.

## A cited answer without a loop

`stores.question_answering()` returns generated text with `<cite i="n"/>` tags plus a `sources` list. Use it when a cited answer over one corpus is the whole requirement, and the completions loop when you need custom tools, round control, or a structured terminal.
