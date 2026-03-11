---
name: mixedbread-search
description: >-
  Build and query managed search indexes (Stores) using the Mixedbread Python and TypeScript SDKs.
  Use when creating knowledge bases, uploading documents, performing semantic or vector search,
  asking questions over documents, using agentic multi-step retrieval, combining store search with
  web results, filtering by metadata, reranking, or discovering metadata facets.
---

# Mixedbread Search

Create and search managed knowledge bases using the Stores API. Stores are multimodal search indexes that handle text, images, tables, audio, and video across 100+ languages.

## Setup

```bash
pip install mixedbread          # Python
npm install @mixedbread/sdk     # TypeScript
```

```bash
export MXBAI_API_KEY=your_api_key
```

## Quick Start

**Python:**
```python
from mixedbread import Mixedbread

client = Mixedbread()

# Create a store
store = client.stores.create(name="my-docs", description="Product documentation")

# Upload a file
client.stores.files.upload(store_identifier=store.id, file=open("guide.pdf", "rb"))

# Search
results = client.stores.search(
    query="How does authentication work?",
    store_identifiers=["my-docs"],
    top_k=5,
)
for chunk in results.data:
    print(f"{chunk.score:.3f} | {chunk.filename}: {chunk.text[:100]}")
```

**TypeScript:**
```typescript
import Mixedbread from '@mixedbread/sdk';
import fs from 'fs';

const client = new Mixedbread();

const store = await client.stores.create({
    name: 'my-docs',
    description: 'Product documentation',
});

await client.stores.files.upload(store.id, { file: fs.createReadStream('guide.pdf') });

const results = await client.stores.search({
    query: 'How does authentication work?',
    store_identifiers: ['my-docs'],
    top_k: 5,
});
```

## SDK Reference

### Store Operations

| Operation | Python | TypeScript |
|-----------|--------|------------|
| Create | `client.stores.create(name=..., description=...)` | `client.stores.create({ name, description })` |
| Retrieve | `client.stores.retrieve(store_identifier)` | `client.stores.retrieve(storeIdentifier)` |
| Update | `client.stores.update(store_identifier, ...)` | `client.stores.update(storeIdentifier, {...})` |
| List | `client.stores.list()` | `client.stores.list()` |
| Delete | `client.stores.delete(store_identifier)` | `client.stores.delete(storeIdentifier)` |

### File Upload

| Operation | Python | TypeScript |
|-----------|--------|------------|
| Upload to store | `client.stores.files.upload(store_identifier, file=...)` | `client.stores.files.upload(storeId, {file})` |

### Search & QA

| Operation | Python | TypeScript |
|-----------|--------|------------|
| Search | `client.stores.search(query=..., store_identifiers=[...])` | `client.stores.search({ query, store_identifiers })` |
| Question answering | `client.stores.question_answering(query=..., store_identifiers=[...])` | `client.stores.questionAnswering({ query, store_identifiers })` |
| Metadata facets | `client.stores.metadata_facets(store_identifiers=[...])` | `client.stores.metadataFacets({ store_identifiers })` |

## Store Configuration

```python
store = client.stores.create(
    name="my-docs",
    description="Product documentation",
    config={
        "contextualization": {"with_metadata": ["title", "category"]},
        "save_content": True,
    },
    expires_after={"anchor": "last_active_at", "days": 30},
    metadata={"team": "engineering"},
    is_public=False,
)
```

Key config options:
- **`contextualization`**: Include metadata fields in embeddings for richer search. Set to `True` for all metadata, or specify fields like `["title", "author"]`.
- **`save_content`**: Store original content (default `True`). Set `False` for index-only mode (no reranking).
- **`expires_after`**: Auto-delete after N days of inactivity.
- **`is_public`**: Allow anyone with an API key to search.

## Search with Filters

```python
results = client.stores.search(
    query="deployment guide",
    store_identifiers=["my-docs"],
    top_k=10,
    filters={
        "all": [
            {"key": "category", "operator": "eq", "value": "guides"},
            {"key": "status", "operator": "not_eq", "value": "archived"},
        ]
    },
    search_options={
        "rerank": True,
        "return_metadata": True,
        "score_threshold": 0.3,
    },
)
```

Filter operators: `eq`, `not_eq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `like`, `starts_with`, `not_like`, `regex`.

Combine with `all` (AND), `any` (OR), `none` (NOT).

## Search Options

| Option | Type | Description |
|--------|------|-------------|
| `score_threshold` | float | Minimum score to include a result. |
| `rewrite_query` | bool | Rewrite the query for better retrieval. |
| `rerank` | bool \| object | Rerank results. Object: `{model, with_metadata, top_k}`. |
| `agentic` | bool \| object | Multi-step agentic retrieval (see below). |
| `return_metadata` | bool | Include metadata in results. |
| `apply_search_rules` | bool | Apply store-level search rules configured via the dashboard. |

## Agentic Search

For complex questions that benefit from multi-step retrieval. The system decomposes your query into sub-queries and runs multiple retrieval rounds, refining results iteratively to find the most comprehensive answer.

```python
results = client.stores.search(
    query="Compare the pricing tiers and their feature differences",
    store_identifiers=["product-docs"],
    search_options={
        "agentic": {
            "max_rounds": 3,
            "queries_per_round": 2,
            "results_per_query": 5,
        }
    },
)
```

Set `"agentic": True` for default settings, or pass an object to control rounds, queries per round, and results per query.

## Question Answering

```python
result = client.stores.question_answering(
    query="What are the rate limits?",
    store_identifiers=["my-docs"],
    top_k=10,
    qa_options={"cite": True, "multimodal": True},
    search_options={"rerank": True},
)
print(result.answer)
for source in result.sources:
    print(f"  {source.filename} (score: {source.score:.3f})")
```

## Web Search Integration

Include `"mixedbread/web"` in `store_identifiers` to combine store search with live web results. This is a reserved store identifier — no setup required. Web results include title, URL, and excerpts alongside your store results.

```python
results = client.stores.search(
    query="latest best practices",
    store_identifiers=["my-docs", "mixedbread/web"],
)
```

You can also search the web alone by using only `"mixedbread/web"` as the store identifier.

## Anti-Patterns

- **Don't create a new store per query.** Stores are persistent indexes meant to be reused. Create once, search many times.
- **Don't use agentic search for simple lookups.** Agentic search adds latency from multiple retrieval rounds. Use standard search for straightforward queries.
- **Don't set `save_content: False` if you need reranking or QA.** Reranking and question answering require access to the original content.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No results returned | Check that the store has completed files (`store.file_counts.completed > 0`). Lower `score_threshold` if set. Verify `store_identifiers` matches your store name or ID. |
| Metadata filters not working | Use `metadata_facets()` to discover available metadata keys and values before building filters. |
| Reranking not improving results | Reranking requires `save_content: True` on the store. Check store config. |
| API key error | Verify `MXBAI_API_KEY` is set and valid. Get a key at https://platform.mixedbread.com/platform?next=api-keys |
| Slow agentic search | Reduce `max_rounds` or `queries_per_round`. Use standard search if the query is simple. |

## References

| Topic | Reference |
|-------|-----------|
| Store CRUD operations | [references/stores-api.md](references/stores-api.md) |
| File upload, metadata, and filters | [references/store-files-api.md](references/store-files-api.md) |
| Search and QA endpoints | [references/search-and-qa-api.md](references/search-and-qa-api.md) |
