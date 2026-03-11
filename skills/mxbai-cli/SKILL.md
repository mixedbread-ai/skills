---
name: mxbai-cli
description: >-
  Use the mxbai CLI to manage stores, upload files, search documents, ask questions, and sync directories
  from the terminal. Use when performing Mixedbread operations via command line, setting up CI/CD pipelines
  with store sync, or managing API keys.
---

# mxbai CLI

The `mxbai` CLI manages stores, uploads files, performs semantic search, and syncs directories with Mixedbread from the terminal.

Docs: https://www.mixedbread.com/cli.md

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

## Quick Start

```bash
# Create a store and upload docs
mxbai store create "my-docs" --description "Product documentation"
mxbai store upload "my-docs" "docs/**/*.md"

# Search
mxbai store search "my-docs" "How does authentication work?"

# Sync changed files (hash-based detection by default)
mxbai store sync "my-docs" "docs/**"
```

## Decision Tree

- **Upload vs Sync?**
  - One-time or manual upload → `mxbai store upload`
  - Ongoing updates (especially CI/CD) → `mxbai store sync`
- **Which change detection for sync?**
  - In a git repo with known base commit → `--from-git HEAD~1` (fastest)
  - Outside git or need exact comparison → hash-based detection (default, compares content hashes)
- **CLI vs SDK?**
  - Shell scripts, CI/CD, one-off tasks → CLI
  - Application code, custom logic, programmatic access → Python/TypeScript SDK

## Workflows

### CI/CD Documentation Sync

Sync documentation to a store on every push using the default hash-based change detection.

**GitHub Actions:**
```yaml
name: Sync Documentation
on:
  push:
    branches: [main]
    paths:
      - 'docs/**'

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install mxbai CLI
        run: npm install -g @mixedbread/cli

      - name: Sync docs to store
        env:
          MXBAI_API_KEY: ${{ secrets.MXBAI_API_KEY }}
        run: |
          mxbai store sync my-docs "docs/**/*.md" \
            --strategy high_quality \
            --yes
```

For faster change detection in git repos, add `--from-git HEAD~1` (requires `fetch-depth: 2`) or `--from-git origin/main` (requires `fetch-depth: 0`).

**Key points:**
- Always pass `--yes` — CI environments are non-interactive and commands hang without it
- Use `--from-git` for faster change detection in git repos
- Store the API key as a secret via `MXBAI_API_KEY`
- Use `--dry-run` in a separate step to preview changes before applying

**Preview before syncing:**
```bash
mxbai store sync "my-docs" "docs/**" --dry-run
```

### Multi-Environment Setup

Manage separate API keys for staging and production.

```bash
# Add keys for different environments
mxbai config keys add mxb_xxxxx production
mxbai config keys add mxb_xxxxx staging

# Set production as default
mxbai config keys set-default production

# Use staging for a specific command
mxbai store search staging-docs "query" --saved-key staging
```

### Upload with Manifest

Use a manifest file for complex uploads with per-file metadata and strategy overrides.

```yaml
# upload-manifest.yaml
version: "1"
defaults:
  strategy: fast
  metadata:
    team: engineering
files:
  - path: docs/getting-started.md
    metadata:
      title: Getting Started Guide
      priority: high
  - path: docs/api-reference.md
    strategy: high_quality
    metadata:
      title: API Reference
  - path: reports/*.pdf
    metadata:
      category: reports
```

```bash
mxbai store upload "my-docs" --manifest upload-manifest.yaml
```

### Store Aliases

Create short aliases for frequently used stores:

```bash
mxbai config set aliases.docs "my-documentation-store"
mxbai config set aliases.prod "str_abc123"

# Use aliases in any command
mxbai store search docs "how to deploy"
mxbai store upload prod "files/**/*.md"
```

## Rules

### CRITICAL
- **Always pass `--yes` in CI/CD.** Without it, sync and delete commands hang waiting for interactive confirmation that never comes. CI environments don't have a TTY.
- **`--contextualization` on upload/sync is deprecated since v2.2.0.** Configure contextualization at store creation with `mxbai store create --contextualization`. The flag on upload/sync shows a warning and is ignored.

### HIGH
- **`--parallel` max is 200.** The CLI validates and rejects values above 200. Default is 100.
- **`--force` sync re-uploads everything.** It bypasses change detection entirely. Use sparingly — typically only for periodic full re-syncs (e.g., weekly cron).
- **Store names: lowercase letters, numbers, hyphens, and periods only.** Invalid names cause creation to fail.

### MEDIUM
- **Use `--dry-run` before first sync.** Preview what would be uploaded, changed, or deleted before committing.
- **Use store aliases for frequently-used stores.** Avoids typos and long store names in commands.
- **Use `--unique` on upload to skip duplicates.** Prevents re-uploading files that already exist (based on content hash).

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Command not found" | Node.js < 20 or not globally installed | Verify Node.js >= 20. Try `npx mxbai` for project-local installs. |
| "No API key" | No key configured | Run `mxbai config keys add <key>` or set `MXBAI_API_KEY` env var. |
| Sync hangs in CI | Missing `--yes` flag | Pass `--yes` for non-interactive mode. |
| Upload timeout for large files | Default multipart settings insufficient | Tune `--multipart-threshold`, `--multipart-part-size`, `--multipart-concurrency`. |
| Store not found | Wrong name or alias | Check aliases with `mxbai config get aliases`. Verify name uses valid characters. |
| Contextualization warning | Deprecated flag on upload/sync | Set contextualization at store creation instead. |
| Sync detects no changes | Hash-based detection with modified metadata only | Use `--force` to re-upload, or `--from-git` to detect changes via git. |
| `--from-git` misses files | `fetch-depth` too shallow in CI | Set `fetch-depth: 0` for full history, or `fetch-depth: 2` minimum for `HEAD~1`. |
