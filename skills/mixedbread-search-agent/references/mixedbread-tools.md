# Backing function tools with Mixedbread Stores

For a loop you run yourself with Stores as the backend. Hosted tools are an alternative when you want the API to manage retrieval — see [hosted-tools.md](hosted-tools.md). The examples below show custom function implementations; their names and interfaces are yours to adapt.

Read [tool-contracts.md](tool-contracts.md) for the schemas, envelopes, and descriptions; SKILL.md for the API. This is only the wiring. For building the Stores themselves, use the `mixedbread-search` skill.

## Which call backs which tool

| Tool you define | Backing call | Matches on | Hosted equivalent |
| --- | --- | --- | --- |
| `semantic_search` | `stores.search()` | Meaning and paraphrase | `search_corpus` |
| `grep_search` | `POST /v1/stores/grep` | RE2 regex, literal tokens | `grep` |
| `list_chunks` | `stores.list_chunks()` | Metadata filters, numeric order | `filter_chunks` |
| `metadata_facets` | `stores.metadata_facets()` | Nothing — it describes the corpus | `inspect_metadata` |
| `expand_chunks` | `stores.files.retrieve()` | Known chunk identity | `get_chunks` |

For a fixed corpus, pin `store_identifiers` in application config. If the model chooses stores, `stores.list()` can help it discover valid names. Enforce access scope independently of that choice.

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

Consider `rerank` for better evidence quality and measure its latency tradeoff. Using `search_options={"agentic": True}` invokes another search-agent loop; use that when you deliberately want nested agentic retrieval, and account for its additional work.

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

A `sort_by` field the backend cannot order server-side raises `UnprocessableEntityError`. Report the limitation, or use a client-side fallback that clearly states which retrieved subset it ordered.

`sort_by` takes a field name or `[field, ascending]`. Unprefixed paths target file metadata; `generated_metadata.*` targets chunk metadata. For numeric metric ordering, confirm the field's type and report non-numeric or missing values. Other ordering depends on the backend's supported sorts.

## Metadata facets

```python
facets = mxbai.stores.metadata_facets(store_identifiers=STORE_IDENTIFIERS)
# {"year": {"2023": 1, "2024": 1}, "author": {"Dana Lee": 1, "Joe Smith": 1}}
```

Use facets or metadata on results to confirm unfamiliar filter keys. A nonexistent key can quietly produce zero results.

## Chunk expansion

```python
file = mxbai.stores.files.retrieve(
    file_identifier=file_id,
    store_identifier=STORE_IDENTIFIERS[0],  # this endpoint accepts one store
    return_chunks=[3, 4, 5],                # or True for every chunk
)
```

Resolve evidence references to `(file_id, chunk_index)` and validate the requested range. An out-of-range index fails with HTTP 422; return an informative tool error rather than allowing an exception to escape the executor.

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

A flat condition list plus `filter_mode: "all" | "any"` can simplify the model's interface; your function can build the tree. Enforce application access scope independently of model-supplied filters.

## Chunk identity and available fields

`stores.search`, grep, and list-chunks share a chunk shape, so a common envelope can serve all three. Preserve `(store_id, file_id, chunk_index)` as the source identity. Short handles are optional; keep references stable across calls and retain their provenance application-side.

Fields available for the envelope: `text`, `score`, `filename`, `file_id`, `store_id`, `external_id`, `chunk_index`, `offset`, `metadata`, `generated_metadata`, `summary`, `context`, `type`, and `mime_type`. `text` is a text chunk's field; image chunks carry `ocr_text` and audio/video chunks `transcription` instead, so fall back across them when the store is not text-only.
