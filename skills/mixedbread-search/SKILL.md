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

Docs: https://www.mixedbread.com/docs/stores/overview.md

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

mxbai = Mixedbread()

# Create a store
store = mxbai.stores.create(name="my-docs", description="Product documentation")

# Upload a file
mxbai.stores.files.upload(store_identifier=store.id, file=open("guide.pdf", "rb"))

# Search
results = mxbai.stores.search(
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

const mxbai = new Mixedbread();

const store = await mxbai.stores.create({
    name: 'my-docs',
    description: 'Product documentation',
});

await mxbai.stores.files.upload(store.id, { file: fs.createReadStream('guide.pdf') });

const results = await mxbai.stores.search({
    query: 'How does authentication work?',
    store_identifiers: ['my-docs'],
    top_k: 5,
});
```

## Decision Tree

- **What kind of retrieval do you need?**
  - Simple keyword/semantic lookup → Standard `search()` with `top_k`
  - Natural-language answer with citations → `question_answering()` with `cite` enabled
  - Complex multi-hop question → `search()` with `agentic` enabled
  - Combine internal docs with live web → Add `"mixedbread/web"` to `store_identifiers`
- **Do you need metadata filtering?**
  - Don't know what metadata exists → Call `metadata_facets()` first
  - Know the fields → Build `filters` with `all`/`any`/`none` combinators
- **Do you need higher relevance?**
  - Yes → Enable `rerank` in `search_options`
- **Is the store temporary (e.g., PR review)?**
  - Yes → Set `expires_after` with a day limit at creation

## Workflows

### Build a Searchable Knowledge Base

Create a store, upload documents, verify they're processed, then search.

**Python:**
```python
# 1. Create the store
store = mxbai.stores.create(
    name="product-docs",
    description="Product documentation",
    config={"contextualization": True},
)

# 2. Upload files
mxbai.stores.files.upload(store_identifier=store.id, file=open("guide.pdf", "rb"))
mxbai.stores.files.upload(store_identifier=store.id, file=open("faq.md", "rb"))

# 3. Verify files are processed
store = mxbai.stores.retrieve("product-docs")
print(f"Completed: {store.file_counts.completed}, In progress: {store.file_counts.in_progress}")
# Wait until file_counts.completed > 0 before searching

# 4. Search
results = mxbai.stores.search(
    query="How do I reset my password?",
    store_identifiers=["product-docs"],
    top_k=5,
    search_options={"rerank": True},
)
```

**TypeScript:**
```typescript
// 1. Create the store
const store = await mxbai.stores.create({
    name: 'product-docs',
    description: 'Product documentation',
    config: { contextualization: true },
});

// 2. Upload files
await mxbai.stores.files.upload(store.id, { file: fs.createReadStream('guide.pdf') });
await mxbai.stores.files.upload(store.id, { file: fs.createReadStream('faq.md') });

// 3. Verify files are processed
const updated = await mxbai.stores.retrieve('product-docs');
console.log(`Completed: ${updated.file_counts.completed}, In progress: ${updated.file_counts.in_progress}`);
// Wait until file_counts.completed > 0 before searching

// 4. Search
const results = await mxbai.stores.search({
    query: 'How do I reset my password?',
    store_identifiers: ['product-docs'],
    top_k: 5,
    search_options: { rerank: true },
});
```

### Filter-Driven Search

Discover available metadata, then build targeted filters.

**Python:**
```python
# 1. Discover what metadata exists
facets = mxbai.stores.metadata_facets(store_identifiers=["product-docs"])
for facet in facets.data:
    print(f"{facet.key}: {facet.values}")

# 2. Build a filter based on discovered facets
results = mxbai.stores.search(
    query="deployment guide",
    store_identifiers=["product-docs"],
    top_k=10,
    filters={
        "all": [
            {"key": "category", "operator": "eq", "value": "guides"},
            {"key": "status", "operator": "not_eq", "value": "archived"},
        ]
    },
    search_options={"rerank": True, "return_metadata": True},
)
```

**TypeScript:**
```typescript
// 1. Discover what metadata exists
const facets = await mxbai.stores.metadataFacets({
    store_identifiers: ['product-docs'],
});
for (const facet of facets.data) {
    console.log(`${facet.key}: ${JSON.stringify(facet.values)}`);
}

// 2. Build a filter based on discovered facets
const results = await mxbai.stores.search({
    query: 'deployment guide',
    store_identifiers: ['product-docs'],
    top_k: 10,
    filters: {
        all: [
            { key: 'category', operator: 'eq', value: 'guides' },
            { key: 'status', operator: 'not_eq', value: 'archived' },
        ],
    },
    search_options: { rerank: true, return_metadata: true },
});
```

Filter operators: `eq`, `not_eq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `like`, `starts_with`, `not_like`, `regex`. Combine with `all` (AND), `any` (OR), `none` (NOT).

### Web-Augmented Search

Include `"mixedbread/web"` in `store_identifiers` to combine store search with live web results. This is a reserved store identifier — no setup required. You can also search the web alone.

**Python:**
```python
results = mxbai.stores.search(
    query="latest best practices",
    store_identifiers=["my-docs", "mixedbread/web"],
)
```

**TypeScript:**
```typescript
const results = await mxbai.stores.search({
    query: 'latest best practices',
    store_identifiers: ['my-docs', 'mixedbread/web'],
});
```

### Question Answering

Get a generated answer with cited sources.

**Python:**
```python
result = mxbai.stores.question_answering(
    query="What are the rate limits?",
    store_identifiers=["my-docs"],
    top_k=10,
    qa_options={"cite": True},
    search_options={"rerank": True},
)
print(result.answer)
for source in result.sources:
    print(f"  {source.filename} (score: {source.score:.3f})")
```

**TypeScript:**
```typescript
const result = await mxbai.stores.questionAnswering({
    query: 'What are the rate limits?',
    store_identifiers: ['my-docs'],
    top_k: 10,
    qa_options: { cite: true },
    search_options: { rerank: true },
});
console.log(result.answer);
for (const source of result.sources) {
    console.log(`  ${source.filename} (score: ${source.score.toFixed(3)})`);
}
```

### Agentic Search

For complex questions requiring multi-step retrieval. The system decomposes your query into sub-queries and runs multiple rounds.

**Python:**
```python
results = mxbai.stores.search(
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

**TypeScript:**
```typescript
const results = await mxbai.stores.search({
    query: 'Compare the pricing tiers and their feature differences',
    store_identifiers: ['product-docs'],
    search_options: {
        agentic: {
            max_rounds: 3,
            queries_per_round: 2,
            results_per_query: 5,
        },
    },
});
```

Set `agentic` to `true` for default settings, or pass an object to control rounds, queries per round, and results per query.

## Rules

### CRITICAL
- **Store names must be lowercase letters, numbers, hyphens, and periods only.** Invalid names cause creation to fail. No spaces, underscores, or uppercase.

### HIGH
- **Check `file_counts.completed > 0` before searching.** Searching a store with no completed files returns empty results. After uploading, retrieve the store and verify files have finished processing.
- **Use `metadata_facets()` before building filters.** Don't guess metadata keys — discover them. Typos in filter keys silently return no results.
- **Enable `rerank` for production search.** Reranking significantly improves relevance. Only skip it for latency-sensitive prototyping.
- **Use standard search for simple lookups.** Agentic search adds latency from multiple retrieval rounds. Only use it for complex, multi-hop questions.

### MEDIUM
- **Set `expires_after` for temporary stores.** PR review stores, demo stores, and test stores should auto-expire to avoid accumulating unused indexes.
- **One store per knowledge domain, not per query.** Stores are persistent indexes meant to be reused. Create once, search many times.
- **Use `score_threshold` to filter low-relevance noise.** Without a threshold, you may get results that are technically "closest" but not actually relevant.
- **Start with default `agentic` settings.** Only increase `max_rounds` if results are insufficient.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No results returned | Store has no completed files | Check `store.file_counts.completed > 0`. Wait for processing to finish. |
| No results returned | `score_threshold` too high | Lower or remove `score_threshold`. |
| No results returned | Wrong `store_identifiers` | Verify the store name or ID matches exactly. |
| Metadata filters return nothing | Wrong key name or value | Use `metadata_facets()` to discover actual keys and values. |
| Slow agentic search | Too many rounds or queries | Reduce `max_rounds` or `queries_per_round`. Use standard search if the query is simple. |
| API key error | Invalid or missing key | Verify `MXBAI_API_KEY` is set. Get a key at https://platform.mixedbread.com/platform?next=api-keys |
