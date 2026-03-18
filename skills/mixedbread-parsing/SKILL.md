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

Docs: https://www.mixedbread.com/docs/parsing/overview.md
Agent-readable docs: https://www.mixedbread.com/docs/llms.txt
Latest docs search: https://www.mixedbread.com/question?q=parsing&section=docs

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

# Upload and parse a document (waits for completion)
job = mxbai.parsing.jobs.upload_and_poll(
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

const mxbai = new Mixedbread();

const job = await mxbai.parsing.jobs.uploadAndPoll(
    fs.createReadStream('report.pdf'),
    { return_format: 'markdown' },
);

for (const chunk of job.result.chunks) {
    console.log(chunk.content);
}
```

## Decision Tree

- **Which convenience method?**
  - File on disk → `upload_and_poll()` (uploads + creates job + polls)
  - File already uploaded via Files API → `create_and_poll()` (creates job + polls)
  - Need async control → `upload()` or `create()` then `poll()` separately
- **Which parsing mode?**
  - Born-digital PDF (selectable text) → `fast` mode
  - Scanned document or image → `high_quality` mode
- **Need specific elements only?** → Set `element_types` to reduce processing time

## Supported File Types

PDF (`.pdf`), Word (`.doc`, `.docx`, `.dotx`, `.docm`, `.dotm`, `.odt`, `.rtf`), Slides (`.ppt`, `.pptx`, `.ppsx`, `.pptm`, `.potm`, `.ppsm`, `.odp`), Images (`.jpeg`, `.png`, `.webp`, `.avif`).

Element types: `text`, `title`, `section-header`, `header`, `footer`, `page-number`, `list-item`, `figure`, `picture`, `table`, `form`, `footnote`, `caption`, `formula`.

## Workflows

### Extract Tables from Documents

Filter for table elements to pull structured data from reports.

**Python:**
```python
job = mxbai.parsing.jobs.upload_and_poll(
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

**TypeScript:**
```typescript
const job = await mxbai.parsing.jobs.uploadAndPoll(
    fs.createReadStream('financial-report.pdf'),
    { element_types: ['table'], return_format: 'html', mode: 'high_quality' },
);
for (const chunk of job.result.chunks) {
    for (const element of chunk.elements) {
        if (element.type === 'table') {
            console.log(`Page ${element.page}, confidence ${element.confidence.toFixed(2)}`);
            console.log(element.content);
        }
    }
}
```

### Batch Parse Multiple Files

Upload multiple files asynchronously, then poll all jobs:

**Python:**
```python
import os

jobs = []
for filename in os.listdir("./documents"):
    if filename.endswith(".pdf"):
        job = mxbai.parsing.jobs.upload(
            file=open(f"./documents/{filename}", "rb"),
            return_format="markdown",
        )
        jobs.append(job)

# Poll all jobs
for job in jobs:
    completed = mxbai.parsing.jobs.poll(job_id=job.id)
    print(f"{completed.filename}: {len(completed.result.chunks)} chunks")
```

**TypeScript:**
```typescript
import { readdirSync, createReadStream } from 'fs';
import path from 'path';

const files = readdirSync('./documents').filter(f => f.endsWith('.pdf'));
const jobs = await Promise.all(
    files.map(f => mxbai.parsing.jobs.upload(
        createReadStream(path.join('./documents', f)),
        { return_format: 'markdown' },
    )),
);

// Poll all jobs
for (const job of jobs) {
    const completed = await mxbai.parsing.jobs.poll(job.id);
    console.log(`${completed.filename}: ${completed.result.chunks.length} chunks`);
}
```

## Rules

### CRITICAL
- **Don't double-parse.** Store uploads auto-parse documents. If you upload to a Store, do NOT also run the Parsing API on the same file. Use the Parsing API only for standalone document extraction.
- **Use `upload_and_poll()` / `create_and_poll()` instead of manual polling loops.** These methods handle backoff automatically. Manual `while` loops with `retrieve()` are fragile and waste API calls.

### HIGH
- **Specify `element_types` when you only need certain elements.** Requesting all types increases processing time and response size. If you only need tables, set `element_types` to `table` only.
- **Use `fast` mode for born-digital PDFs.** The `high_quality` mode adds OCR overhead that provides no benefit when text is already selectable.
- **Check `confidence` scores on OCR output.** Low-confidence elements (< 0.5) may contain errors. Filter or flag them.

### MEDIUM
- **Check `job.error` before retrying failed jobs.** Common causes: unsupported file type, corrupt file, file too large. Blindly retrying wastes quota.
- **Use `content_to_embed` for embedding pipelines.** Each chunk provides both `content` (full text) and `content_to_embed` (optimized for embedding). Use the latter when feeding into vector stores outside Mixedbread.
- **Verify file format before parsing.** Only PDF, Word, PowerPoint, and images are supported. Convert other formats first.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Job stuck in `pending` | Queue is busy | Use `poll()` with a longer `poll_timeout_ms`. Check job status with `retrieve()`. |
| Job status `failed` | Unsupported file type, corrupt file, or file too large | Check `job.error` for details. Verify file format is supported. |
| Empty chunks in result | File has no extractable content (blank pages) | Verify the file has content. Try `high_quality` mode for scanned documents. |
| Low confidence scores | Scanned or low-resolution source | Use `high_quality` mode for better OCR accuracy. |
| Missing tables or figures | Element types not requested | Set `element_types` to include `table` and `figure` explicitly. |
| `upload_and_poll()` timeout | Very large document or slow processing | Increase `poll_timeout_ms`, or use `upload()` + `poll()` separately for more control. |
