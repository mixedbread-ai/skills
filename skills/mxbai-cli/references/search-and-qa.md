# Search and Question Answering

Query a store using semantic search or ask questions with retrieval-augmented answers.

## Search

```
mxbai store search <name-or-id> <query>
```

Performs semantic search across all files in a store and returns the most relevant chunks.

| Flag | Description |
|------|-------------|
| `--top-k` | Number of results to return (1-100). Default: `10` |
| `--threshold` | Minimum similarity score (0.0-1.0). Results below this score are excluded |
| `--return-metadata` | Include file and chunk metadata in the results |
| `--rerank` | Re-rank results using a cross-encoder model for improved relevance |
| `--file-search` | Search at the file level rather than the chunk level |

**Note:** Default values for `--top-k` and `--rerank` can be configured globally using `mxbai config`.

### Examples

Basic search:

```bash
mxbai store search my-docs "how to authenticate with the API"
```

Search with more results and a similarity threshold:

```bash
mxbai store search my-docs "rate limiting" --top-k 25 --threshold 0.5
```

Search with reranking for higher relevance:

```bash
mxbai store search my-docs "error handling best practices" --rerank
```

Search with metadata in the output:

```bash
mxbai store search my-docs "deployment steps" --return-metadata
```

File-level search:

```bash
mxbai store search my-docs "kubernetes configuration" --file-search
```

Combine multiple flags:

```bash
mxbai store search my-docs "database migrations" \
  --top-k 20 \
  --threshold 0.6 \
  --rerank \
  --return-metadata
```

### Output Format

By default, results are displayed as a table:

```
 #  Score   Content
 1  0.92    To authenticate, include your API key in the Authorization header...
 2  0.87    All API requests must be authenticated using a Bearer token...
 3  0.81    You can generate API keys from the dashboard under Settings...
```

With `--return-metadata`, additional columns are included:

```
 #  Score   File                    Content
 1  0.92    docs/auth.md            To authenticate, include your API key in the Authorization header...
 2  0.87    docs/quickstart.md      All API requests must be authenticated using a Bearer token...
 3  0.81    docs/settings.md        You can generate API keys from the dashboard under Settings...
```

JSON output is available through the global `--output json` flag:

```bash
mxbai store search my-docs "authentication" --return-metadata --output json
```

```json
{
  "results": [
    {
      "score": 0.92,
      "content": "To authenticate, include your API key in the Authorization header...",
      "metadata": {
        "file_id": "file_abc123",
        "file_name": "docs/auth.md",
        "chunk_index": 3
      }
    }
  ]
}
```

## Question Answering

```
mxbai store qa <name-or-id> <question>
```

Retrieves relevant context from the store and generates a natural-language answer to the question.

| Flag | Description |
|------|-------------|
| `--top-k` | Number of context chunks to retrieve (affects answer quality). Default: `10` |
| `--threshold` | Minimum similarity score for context chunks (0.0-1.0) |
| `--return-metadata` | Include source references in the output |

### Examples

Ask a question:

```bash
mxbai store qa my-docs "What authentication methods are supported?"
```

Ask with more context for a detailed answer:

```bash
mxbai store qa my-docs "How do I set up CI/CD?" --top-k 25
```

Ask with source references:

```bash
mxbai store qa my-docs "What are the rate limits?" --return-metadata
```

Filter low-relevance context:

```bash
mxbai store qa my-docs "How do backups work?" --threshold 0.5
```

### Output Format

By default, QA returns a plain-text answer:

```
Based on the documentation, the API supports three authentication methods:

1. API Key - passed via the Authorization header as a Bearer token
2. OAuth 2.0 - using the standard authorization code flow
3. Service accounts - for server-to-server communication

API keys can be generated from the dashboard under Settings > API Keys.
```

With `--return-metadata`, source references are appended:

```
Based on the documentation, the API supports three authentication methods:
...

Sources:
  - docs/auth.md (score: 0.92)
  - docs/quickstart.md (score: 0.87)
  - docs/settings.md (score: 0.81)
```

## Configuring Defaults

Use `mxbai config` to set default values so you do not need to pass them on every command:

```bash
# Set default top-k for search and QA
mxbai config set default_top_k 20

# Enable reranking by default for search
mxbai config set default_rerank true
```

These defaults are overridden by any flags passed directly on the command line.

## Common Patterns

Search, inspect, then ask a targeted question:

```bash
# Broad search to understand what is in the store
mxbai store search my-docs "authentication" --top-k 5

# Follow up with a specific question
mxbai store qa my-docs "What is the token expiration policy for OAuth tokens?"
```

Use file-level search to find relevant documents, then search within:

```bash
# Find which files discuss the topic
mxbai store search my-docs "error codes" --file-search --top-k 5

# Then do a detailed chunk-level search
mxbai store search my-docs "HTTP 429 rate limit error" --top-k 20 --rerank
```
