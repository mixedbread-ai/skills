# Stores API

CRUD operations for managing Stores -- managed multimodal search indexes.

Base URL: `https://api.mixedbread.com`

## Endpoints

### Create a Store

```
POST /v1/stores
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | No | Unique name. Lowercase letters, numbers, hyphens, and periods only. |
| `description` | string | No | Human-readable description of the store. |
| `is_public` | boolean | No | If `true`, anyone with a valid API key can search this store. Default `false`. |
| `expires_after` | object | No | Auto-expiration policy. `{anchor: "last_active_at", days: <int>}`. |
| `metadata` | object | No | Arbitrary key-value metadata (string keys, JSON values). |
| `config` | object | No | Store configuration (see below). |
| `file_ids` | string[] | No | File IDs to add to the store on creation. |

**Config object:**

| Field | Type | Description |
|-------|------|-------------|
| `contextualization` | bool \| object | Include metadata in embeddings. `true` for all metadata, or `{with_metadata: bool \| string[]}` to specify fields. |
| `save_content` | bool | Store original file content. Default `true`. Set `false` for index-only mode (disables reranking). |

**Python:**
```python
from mixedbread import Mixedbread

client = Mixedbread()  # uses MXBAI_API_KEY env var

store = client.stores.create(
    name="product-docs",
    description="Product documentation and guides",
    is_public=False,
    expires_after={"anchor": "last_active_at", "days": 90},
    metadata={"team": "engineering", "version": "2.0"},
    config={
        "contextualization": {"with_metadata": ["title", "category"]},
        "save_content": True,
    },
)
print(store.id, store.name, store.status)
```

**TypeScript:**
```typescript
import Mixedbread from '@mixedbread/sdk';

const client = new Mixedbread(); // uses MXBAI_API_KEY env var

const store = await client.stores.create({
    name: 'product-docs',
    description: 'Product documentation and guides',
    is_public: false,
    expires_after: { anchor: 'last_active_at', days: 90 },
    metadata: { team: 'engineering', version: '2.0' },
    config: {
        contextualization: { with_metadata: ['title', 'category'] },
        save_content: true,
    },
});
console.log(store.id, store.name, store.status);
```

### Retrieve a Store

```
GET /v1/stores/{store_identifier}
```

`store_identifier` can be the store ID or the store name.

**Python:**
```python
store = client.stores.retrieve("product-docs")
# or by ID
store = client.stores.retrieve("store_abc123")

print(store.name)
print(store.status)            # "expired" | "in_progress" | "completed"
print(store.file_counts.total)
print(store.usage_bytes)
```

**TypeScript:**
```typescript
const store = await client.stores.retrieve('product-docs');

console.log(store.name);
console.log(store.status);
console.log(store.file_counts.total);
console.log(store.usage_bytes);
```

### Update a Store

```
PUT /v1/stores/{store_identifier}
```

Accepts the same parameters as create. Only provided fields are updated.

**Python:**
```python
store = client.stores.update(
    "product-docs",
    description="Updated product docs for v3",
    metadata={"team": "engineering", "version": "3.0"},
    config={"contextualization": True},
)
```

**TypeScript:**
```typescript
const store = await client.stores.update('product-docs', {
    description: 'Updated product docs for v3',
    metadata: { team: 'engineering', version: '3.0' },
    config: { contextualization: true },
});
```

### List Stores

```
GET /v1/stores
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Maximum number of stores to return. |
| `order` | string | Sort order (`"asc"` or `"desc"`). |
| `after` | string | Cursor for forward pagination. |
| `before` | string | Cursor for backward pagination. |

**Python:**
```python
stores = client.stores.list(limit=20, order="desc")
for store in stores.data:
    print(f"{store.name}: {store.status} ({store.file_counts.total} files)")
```

**TypeScript:**
```typescript
const stores = await client.stores.list({ limit: 20, order: 'desc' });
for (const store of stores.data) {
    console.log(`${store.name}: ${store.status} (${store.file_counts.total} files)`);
}
```

### Delete a Store

```
DELETE /v1/stores/{store_identifier}
```

**Python:**
```python
client.stores.delete("product-docs")
```

**TypeScript:**
```typescript
await client.stores.delete('product-docs');
```

## Response Type: Store

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique store identifier. |
| `name` | string | Store name. |
| `description` | string | Store description. |
| `is_public` | boolean | Whether the store is publicly searchable. |
| `metadata` | object | Arbitrary key-value metadata. |
| `config` | object | Store configuration (contextualization, save_content). |
| `file_counts` | object | `{pending, in_progress, cancelled, completed, failed, total}` |
| `expires_after` | object | Expiration policy. |
| `status` | string | `"expired"`, `"in_progress"`, or `"completed"`. |
| `created_at` | string | ISO 8601 timestamp. |
| `updated_at` | string | ISO 8601 timestamp. |
| `last_active_at` | string | ISO 8601 timestamp. |
| `usage_bytes` | int | Storage usage in bytes. |
| `usage_tokens` | int | Token usage. |
| `expires_at` | string | ISO 8601 timestamp of when the store will expire. |
| `object` | string | Always `"store"`. |

## Async Usage (Python)

```python
from mixedbread import AsyncMixedbread

client = AsyncMixedbread()

store = await client.stores.create(
    name="async-store",
    description="Created asynchronously",
)
stores = await client.stores.list(limit=10)
```
