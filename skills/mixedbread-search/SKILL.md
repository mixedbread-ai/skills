---
name: mixedbread-search
description: Build and query managed search indexes (Stores) using the Mixedbread Python and TypeScript SDKs. Use when creating knowledge bases, uploading documents, performing semantic search, asking questions over documents, or connecting external data sources via the API.
---

# Mixedbread Search

Create and search managed knowledge bases using the Stores API. Stores are multimodal search indexes that handle text, images, tables, audio, and video across 100+ languages.

## Setup

```bash
pip install mixedbread          # Python
npm install @mixedbread/sdk     # TypeScript
```

```bash
export MXBAI_API_KEY=your-api-key
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
| Create | `client.stores.create(name=..., description=...)` | `client.stores.create({name, description})` |
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
| Search | `client.stores.search(query=..., store_identifiers=[...])` | `client.stores.search({query, store_identifiers})` |
| Question answering | `client.stores.question_answering(query=..., store_identifiers=[...])` | `client.stores.questionAnswering({query, store_identifiers})` |
| Metadata facets | `client.stores.metadata_facets(store_identifiers=[...])` | `client.stores.metadataFacets({store_identifiers})` |

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

## Agentic Search

For complex questions that benefit from multi-step retrieval:

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

Combine store search with web results:

```python
results = client.stores.search(
    query="latest best practices",
    store_identifiers=["my-docs", "mixedbread/web"],
)
```

## References

| Topic | Reference |
|-------|-----------|
| Store CRUD operations | [references/stores-api.md](references/stores-api.md) |
| File upload, metadata, and filters | [references/store-files-api.md](references/store-files-api.md) |
| Search and QA endpoints | [references/search-and-qa-api.md](references/search-and-qa-api.md) |
| External data sources | [references/data-sources.md](references/data-sources.md) |
