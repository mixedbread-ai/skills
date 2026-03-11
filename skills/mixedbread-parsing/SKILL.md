---
name: mixedbread-parsing
description: >-
  Parse documents, extract structured content, and run OCR using the Mixedbread Parsing API.
  Use when parsing PDFs, Word documents, PowerPoint slides, or images, extracting tables or form fields,
  running OCR on scanned documents, converting documents to markdown or HTML, or extracting
  structured chunks with element-level bounding boxes and confidence scores.
---

# Mixedbread Parsing

Parse documents, extract structured content, and run OCR using the Parsing API. Supports PDFs, Word documents, PowerPoint presentations, and images.

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

# Upload and parse a document (waits for completion)
job = client.parsing.jobs.upload_and_poll(
    file=open("report.pdf", "rb"),
    return_format="markdown",
)

for chunk in job.result.chunks:
    print(chunk.content)
```

**TypeScript:**
```typescript
import Mixedbread from '@mixedbread/sdk';
import fs from 'fs';

const client = new Mixedbread();

const job = await client.parsing.jobs.uploadAndPoll(
    fs.createReadStream('report.pdf'),
    { return_format: 'markdown' },
);

for (const chunk of job.result.chunks) {
    console.log(chunk.content);
}
```

## Parsing API

| Operation | Python | TypeScript |
|-----------|--------|------------|
| Create job | `client.parsing.jobs.create(file_id=...)` | `client.parsing.jobs.create({ file_id })` |
| Upload + create | `client.parsing.jobs.upload(file=...)` | `client.parsing.jobs.upload(file, {...})` |
| Upload + poll | `client.parsing.jobs.upload_and_poll(file=...)` | `client.parsing.jobs.uploadAndPoll(file, {...})` |
| Create + poll | `client.parsing.jobs.create_and_poll(file_id=...)` | `client.parsing.jobs.createAndPoll({ file_id })` |
| Poll job | `client.parsing.jobs.poll(job_id=...)` | `client.parsing.jobs.poll(jobId)` |
| Retrieve job | `client.parsing.jobs.retrieve(job_id=...)` | `client.parsing.jobs.retrieve(jobId)` |
| List jobs | `client.parsing.jobs.list()` | `client.parsing.jobs.list()` |
| Cancel job | `client.parsing.jobs.cancel(job_id=...)` | `client.parsing.jobs.cancel(jobId)` |
| Delete job | `client.parsing.jobs.delete(job_id=...)` | `client.parsing.jobs.delete(jobId)` |

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_id` | string | — | ID of a previously uploaded file (required for `create`) |
| `element_types` | ElementType[] | all | Which element types to extract |
| `chunking_strategy` | string | `"page"` | How to chunk the document. Currently only `"page"` |
| `return_format` | string | `"markdown"` | Output format: `"html"`, `"markdown"`, or `"plain"` |
| `mode` | string | `"high_quality"` | OCR mode: `"fast"` or `"high_quality"` |

## Supported File Types

| Category | Formats |
|----------|---------|
| PDF | `.pdf` |
| Word | `.doc`, `.docx`, `.dotx`, `.docm`, `.dotm`, `.odt`, `.rtf` |
| Slides | `.ppt`, `.pptx`, `.ppsx`, `.pptm`, `.potm`, `.ppsm`, `.odp` |
| Images | `.jpeg`, `.png`, `.webp`, `.avif` |

## Element Types

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

## Response Structure

```
ParsingJob
  ├── id, file_id, filename, status
  ├── error (if failed)
  └── result (DocumentParserResult)
       ├── chunking_strategy, return_format, element_types
       ├── page_sizes: [[width, height], ...]
       └── chunks[]
            ├── content (full chunk text)
            ├── content_to_embed (optimized for embedding)
            └── elements[]
                 ├── type (ElementType)
                 ├── confidence (0.0–1.0)
                 ├── bbox [x1, y1, x2, y2]
                 ├── page (page number)
                 ├── content (element text)
                 ├── summary (optional brief summary)
                 └── image (optional base64 for figures)
```

Job statuses: `pending` → `in_progress` → `completed` | `failed` | `cancelled`

## Parsing with Specific Elements

```python
job = client.parsing.jobs.upload_and_poll(
    file=open("report.pdf", "rb"),
    element_types=["table", "figure", "text"],
    return_format="html",
    mode="high_quality",
)

for chunk in job.result.chunks:
    for element in chunk.elements:
        print(f"[{element.type}] confidence={element.confidence:.2f} page={element.page}")
        print(element.content[:200])
```

## Two-Step Workflow (Upload Then Parse)

```python
# Step 1: Upload file
file_obj = client.files.create(file=open("slides.pptx", "rb"))

# Step 2: Create parsing job and poll
job = client.parsing.jobs.create_and_poll(
    file_id=file_obj.id,
    return_format="markdown",
)
```

## Anti-Patterns

- **Don't re-parse files already in a Store.** Store upload handles parsing automatically. Use the Parsing API only for standalone document extraction.
- **Don't tight-loop poll.** Use `upload_and_poll()` / `create_and_poll()` or `poll()` which handle backoff automatically. Manual polling should use `poll_interval_ms`.
- **Don't use `high_quality` mode for plain text files.** It adds OCR overhead with no benefit. Use `fast` for non-scanned documents.
- **Don't request all element types when you only need a few.** Specify `element_types` to reduce processing time and response size.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Job stuck in `pending` | The queue may be busy. Use `poll()` with a longer `poll_timeout_ms`. Check job status with `retrieve()`. |
| Job status `failed` | Check `job.error` for details. Common causes: unsupported file type, corrupt file, file too large. |
| Empty chunks in result | Verify the file has extractable content (not a blank page). Try `mode="high_quality"` for scanned documents. |
| Unsupported file type | Parsing supports PDF, Word, PowerPoint, and images (JPEG, PNG, WebP, AVIF). Convert other formats first. |
| Low confidence scores | Use `mode="high_quality"` for better OCR accuracy on scanned or low-resolution documents. |

## References

| Topic | Reference |
|-------|-----------|
| Parsing API endpoints and response models | [references/parsing-api.md](references/parsing-api.md) |
