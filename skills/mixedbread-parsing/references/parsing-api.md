# Parsing API

Parse documents, extract structured content, and run OCR. The Parsing API processes files asynchronously via jobs.

Base URL: `https://api.mixedbread.com`

## Endpoints

### Create a Parsing Job

```
POST /v1/parsing/jobs
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_id` | string | Yes | — | ID of a previously uploaded file. |
| `element_types` | ElementType[] | No | all | Element types to extract. |
| `chunking_strategy` | string | No | `"page"` | Chunking strategy. Currently only `"page"`. |
| `return_format` | string | No | `"markdown"` | Output format: `"html"`, `"markdown"`, or `"plain"`. |
| `mode` | string | No | `"high_quality"` | OCR mode: `"fast"` or `"high_quality"`. |

**Python:**
```python
from mixedbread import Mixedbread

client = Mixedbread()

# First upload a file
file_obj = client.files.create(file=open("report.pdf", "rb"))

# Then create a parsing job
job = client.parsing.jobs.create(
    file_id=file_obj.id,
    element_types=["text", "table", "figure"],
    return_format="markdown",
    mode="high_quality",
)
print(job.id, job.status)  # "pending"
```

**TypeScript:**
```typescript
import Mixedbread from '@mixedbread/sdk';
import fs from 'fs';

const client = new Mixedbread();

const fileObj = await client.files.create({ file: fs.createReadStream('report.pdf') });

const job = await client.parsing.jobs.create({
    file_id: fileObj.id,
    element_types: ['text', 'table', 'figure'],
    return_format: 'markdown',
    mode: 'high_quality',
});
console.log(job.id, job.status); // "pending"
```

### Retrieve a Parsing Job

```
GET /v1/parsing/jobs/{job_id}
```

**Python:**
```python
job = client.parsing.jobs.retrieve("job_abc123")
print(job.status)  # "pending" | "in_progress" | "completed" | "failed" | "cancelled"
if job.status == "completed":
    for chunk in job.result.chunks:
        print(chunk.content[:100])
```

**TypeScript:**
```typescript
const job = await client.parsing.jobs.retrieve('job_abc123');
if (job.status === 'completed') {
    for (const chunk of job.result.chunks) {
        console.log(chunk.content?.slice(0, 100));
    }
}
```

### List Parsing Jobs

```
GET /v1/parsing/jobs
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Max items per page (1–100, default 20). |
| `offset` | int | Offset for pagination. |

**Python:**
```python
jobs = client.parsing.jobs.list(limit=20)
for job in jobs.data:
    print(f"{job.id}: {job.status} — {job.filename}")
```

**TypeScript:**
```typescript
const jobs = await client.parsing.jobs.list({ limit: 20 });
for (const job of jobs.data) {
    console.log(`${job.id}: ${job.status} — ${job.filename}`);
}
```

### Cancel a Parsing Job

```
PATCH /v1/parsing/jobs/{job_id}
```

**Python:**
```python
job = client.parsing.jobs.cancel("job_abc123")
print(job.status)  # "cancelled"
```

**TypeScript:**
```typescript
const job = await client.parsing.jobs.cancel('job_abc123');
console.log(job.status); // "cancelled"
```

### Delete a Parsing Job

```
DELETE /v1/parsing/jobs/{job_id}
```

**Python:**
```python
result = client.parsing.jobs.delete("job_abc123")
print(result.deleted)  # True
```

**TypeScript:**
```typescript
const result = await client.parsing.jobs.delete('job_abc123');
console.log(result.deleted); // true
```

---

## Convenience Methods

### Upload and Create Job

Uploads a file and creates a parsing job in one call. The job is processed asynchronously.

**Python:**
```python
job = client.parsing.jobs.upload(
    file=open("document.pdf", "rb"),
    return_format="markdown",
    mode="high_quality",
)
print(job.id, job.status)  # job is processing asynchronously
```

**TypeScript:**
```typescript
const job = await client.parsing.jobs.upload(
    fs.createReadStream('document.pdf'),
    { return_format: 'markdown', mode: 'high_quality' },
);
```

### Upload and Poll (Recommended)

Uploads a file, creates a job, and polls until completion. This is the simplest way to parse a document.

**Python:**
```python
job = client.parsing.jobs.upload_and_poll(
    file=open("document.pdf", "rb"),
    return_format="markdown",
    element_types=["text", "table", "figure"],
    poll_interval_ms=500,
)
# job.status is "completed", "failed", or "cancelled"
for chunk in job.result.chunks:
    print(chunk.content)
```

**TypeScript:**
```typescript
const job = await client.parsing.jobs.uploadAndPoll(
    fs.createReadStream('document.pdf'),
    { return_format: 'markdown', element_types: ['text', 'table', 'figure'] },
    500, // pollIntervalMs
);
for (const chunk of job.result.chunks) {
    console.log(chunk.content);
}
```

### Create and Poll

Creates a job for an already-uploaded file and polls until completion.

**Python:**
```python
job = client.parsing.jobs.create_and_poll(
    file_id="file_abc123",
    return_format="html",
    poll_interval_ms=500,
    poll_timeout_ms=60000,
)
```

**TypeScript:**
```typescript
const job = await client.parsing.jobs.createAndPoll(
    { file_id: 'file_abc123', return_format: 'html' },
    500, // pollIntervalMs
    60000, // pollTimeoutMs
);
```

### Poll an Existing Job

Polls a job until it reaches a terminal state (`completed`, `failed`, or `cancelled`).

**Python:**
```python
job = client.parsing.jobs.poll(
    job_id="job_abc123",
    poll_interval_ms=500,
    poll_timeout_ms=120000,
)
```

**TypeScript:**
```typescript
const job = await client.parsing.jobs.poll('job_abc123', 500, 120000);
```

---

## Response Models

### ParsingJob

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Job ID. |
| `file_id` | string | Source file ID. |
| `filename` | string \| null | Source filename. |
| `status` | string | `"pending"`, `"in_progress"`, `"completed"`, `"failed"`, or `"cancelled"`. |
| `error` | object \| null | Error details if status is `"failed"`. |
| `result` | DocumentParserResult \| null | Parsing result (only when `"completed"`). |
| `started_at` | string \| null | ISO 8601 timestamp. |
| `finished_at` | string \| null | ISO 8601 timestamp. |
| `created_at` | string \| null | ISO 8601 timestamp. |
| `updated_at` | string \| null | ISO 8601 timestamp. |
| `object` | string | Always `"parsing_job"`. |

### DocumentParserResult

| Field | Type | Description |
|-------|------|-------------|
| `chunking_strategy` | string | Strategy used (`"page"`). |
| `return_format` | string | Format used (`"html"`, `"markdown"`, or `"plain"`). |
| `element_types` | string[] | Element types that were extracted. |
| `chunks` | Chunk[] | Extracted chunks. |
| `page_sizes` | int[][] \| null | List of `[width, height]` per page. |

### Chunk

| Field | Type | Description |
|-------|------|-------------|
| `content` | string \| null | Full content of the chunk. |
| `content_to_embed` | string | Content optimized for embedding. |
| `elements` | ChunkElement[] | Elements within this chunk. |

### ChunkElement

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Element type (see Element Types). |
| `confidence` | float | Detection confidence (0.0–1.0). |
| `bbox` | float[4] | Bounding box `[x1, y1, x2, y2]`. |
| `page` | int | Page number (0-indexed). |
| `content` | string | Full content of the element. |
| `summary` | string \| null | Brief summary of element content. |
| `image` | string \| null | Base64-encoded image data (for figures/pictures). |

### Element Types

| Type | Description |
|------|-------------|
| `text` | Regular text content |
| `title` | Document titles |
| `section-header` | Section headers |
| `header` | Page headers |
| `footer` | Page footers |
| `page-number` | Page numbers |
| `list-item` | Items in lists |
| `figure` | Figures and images |
| `picture` | Pictures and photos |
| `table` | Tables |
| `form` | Form elements |
| `footnote` | Footnotes |
| `caption` | Image/table captions |
| `formula` | Mathematical formulas |

---

## Async Usage (Python)

```python
from mixedbread import AsyncMixedbread

client = AsyncMixedbread()

job = await client.parsing.jobs.upload_and_poll(
    file=open("document.pdf", "rb"),
    return_format="markdown",
)
for chunk in job.result.chunks:
    print(chunk.content)
```

## Common Patterns

### Extract Tables Only

```python
job = client.parsing.jobs.upload_and_poll(
    file=open("financial-report.pdf", "rb"),
    element_types=["table"],
    return_format="html",
    mode="high_quality",
)
for chunk in job.result.chunks:
    for element in chunk.elements:
        if element.type == "table":
            print(f"Page {element.page}, confidence {element.confidence:.2f}")
            print(element.content)
```

### Parse and Feed into a Store

```python
# Parse a document for inspection
job = client.parsing.jobs.upload_and_poll(
    file=open("manual.pdf", "rb"),
    return_format="markdown",
)

# If the content looks good, upload to a store for search
# Note: Store upload handles parsing automatically — no need to re-parse
client.stores.files.upload(
    store_identifier="my-docs",
    file=open("manual.pdf", "rb"),
)
```

### Batch Parse Multiple Files

```python
import os

jobs = []
for filename in os.listdir("./documents"):
    if filename.endswith(".pdf"):
        job = client.parsing.jobs.upload(
            file=open(f"./documents/{filename}", "rb"),
            return_format="markdown",
        )
        jobs.append(job)

# Poll all jobs
for job in jobs:
    completed = client.parsing.jobs.poll(job_id=job.id)
    print(f"{completed.filename}: {len(completed.result.chunks)} chunks")
```
