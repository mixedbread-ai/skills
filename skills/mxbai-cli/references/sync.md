# Store Sync

Synchronize local files with a remote store, uploading new and changed files and removing deleted ones.

## Command

```
mxbai store sync <name-or-id> <patterns...>
```

Detects changes between local files (matching the given glob patterns) and the current contents of the store, then applies the necessary uploads and deletions to bring the store in sync.

| Flag | Description |
|------|-------------|
| `--strategy` | Parsing strategy for new/changed files: `fast` or `high_quality` |
| `--from-git` | Use git diff from the given ref to detect changes (e.g., `HEAD~1`, `main`, `abc1234`) |
| `--dry-run` | Show what would be synced without making any changes |
| `--yes` / `-y` | Skip the confirmation prompt |
| `--force` / `-f` | Force re-upload of all matched files, regardless of change detection |
| `--metadata` | JSON metadata to attach to newly uploaded files |
| `--parallel` | Number of concurrent uploads (1-200). Default: `100` |

**Note:** The `--contextualization` flag on sync is **deprecated**. Configure contextualization at store creation time using `mxbai store create --contextualization` instead.

## Change Detection Methods

The sync command supports two methods for detecting which files have changed.

### 1. Git-Based Detection (`--from-git`)

Uses `git diff` from a reference commit to determine which files were added, modified, or deleted. This is the **fastest** method and is ideal for CI/CD pipelines where you know the base commit.

```bash
# Sync changes since the previous commit
mxbai store sync my-docs "docs/**/*.md" --from-git HEAD~1

# Sync changes since the main branch
mxbai store sync my-docs "docs/**/*.md" --from-git main

# Sync changes since a specific commit
mxbai store sync my-docs "docs/**/*.md" --from-git abc1234
```

Only files matching the provided glob patterns are considered, even if `git diff` reports changes to other files.

### 2. Hash-Based Detection (Default)

When `--from-git` is not specified, the CLI computes a hash of each local file and compares it against the hash stored in the file's metadata on the server. This is the **most accurate** method and works in any environment, including outside of git repositories.

```bash
# Hash-based sync (default behavior)
mxbai store sync my-docs "docs/**/*.md"
```

This method requires downloading file metadata from the store, so it may be slower than git-based detection for large stores.

## Examples

### Basic Sync

Sync all markdown files in the docs directory:

```bash
mxbai store sync my-docs "docs/**/*.md"
```

### Dry Run

Preview changes before applying them:

```bash
mxbai store sync my-docs "docs/**/*.md" --dry-run
```

Example output:

```
Sync plan for store "my-docs":
  Upload (new):      3 files
  Upload (changed):  2 files
  Delete (removed):  1 file
  Unchanged:        14 files

New files:
  + docs/guides/new-feature.md
  + docs/guides/migration.md
  + docs/api/webhooks.md

Changed files:
  ~ docs/api/authentication.md
  ~ docs/getting-started.md

Deleted files:
  - docs/deprecated/old-guide.md

Run without --dry-run to apply these changes.
```

### Force Sync

Re-upload all files, ignoring change detection:

```bash
mxbai store sync my-docs "docs/**/*.md" --force
```

### Non-Interactive Sync

Skip the confirmation prompt (required for CI/CD):

```bash
mxbai store sync my-docs "docs/**/*.md" --yes
```

### Sync with Metadata and Strategy

```bash
mxbai store sync my-docs "docs/**/*.md" \
  --strategy high_quality \
  --metadata '{"source": "ci", "build": "1234"}'
```

### Sync with Limited Parallelism

```bash
mxbai store sync my-docs "data/**/*" --parallel 20 --yes
```

## CI/CD Integration

### GitHub Actions

A typical workflow that syncs documentation on every push to the main branch:

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
        with:
          fetch-depth: 2  # Need at least 2 commits for HEAD~1

      - name: Install mxbai CLI
        run: npm install -g @mixedbread/cli

      - name: Sync docs to store
        env:
          MXBAI_API_KEY: ${{ secrets.MXBAI_API_KEY }}
        run: |
          mxbai store sync my-docs "docs/**/*.md" \
            --from-git HEAD~1 \
            --strategy high_quality \
            --yes
```

### GitHub Actions with Full Diff Against Main

For pull-request or merge workflows where you want to sync all changes since the branch diverged:

```yaml
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for accurate diff

      - name: Sync docs to store
        env:
          MXBAI_API_KEY: ${{ secrets.MXBAI_API_KEY }}
        run: |
          mxbai store sync my-docs "docs/**/*.md" \
            --from-git origin/main \
            --yes
```

### Key Points for CI/CD

- Always pass `--yes` (or `-y`) to skip the interactive confirmation prompt. CI environments are non-interactive and the command will hang without this flag.
- Use `--from-git` for faster change detection when running in a git repository. Set `fetch-depth` appropriately in your checkout step.
- Store the API key as a secret and expose it via the `MXBAI_API_KEY` environment variable.
- Use `--dry-run` in a separate step or job if you want to preview changes before applying them.

## Common Patterns

Sync on every deployment:

```bash
# In your deploy script
mxbai store sync production-docs "docs/**/*.md" \
  --from-git HEAD~1 \
  --strategy high_quality \
  --metadata '{"deploy_id": "'$DEPLOY_ID'"}' \
  --yes
```

Sync multiple directories into one store:

```bash
mxbai store sync my-docs "docs/**/*.md" "guides/**/*.md" "api/**/*.yaml" --yes
```

Periodic full re-sync with force:

```bash
# Weekly cron job to ensure store is fully up to date
mxbai store sync my-docs "docs/**/*" --force --yes
```
