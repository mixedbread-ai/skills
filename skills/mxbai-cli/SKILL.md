---
name: mxbai-cli
description: Use the mxbai CLI to manage stores, upload files, search documents, ask questions, and sync directories. Activate when the user needs to perform Mixedbread operations from the terminal, set up CI/CD pipelines, or manage API keys.
---

# mxbai CLI

The `mxbai` CLI manages stores, uploads files, performs semantic search, and syncs directories with Mixedbread from the terminal.

## Installation

```bash
npm install -g @mixedbread/cli    # global
npm install --save-dev @mixedbread/cli  # project-local (use npx mxbai)
```

Requires Node.js >= 20.0. Verify with `mxbai --version`.

## Authentication

Resolved in priority order:

1. **Flag:** `--api-key mxb_xxxxx` or `--saved-key <name>`
2. **Environment variable:** `export MXBAI_API_KEY=mxb_xxxxx`
3. **Config file:** `mxbai config set api_key mxb_xxxxx`

Get your API key at https://platform.mixedbread.com

## Quick Command Reference

| Command | Description |
|---------|-------------|
| `mxbai config set api_key <key>` | Save API key to config |
| `mxbai store create <name>` | Create a new store |
| `mxbai store list` | List all stores |
| `mxbai store get <name>` | Get store details |
| `mxbai store update <name>` | Update store config |
| `mxbai store delete <name>` | Delete a store |
| `mxbai store upload <name> <patterns...>` | Upload files to a store |
| `mxbai store search <name> <query>` | Semantic search |
| `mxbai store qa <name> <question>` | Question answering |
| `mxbai store sync <name> <patterns...>` | Sync changed files |

## Store Management

```bash
# Create a store with metadata contextualization
mxbai store create "my-docs" \
  --description "Product documentation" \
  --contextualization title,author \
  --metadata '{"team": "engineering"}'

# Create a public store with auto-expiration
mxbai store create "temp-store" --public --expires-after 30

# List and filter stores
mxbai store list --filter "docs"

# Update a store
mxbai store update "my-docs" --description "Updated description"

# Delete (with confirmation bypass)
mxbai store delete "my-docs" --yes
```

Store names: lowercase letters, numbers, periods, and hyphens only.

> See [references/store-management.md](references/store-management.md) for all options.

## File Upload

```bash
# Upload files matching glob patterns
mxbai store upload "my-docs" "docs/**/*.md" "guides/*.pdf"

# High-quality processing with metadata
mxbai store upload "my-docs" "./reports/" \
  --strategy high_quality \
  --metadata '{"category": "reports"}' \
  --parallel 50

# Preview what would be uploaded
mxbai store upload "my-docs" "**/*.md" --dry-run

# Replace existing files instead of duplicating
mxbai store upload "my-docs" "**/*.md" --unique

# Use a manifest file for complex uploads
mxbai store upload "my-docs" --manifest upload.yaml
```

> See [references/file-operations.md](references/file-operations.md) for manifest format and all flags.

## Search

```bash
# Basic semantic search
mxbai store search "my-docs" "How does authentication work?"

# Search with reranking and metadata
mxbai store search "my-docs" "deployment guide" \
  --top-k 20 \
  --rerank \
  --return-metadata \
  --threshold 0.5

# File-level search (instead of chunk-level)
mxbai store search "my-docs" "API reference" --file-search
```

> See [references/search-and-qa.md](references/search-and-qa.md) for all search options.

## Question Answering

```bash
# Ask a question and get an AI-generated answer with sources
mxbai store qa "my-docs" "What are the rate limits?" \
  --top-k 15 \
  --return-metadata
```

## Sync

Uploads only changed files since the last sync. Ideal for CI/CD pipelines.

```bash
# Sync using git-based change detection
mxbai store sync "my-docs" "docs/**" --from-git HEAD~1

# Preview changes before syncing
mxbai store sync "my-docs" "docs/**" --dry-run

# Force re-upload all files
mxbai store sync "my-docs" "**/*.md" --force

# CI/CD pipeline (non-interactive)
mxbai store sync "my-docs" "docs/**" --yes --from-git HEAD~1
```

> See [references/sync.md](references/sync.md) for change detection methods and CI/CD patterns.

## Global Options

| Flag | Description |
|------|-------------|
| `--api-key <key>` | API key for this command |
| `--saved-key <name>` | Use a saved API key by name |
| `--base-url <url>` | Custom API base URL |
| `--format <fmt>` | Output format: `table`, `json`, `csv` |
| `--debug` | Enable debug output |
| `--help` | Show help |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MXBAI_API_KEY` | Default API key |
| `MXBAI_BASE_URL` | Custom API base URL |
| `MXBAI_DEBUG` | Enable debug mode |
| `MXBAI_CONFIG_PATH` | Custom config file path |

## Shell Completion

```bash
mxbai completion install           # Auto-detect and install
mxbai completion install --shell zsh  # Specific shell
mxbai completion refresh           # Refresh cache
```

## References

| Topic | Reference |
|-------|-----------|
| Store creation, update, deletion | [references/store-management.md](references/store-management.md) |
| File upload and manifests | [references/file-operations.md](references/file-operations.md) |
| Search and question answering | [references/search-and-qa.md](references/search-and-qa.md) |
| Sync and CI/CD workflows | [references/sync.md](references/sync.md) |
