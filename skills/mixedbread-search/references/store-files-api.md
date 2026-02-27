# Store Files API

Upload files to Stores and filter search results by metadata.

Base URL: `https://api.mixedbread.com`

## Supported File Types

Text, Markdown, PDF, DOCX, PPTX, images (PNG, JPG, SVG, etc.), code files, audio, and video.

## Upload a File to a Store

```
POST /v1/stores/{store_identifier}/files
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | file | Yes | The file to upload. |
| `metadata` | object | No | Key-value metadata to attach to the file in this store. |
| `config` | object | No | `{parsing_strategy: "fast" \| "high_quality"}`. |
| `external_id` | string | No | External identifier for the file. |
| `overwrite` | bool | No | If `true`, replace file if `external_id` already exists. |

**Python:**
```python
from mixedbread import Mixedbread

client = Mixedbread()

store_file = client.stores.files.upload(
    store_identifier="product-docs",
    file=open("report.pdf", "rb"),
    metadata={"category": "reports", "year": "2025"},
    config={"parsing_strategy": "high_quality"},
)
```

**TypeScript:**
```typescript
import Mixedbread from '@mixedbread/sdk';
import fs from 'fs';

const client = new Mixedbread();

const storeFile = await client.stores.files.upload('product-docs', {
    file: fs.createReadStream('report.pdf'),
    metadata: { category: 'reports', year: '2025' },
    config: { parsing_strategy: 'high_quality' },
});
```

### Batch Upload Example

**Python:**
```python
import os
from mixedbread import Mixedbread

client = Mixedbread()

pdf_dir = "./documents"
for filename in os.listdir(pdf_dir):
    if filename.endswith(".pdf"):
        client.stores.files.upload(
            store_identifier="product-docs",
            file=open(os.path.join(pdf_dir, filename), "rb"),
            metadata={"source": "local", "filename": filename},
        )
        print(f"Uploaded: {filename}")
```

## Metadata

Metadata is a key-value map attached to files within a store. Keys are strings, values can be any JSON type (string, number, boolean, array, object).

### Upload with Rich Metadata

**Python:**
```python
client.stores.files.upload(
    store_identifier="product-docs",
    file=open("report.pdf", "rb"),
    metadata={
        "category": "reports",
        "year": 2025,
        "tags": ["quarterly", "finance"],
        "reviewed": True,
    },
)
```

**TypeScript:**
```typescript
await client.stores.files.upload('product-docs', {
    file: fs.createReadStream('report.pdf'),
    metadata: {
        category: 'reports',
        year: 2025,
        tags: ['quarterly', 'finance'],
        reviewed: true,
    },
});
```

### Contextualization

Store-level config can embed metadata into vector representations for richer semantic search.

```python
store = client.stores.create(
    name="enriched-docs",
    config={
        # Include specific metadata fields in embeddings
        "contextualization": {"with_metadata": ["title", "category", "author"]},
    },
)
```

Set `contextualization` to `True` to include all metadata fields, or provide a list of specific field names.

---

## Search Filters

Filters narrow search results based on metadata values.

### SearchFilterCondition

A single condition on a metadata field.

```json
{"key": "category", "operator": "eq", "value": "guides"}
```

| Field | Type | Description |
|-------|------|-------------|
| `key` | string | Metadata field name. |
| `operator` | string | Comparison operator (see below). |
| `value` | any | Value to compare against. |

### Operators

| Operator | Description | Example Value |
|----------|-------------|---------------|
| `eq` | Equals | `"guides"` |
| `not_eq` | Not equals | `"archived"` |
| `gt` | Greater than | `100` |
| `gte` | Greater than or equal | `2024` |
| `lt` | Less than | `50` |
| `lte` | Less than or equal | `2023` |
| `in` | In list | `["guides", "tutorials"]` |
| `not_in` | Not in list | `["draft", "archived"]` |
| `like` | Pattern match (SQL LIKE) | `"%deploy%"` |
| `starts_with` | Starts with prefix | `"prod-"` |
| `not_like` | Negated pattern match | `"%test%"` |
| `regex` | Regular expression match | `"^v[0-9]+\\."` |

### SearchFilter (Compound)

Combine conditions with logical operators. These are combinable and nestable.

```json
{
    "all": [...],   // AND — all conditions must match
    "any": [...],   // OR  — at least one condition must match
    "none": [...]   // NOT — no condition may match
}
```

Each array element can be a `SearchFilterCondition` or another nested `SearchFilter`.

---

## Filter Examples

### Simple Filter

**Python:**
```python
results = client.stores.search(
    query="deployment instructions",
    store_identifiers=["product-docs"],
    filters={"key": "category", "operator": "eq", "value": "guides"},
)
```

**TypeScript:**
```typescript
const results = await client.stores.search({
    query: 'deployment instructions',
    store_identifiers: ['product-docs'],
    filters: { key: 'category', operator: 'eq', value: 'guides' },
});
```

### Compound Filter (AND + NOT)

**Python:**
```python
results = client.stores.search(
    query="API reference",
    store_identifiers=["product-docs"],
    filters={
        "all": [
            {"key": "category", "operator": "in", "value": ["guides", "reference"]},
            {"key": "year", "operator": "gte", "value": 2024},
        ],
        "none": [
            {"key": "status", "operator": "eq", "value": "archived"},
        ],
    },
)
```

**TypeScript:**
```typescript
const results = await client.stores.search({
    query: 'API reference',
    store_identifiers: ['product-docs'],
    filters: {
        all: [
            { key: 'category', operator: 'in', value: ['guides', 'reference'] },
            { key: 'year', operator: 'gte', value: 2024 },
        ],
        none: [
            { key: 'status', operator: 'eq', value: 'archived' },
        ],
    },
});
```

### Nested Filter (OR of ANDs)

**Python:**
```python
results = client.stores.search(
    query="setup instructions",
    store_identifiers=["product-docs"],
    filters={
        "any": [
            {
                "all": [
                    {"key": "category", "operator": "eq", "value": "guides"},
                    {"key": "audience", "operator": "eq", "value": "developers"},
                ]
            },
            {
                "all": [
                    {"key": "category", "operator": "eq", "value": "tutorials"},
                    {"key": "difficulty", "operator": "in", "value": ["beginner", "intermediate"]},
                ]
            },
        ]
    },
)
```

**TypeScript:**
```typescript
const results = await client.stores.search({
    query: 'setup instructions',
    store_identifiers: ['product-docs'],
    filters: {
        any: [
            {
                all: [
                    { key: 'category', operator: 'eq', value: 'guides' },
                    { key: 'audience', operator: 'eq', value: 'developers' },
                ],
            },
            {
                all: [
                    { key: 'category', operator: 'eq', value: 'tutorials' },
                    { key: 'difficulty', operator: 'in', value: ['beginner', 'intermediate'] },
                ],
            },
        ],
    },
});
```

---

## Metadata Facets

```
POST /v1/stores/metadata-facets
```

Discover available metadata keys and their value distributions across stores.

**Python:**
```python
facets = client.stores.metadata_facets(
    store_identifiers=["product-docs"],
)
for facet in facets.data:
    print(f"{facet.key}: {facet.values}")
```

**TypeScript:**
```typescript
const facets = await client.stores.metadataFacets({
    store_identifiers: ['product-docs'],
});
for (const facet of facets.data) {
    console.log(`${facet.key}: ${JSON.stringify(facet.values)}`);
}
```

Use facets to understand what metadata fields are available before building filters.
