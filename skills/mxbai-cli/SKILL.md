---
name: mxbai-cli
description: >-
  Use the mxbai CLI to manage stores, upload files, search documents, ask questions, and sync directories
  from the terminal. Use when performing Mixedbread operations via command line, setting up CI/CD pipelines
  with store sync, or managing API keys.
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

Get your API key at https://platform.mixedbread.com/platform?next=api-keys

## Quick Command Reference

| Command | Description |
|---------|-------------|
| `mxbai config set api_key <key>` | Save API key to config |
| `mxbai config keys add <key> [name]` | Add a named API key |
| `mxbai config keys list` | List saved API keys |
| `mxbai config keys set-default <name>` | Set default API key |
| `mxbai store create <name>` | Create a new store |
| `mxbai store list` | List all stores |
| `mxbai store get <name>` | Get store details |
| `mxbai store update <name>` | Update store config |
| `mxbai store delete <name>` | Delete a store |
| `mxbai store upload <name> <patterns...>` | Upload files to a store |
| `mxbai store files list <name>` | List files in a store |
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

## Multipart Upload

Files above 5 MB automatically use multipart upload. Tune with these flags:

```bash
mxbai store upload "my-docs" "large-files/**" \
  --multipart-threshold 10 \
  --multipart-part-size 10 \
  --multipart-concurrency 4
```

| Flag | Description |
|------|-------------|
| `--multipart-threshold <mb>` | File size in MB to trigger multipart (minimum 5 MB) |
| `--multipart-part-size <mb>` | Size of each part in MB (minimum 5 MB) |
| `--multipart-concurrency <n>` | Concurrent part uploads (minimum 1) |

These flags also work with `mxbai store sync`.

## File Status Filtering

List files in a store filtered by processing status:

```bash
mxbai store files list "my-docs" --status completed
mxbai store files list "my-docs" --status failed
mxbai store files list "my-docs" --status in_progress
```

Valid status values: `all` (default), `completed`, `in_progress`, `failed`.

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

## API Key Management

```bash
# Add a named API key
mxbai config keys add mxb_xxxxx production

# List all saved keys
mxbai config keys list

# Set the default key
mxbai config keys set-default production

# Remove a key
mxbai config keys remove staging --yes

# Use a saved key for a command
mxbai store list --saved-key production
```

> See [references/config-and-keys.md](references/config-and-keys.md) for full key management docs.

## Store Aliases

Create short aliases for frequently used stores:

```bash
# Set aliases
mxbai config set aliases.docs "my-documentation-store"
mxbai config set aliases.prod "str_abc123"

# Use aliases in any command
mxbai store search docs "how to deploy"
mxbai store upload prod "files/**/*.md"
```

## Configuration Defaults

```bash
# Set default parsing strategy
mxbai config set defaults.upload.strategy high_quality

# Set default parallelism
mxbai config set defaults.upload.parallel 50

# Set default search results count
mxbai config set defaults.search.top_k 20

# Enable reranking by default
mxbai config set defaults.search.rerank true
```

> See [references/config-and-keys.md](references/config-and-keys.md) for all configuration options.

## Contextualization Deprecation

> **Note:** The `--contextualization` flag on `upload` and `sync` commands is **deprecated** since v2.2.0. Contextualization is now configured at store creation time using `mxbai store create --contextualization`. Using the deprecated flag will show a warning and be ignored.

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

## Anti-Patterns

- **Don't use `--contextualization` on upload or sync.** It's deprecated. Configure contextualization at store creation with `mxbai store create --contextualization`.
- **Don't use `--force` sync in CI unless you intend full re-upload.** Force bypasses change detection and re-uploads everything.
- **Don't set `--parallel` above 200.** The CLI validates and rejects values above 200.
- **Don't forget `--yes` in CI/CD.** Without it, sync and delete commands hang waiting for interactive confirmation.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Command not found" | Verify Node.js >= 20 is installed. Try `npx mxbai` for project-local installs. |
| "No API key" | Run `mxbai config keys add <key>` or set `MXBAI_API_KEY` env var. |
| Upload timeout for large files | Tune multipart flags: `--multipart-threshold`, `--multipart-part-size`, `--multipart-concurrency`. |
| Sync hangs in CI | Must pass `--yes` for non-interactive mode. CI environments don't have a TTY. |
| Store not found | Check aliases with `mxbai config get aliases`. Verify store name uses valid characters (lowercase, numbers, hyphens, periods). |
| Contextualization warning | The `--contextualization` flag on upload/sync is deprecated. Set it at store creation instead. |

## References

| Topic | Reference |
|-------|-----------|
| Store creation, update, deletion | [references/store-management.md](references/store-management.md) |
| File upload, manifests, and multipart | [references/file-operations.md](references/file-operations.md) |
| Search and question answering | [references/search-and-qa.md](references/search-and-qa.md) |
| Sync and CI/CD workflows | [references/sync.md](references/sync.md) |
| API keys, defaults, and aliases | [references/config-and-keys.md](references/config-and-keys.md) |
