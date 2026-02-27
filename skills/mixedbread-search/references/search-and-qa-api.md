# Search and Question Answering API

Semantic search and question answering over Stores.

Base URL: `https://api.mixedbread.com`

## Search

```
POST /v1/stores/search
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string \| ImageURLInput \| TextInput | Yes | Search query. String for text, or structured input for images. |
| `store_identifiers` | string[] | Yes | Store names or IDs to search. Include `"mixedbread/web"` for web results. |
| `top_k` | int | No | Number of results to return. |
| `filters` | SearchFilter \| SearchFilterCondition | No | Metadata filters (see [metadata-and-filters.md](metadata-and-filters.md)). |
| `file_ids` | string[] | No | Restrict search to specific file IDs. |
| `search_options` | StoreChunkSearchOptions | No | Advanced search configuration. |

### StoreChunkSearchOptions

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `score_threshold` | float | — | Minimum score to include a result. |
| `rewrite_query` | bool | — | Rewrite the query for better retrieval. |
| `rerank` | bool \| object | — | Rerank results. Object form: `{model, with_metadata, top_k}`. |
| `agentic` | bool \| object | — | Multi-step agentic retrieval. Object form: `{max_rounds, queries_per_round, results_per_query}`. |
| `return_metadata` | bool | — | Include metadata in results. |
| `apply_search_rules` | bool | — | Apply store-level search rules. |

### Basic Search

**Python:**
```python
from mixedbread import Mixedbread

client = Mixedbread()

results = client.stores.search(
    query="How do I configure authentication?",
    store_identifiers=["product-docs"],
    top_k=10,
)
for chunk in results.data:
    print(f"{chunk.score:.3f} | {chunk.filename}: {chunk.text[:120]}")
```

**TypeScript:**
```typescript
import Mixedbread from '@mixedbread/sdk';

const client = new Mixedbread();

const results = await client.stores.search({
    query: 'How do I configure authentication?',
    store_identifiers: ['product-docs'],
    top_k: 10,
});
for (const chunk of results.data) {
    console.log(`${chunk.score.toFixed(3)} | ${chunk.filename}: ${chunk.text?.slice(0, 120)}`);
}
```

### Search with Filters and Reranking

**Python:**
```python
results = client.stores.search(
    query="deployment best practices",
    store_identifiers=["product-docs"],
    top_k=20,
    filters={
        "all": [
            {"key": "category", "operator": "eq", "value": "guides"},
            {"key": "year", "operator": "gte", "value": "2024"},
        ]
    },
    search_options={
        "rerank": {
            "model": "mixedbread-ai/mxbai-rerank-large-v2",
            "with_metadata": True,
            "top_k": 5,
        },
        "return_metadata": True,
        "score_threshold": 0.3,
    },
)
for chunk in results.data:
    print(f"{chunk.score:.3f} | {chunk.filename}")
    print(f"  metadata: {chunk.metadata}")
```

**TypeScript:**
```typescript
const results = await client.stores.search({
    query: 'deployment best practices',
    store_identifiers: ['product-docs'],
    top_k: 20,
    filters: {
        all: [
            { key: 'category', operator: 'eq', value: 'guides' },
            { key: 'year', operator: 'gte', value: '2024' },
        ],
    },
    search_options: {
        rerank: {
            model: 'mixedbread-ai/mxbai-rerank-large-v2',
            with_metadata: true,
            top_k: 5,
        },
        return_metadata: true,
        score_threshold: 0.3,
    },
});
```

### Agentic Search

For complex questions that benefit from iterative, multi-step retrieval.

**Python:**
```python
results = client.stores.search(
    query="Compare the pricing tiers and list feature differences between Pro and Enterprise",
    store_identifiers=["product-docs"],
    search_options={
        "agentic": {
            "max_rounds": 3,
            "queries_per_round": 2,
            "results_per_query": 5,
        },
        "rerank": True,
    },
)
for chunk in results.data:
    print(f"{chunk.score:.3f} | {chunk.filename}: {chunk.text[:150]}")
```

**TypeScript:**
```typescript
const results = await client.stores.search({
    query: 'Compare the pricing tiers and list feature differences between Pro and Enterprise',
    store_identifiers: ['product-docs'],
    search_options: {
        agentic: {
            max_rounds: 3,
            queries_per_round: 2,
            results_per_query: 5,
        },
        rerank: true,
    },
});
```

### Search with Web Results

Include `"mixedbread/web"` in `store_identifiers` to combine store search with web results.

**Python:**
```python
results = client.stores.search(
    query="latest security best practices",
    store_identifiers=["product-docs", "mixedbread/web"],
    top_k=10,
)
```

**TypeScript:**
```typescript
const results = await client.stores.search({
    query: 'latest security best practices',
    store_identifiers: ['product-docs', 'mixedbread/web'],
    top_k: 10,
});
```

### Restricting Search to Specific Files

**Python:**
```python
results = client.stores.search(
    query="rate limits",
    store_identifiers=["product-docs"],
    file_ids=["file_abc123", "file_def456"],
    top_k=5,
)
```

## Response Type: StoreSearchResponse

The `data` field contains an array of `ScoredChunk` objects. Chunk types depend on the content:

- `ScoredTextInputChunk` — text content
- `ScoredImageURLInputChunk` — image content

### ScoredTextInputChunk Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Chunk type identifier. |
| `text` | string | The matched text content. |
| `score` | float | Relevance score. |
| `chunk_index` | int | Position of this chunk within the file. |
| `offset` | int | Character offset in the original content. |
| `file_id` | string | Source file ID. |
| `filename` | string | Source filename. |
| `store_id` | string | Source store ID. |
| `metadata` | object | File metadata (when `return_metadata` is `true`). |
| `mime_type` | string | MIME type of the source file. |
| `model` | string | Embedding model used. |
| `generated_metadata` | object | Auto-generated metadata (e.g. extracted titles, headings). |

---

## Question Answering

```
POST /v1/stores/question-answering
```

Returns a generated answer with cited sources.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | The question to answer. |
| `store_identifiers` | string[] | Yes | Store names or IDs to search. |
| `top_k` | int | No | Number of source chunks to retrieve. |
| `filters` | SearchFilter \| SearchFilterCondition | No | Metadata filters. |
| `file_ids` | string[] | No | Restrict to specific files. |
| `search_options` | StoreChunkSearchOptions | No | Same options as search. |
| `stream` | bool | No | Stream the response. |
| `qa_options` | object | No | `{cite: bool, multimodal: bool}`. |

### QA Options

| Field | Type | Description |
|-------|------|-------------|
| `cite` | bool | Include inline citations in the answer. |
| `multimodal` | bool | Include images and other media in the answer context. |

### Basic QA

**Python:**
```python
result = client.stores.question_answering(
    query="What are the API rate limits?",
    store_identifiers=["product-docs"],
    top_k=10,
    qa_options={"cite": True},
    search_options={"rerank": True},
)
print(result.answer)
for source in result.sources:
    print(f"  [{source.score:.3f}] {source.filename}: {source.text[:80]}")
```

**TypeScript:**
```typescript
const result = await client.stores.questionAnswering({
    query: 'What are the API rate limits?',
    store_identifiers: ['product-docs'],
    top_k: 10,
    qa_options: { cite: true },
    search_options: { rerank: true },
});
console.log(result.answer);
for (const source of result.sources) {
    console.log(`  [${source.score.toFixed(3)}] ${source.filename}: ${source.text?.slice(0, 80)}`);
}
```

### Multimodal QA

**Python:**
```python
result = client.stores.question_answering(
    query="Describe the architecture diagram",
    store_identifiers=["product-docs"],
    qa_options={"cite": True, "multimodal": True},
)
print(result.answer)
```

### QA with Agentic Search

**Python:**
```python
result = client.stores.question_answering(
    query="How does the billing system handle upgrades vs downgrades differently?",
    store_identifiers=["product-docs"],
    search_options={
        "agentic": {
            "max_rounds": 3,
            "queries_per_round": 2,
            "results_per_query": 5,
        },
        "rerank": True,
    },
    qa_options={"cite": True},
)
print(result.answer)
```

### QA Response Type

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The generated answer text, with inline citations if `cite` is enabled. |
| `sources` | ScoredChunk[] | The source chunks used to generate the answer. |
