# File Operations

Upload files to a store.

## Upload Files

```
mxbai store upload <name-or-id> <patterns...>
```

Uploads files matching the given glob patterns into a store. Patterns follow standard glob syntax (e.g., `*.pdf`, `docs/**/*.md`).

| Flag | Description |
|------|-------------|
| `--strategy` | Parsing strategy: `fast` or `high_quality`. Default: `fast` |
| `--metadata` | JSON metadata to attach to all uploaded files |
| `--dry-run` | Show which files would be uploaded without actually uploading |
| `--parallel` | Number of concurrent uploads (1-200). Default: `100` |
| `--unique` | Skip files that have already been uploaded (based on content hash) |
| `--manifest` | Path to a JSON or YAML manifest file that specifies files, metadata, and strategy per file |

**Note:** The `--contextualization` flag on upload is **deprecated**. Configure contextualization at store creation time using `mxbai store create --contextualization` instead.

### Examples

Upload all PDFs in the current directory:

```bash
mxbai store upload my-docs "*.pdf"
```

Upload from multiple patterns:

```bash
mxbai store upload my-docs "docs/**/*.md" "guides/**/*.txt"
```

Upload with high-quality parsing and metadata:

```bash
mxbai store upload my-docs "*.pdf" \
  --strategy high_quality \
  --metadata '{"source": "manual-upload", "version": "2.1"}'
```

Preview what would be uploaded:

```bash
mxbai store upload my-docs "src/**/*.md" --dry-run
```

Upload with limited parallelism:

```bash
mxbai store upload my-docs "data/**/*" --parallel 10
```

Upload only unique files (skip duplicates):

```bash
mxbai store upload my-docs "docs/**/*.md" --unique
```

Upload using a manifest file:

```bash
mxbai store upload my-docs --manifest upload-manifest.yaml
```

### Manifest File Format

A manifest file lets you specify per-file metadata and strategy overrides. It can be JSON or YAML.

YAML example (`upload-manifest.yaml`):

```yaml
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

Fields:

- `version` -- Manifest format version. Currently `"1"`.
- `defaults.strategy` -- Default parsing strategy applied to all files unless overridden.
- `defaults.metadata` -- Default metadata merged into each file's metadata.
- `files` -- Array of file entries. Each entry supports:
  - `path` -- File path or glob pattern (required).
  - `metadata` -- JSON metadata for this file (merged with defaults).
  - `strategy` -- Parsing strategy override for this file.

