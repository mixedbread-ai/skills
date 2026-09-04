# Backing function tools with Mixedbread Stores

For a loop you run yourself with Stores as the backend. If you only need Stores retrieval and no custom tools, declare the hosted tools instead and skip this file — see [hosted-tools.md](hosted-tools.md): `search_corpus`, `grep`, `filter_chunks`, `inspect_metadata`, and `get_chunks` are exactly the wirings below, executed server-side. Stores are a natural backend for this model: the semantic endpoint is late-interaction retrieval with an optional reranker, and grep, listing, facets, and chunk retrieval cover the remaining primitives.

Read [tool-contracts.md](tool-contracts.md) for the schemas, envelopes, and descriptions; SKILL.md for the API. This is only the wiring. For building the Stores themselves, use the `mixedbread-search` skill.

## Which call backs which tool

| Tool you define | Backing call | Matches on | Hosted equivalent |
| --- | --- | --- | --- |
| `semantic_search` | `stores.search()` | Meaning and paraphrase | `search_corpus` |
| `grep_search` | `POST /v1/stores/grep` | RE2 regex, literal tokens | `grep` |
| `list_chunks` | `stores.list_chunks()` | Metadata filters, numeric order | `filter_chunks` |
| `metadata_facets` | `stores.metadata_facets()` | Nothing — it describes the corpus | `inspect_metadata` |
| `expand_chunks` | `stores.files.retrieve()` | Known chunk identity | `get_chunks` |

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

Keep `rerank` on for production retrieval; it materially improves what the model sees. Do not combine it with `search_options={"agentic": True}`: agentic search runs Mixedbread's own harness inside the Search API and is an alternative to this loop, not a component of it.

## Grep

`POST /v1/stores/grep` has no dedicated SDK method yet. Call it through the SDK's generic `post`, which keeps auth, retries, and base URL handling:

```python
def grep_search(pattern: str, top_k: int = 10) -> dict:
    response = mxbai.post(
        "/v1/stores/grep",
        body={
            "pattern": pattern,
            "store_identifiers": STORE_IDENTIFIERS[:1],  # a list, but grep covers one store per call
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
  body: { pattern, store_identifiers: STORE_IDENTIFIERS.slice(0, 1), top_k: topK },
});
```

- `pattern` is RE2, up to 1024 characters. Say so in the tool description.
- `targets` defaults to both `text` and `generated`. Keep both unless deliberately excluding ingestion-derived OCR, transcription, and summary fields.
- `store_identifiers` is schema-typed as a list (1–16 entries) but grep targets a single store: pass one. No pagination — raise `top_k` for more matches.

## Chunk listing

`stores.list_chunks()` selects by metadata instead of by query, and also targets a single store per call:

```python
kwargs = {
    "store_identifiers": STORE_IDENTIFIERS[:1],
    "filters": filters,
    "top_k": top_k,
    "search_options": {"return_metadata": True},   # metadata is what you filter and rank on
}
if rank_by:
    kwargs["sort_by"] = [rank_by, direction == "asc"]
response = mxbai.stores.list_chunks(**kwargs)
```

A `sort_by` field the backend cannot order server-side raises `UnprocessableEntityError`; catch it and rank client-side rather than failing the tool call.

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
    file_identifier=file_id,
    store_identifier=STORE_IDENTIFIERS[0],  # this endpoint accepts one store
    return_chunks=[3, 4, 5],                # or True for every chunk
)
```

Pass `file_identifier` by keyword: positional works with the SDK but fails the `RetrievalClient` protocol check in toast-harness. Resolve the model's handles to `(file_id, chunk_index)` yourself and validate the range: an index past the end of the file fails with HTTP 422 (`Invalid chunk indices: [0, 1], but must be between 0 and 0`). Clamp and return a structured error instead of letting that reach the model as an exception.

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

Fields available for the envelope: `text`, `score`, `filename`, `file_id`, `store_id`, `external_id`, `chunk_index`, `offset`, `metadata`, `generated_metadata`, `summary`, `context`, `type`, and `mime_type`. `text` is a text chunk's field; image chunks carry `ocr_text` and audio/video chunks `transcription` instead, so fall back across them when the store is not text-only.
