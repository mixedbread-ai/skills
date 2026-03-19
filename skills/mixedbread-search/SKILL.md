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
Agent-readable docs: https://www.mixedbread.com/docs/llms.txt
Latest docs search: https://www.mixedbread.com/question?q=stores&section=docs

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
import os
from mixedbread import Mixedbread

mxbai = Mixedbread(api_key=os.environ["MXBAI_API_KEY"])

store = mxbai.stores.create(name="my-docs", description="Product documentation")

mxbai.stores.files.upload(
    store_identifier=store.id,
    file=open("guide.pdf", "rb"),
    metadata={"category": "guides", "version": "2.0"},
)

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
import { Mixedbread } from '@mixedbread/sdk';
import fs from 'fs';

const mxbai = new Mixedbread({
    apiKey: process.env.MXBAI_API_KEY!,
});

const store = await mxbai.stores.create({
    name: 'my-docs',
    description: 'Product documentation',
});

await mxbai.stores.files.upload({
    storeIdentifier: store.id,
    file: fs.createReadStream('guide.pdf'),
    body: { metadata: { category: 'guides', version: '2.0' } },
});

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
  - Yes → Set `"rerank": true` in `search_options`, or use `{"rerank": {"model": "mixedbread-ai/mxbai-rerank-large-v2"}}` to choose a model
- **Is the store temporary (e.g., PR review)?**
  - Yes → Set `expires_after` with a day limit at creation

## Workflows

### Build a Searchable Knowledge Base

Create a store, upload documents, and search. Most of the time you do not need to poll for finished files. Only gate on processing when the workflow depends on complete batch coverage, such as benchmarks or recall evaluation.

**Python:**
```python
store = mxbai.stores.create(
    name="product-docs",
    description="Product documentation",
    config={"contextualization": {"with_metadata": ["title", "category"]}},
)

mxbai.stores.files.upload(
    store_identifier=store.id,
    file=open("guide.pdf", "rb"),
    metadata={"title": "Setup Guide", "category": "guides"},
)
mxbai.stores.files.upload(
    store_identifier=store.id,
    file=open("faq.md", "rb"),
    metadata={"title": "FAQ", "category": "support"},
)

results = mxbai.stores.search(
    query="How do I reset my password?",
    store_identifiers=["product-docs"],
    top_k=5,
    search_options={"rerank": True, "return_metadata": True},
)
for chunk in results.data:
    print(f"{chunk.score:.3f} | {chunk.filename}: {chunk.text[:100]}")

# Optional: poll store.file_counts if you need deterministic full-batch coverage (benchmarks, migrations).
```

**TypeScript:**
```typescript
const store = await mxbai.stores.create({
    name: 'product-docs',
    description: 'Product documentation',
    config: { contextualization: { with_metadata: ['title', 'category'] } },
});

await mxbai.stores.files.upload({
    storeIdentifier: store.id,
    file: fs.createReadStream('guide.pdf'),
    body: { metadata: { title: 'Setup Guide', category: 'guides' } },
});
await mxbai.stores.files.upload({
    storeIdentifier: store.id,
    file: fs.createReadStream('faq.md'),
    body: { metadata: { title: 'FAQ', category: 'support' } },
});

const results = await mxbai.stores.search({
    query: 'How do I reset my password?',
    store_identifiers: ['product-docs'],
    top_k: 5,
    search_options: { rerank: true, return_metadata: true },
});

// Optional: poll store.file_counts if you need deterministic full-batch coverage (benchmarks, migrations).
```

### Filter-Driven Search

Discover available metadata, then build targeted filters.

**Python:**
```python
facets = mxbai.stores.metadata_facets(store_identifiers=["product-docs"])
for key, values in facets.facets.items():
    print(f"{key}: {values}")

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
const facets = await mxbai.stores.metadataFacets({
    store_identifiers: ['product-docs'],
});
for (const [key, values] of Object.entries(facets.facets ?? {})) {
    console.log(`${key}: ${JSON.stringify(values)}`);
}

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

Get a generated answer with cited sources. The answer may contain `<cite i="n"/>` tags referencing the sources list.

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

### Question Answering with Agentic Fallback

When QA returns no sources, retry with agentic search for deeper retrieval. Always re-call `question_answering()` — do not fall back to raw `search()`, which loses the generated answer.

**Python:**
```python
result = mxbai.stores.question_answering(
    query="Compare the pricing tiers and their feature differences",
    store_identifiers=["my-docs"],
    top_k=10,
    qa_options={"cite": True},
    search_options={"rerank": True},
)

if not result.sources:
    result = mxbai.stores.question_answering(
        query="Compare the pricing tiers and their feature differences",
        store_identifiers=["my-docs"],
        top_k=10,
        qa_options={"cite": True},
        search_options={
            "rerank": True,
            "agentic": {"max_rounds": 3},
        },
    )

print(result.answer)
for source in result.sources:
    print(f"  {source.filename} (score: {source.score:.3f})")
```

### Agentic Search

For complex questions requiring multi-step retrieval. The system decomposes your query into sub-queries and runs multiple rounds. Works in both `search()` and `question_answering()`.

**Python:**
```python
results = mxbai.stores.search(
    query="Compare the pricing tiers and their feature differences",
    store_identifiers=["product-docs"],
    search_options={
        "agentic": {
            "max_rounds": 3,
            "queries_per_round": 2,
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
        },
    },
});
```

Set `agentic` to `true` for default settings, or pass an object to control `max_rounds` and `queries_per_round`.

## Response Shapes

**Search results** (`search()` returns):
```python
response.data  # list of chunks
chunk.text       # str — the matched text
chunk.score      # float — relevance score (0–1)
chunk.filename   # str — source file name
chunk.file_id    # str — source file ID
chunk.store_id   # str — store the chunk belongs to
chunk.metadata   # dict — attached metadata (when return_metadata is enabled)
chunk.type       # str — chunk type (e.g. "text", "image_url")
chunk.image_url  # dict | None — image payload for image chunks
chunk.ocr_text   # str | None — OCR text for image-heavy chunks
```

**QA results** (`question_answering()` returns):
```python
result.answer    # str — generated answer, may contain <cite i="n"/> tags
result.sources   # list of source objects
source.filename  # str
source.score     # float
source.file_id   # str
source.text      # str — the source chunk text
source.image_url # dict | None — image payload with url/format for image chunks
```

## Store Management

```python
stores = mxbai.stores.list(limit=20)
for store in stores.data:
    print(store.name)

store = mxbai.stores.retrieve(store_identifier="my-docs")
print(store.file_counts)  # {"completed": 5, "in_progress": 2, "failed": 0}

mxbai.stores.delete(store_identifier="my-docs")

files = mxbai.stores.files.list(store_identifier="my-docs", limit=20)
for file in files.data:
    print(file.filename, file.status)
```

## Rules

### CRITICAL
- **Store names must be lowercase letters, numbers, hyphens, and periods only.** Invalid names cause creation to fail. No spaces, underscores, or uppercase.
- **For field-level contextualization, use the documented `{"with_metadata": [...]}` form.** The other documented modes are `true` (all metadata) and `false` (none). Dot notation is supported for nested fields.

### HIGH
- **Do not block on full ingestion unless completeness matters.** Stores process files asynchronously, and completed files become searchable as they finish. Most of the time, especially for interactive flows, upload and search immediately without polling. Poll file status or `file_counts` only when the workflow depends on complete batch coverage, such as benchmarks, migrations, or sync verification.
- **Use `metadata_facets()` before building filters.** Don't guess metadata keys — discover them. Typos in filter keys silently return no results.
- **Enable `rerank` for production search.** Reranking significantly improves relevance. Only skip it for latency-sensitive prototyping.
- **Use standard search for simple lookups.** Agentic search adds latency from multiple retrieval rounds. Only use it for complex, multi-hop questions.

### MEDIUM
- **Set `expires_after` for temporary stores.** PR review stores, demo stores, and test stores should auto-expire to avoid accumulating unused indexes.
- **One store per knowledge domain, not per query.** Stores are persistent indexes meant to be reused. Create once, search many times.
- **Use chunk scores to filter low-relevance noise.** If you need a minimum relevance cutoff, post-filter on `chunk.score` (for example `>= 0.3`) after retrieval.
- **Start with default `agentic` settings.** Only increase `max_rounds` if results are insufficient.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No results returned | Newly uploaded files are still processing, or the store name/query is wrong | Retry after processing completes for at least one file. For completeness-sensitive runs, verify the expected files are `completed` before evaluating results. |
| No results returned | Score cutoff too high | Lower or remove your post-filter threshold. |
| No results returned | Wrong `store_identifiers` | Verify the store name or ID matches exactly. |
| Metadata filters return nothing | Wrong key name or value | Use `metadata_facets()` to discover actual keys and values. |
| Slow agentic search | Too many rounds or queries | Reduce `max_rounds` or `queries_per_round`. Use standard search if the query is simple. |
| API key error | Invalid or missing key | Verify `MXBAI_API_KEY` is set. Get a key at https://platform.mixedbread.com/platform?next=api-keys |
