# Store Management

CRUD operations for managing stores in the mixedbread platform.

Store names must contain only lowercase letters, numbers, periods, and hyphens. Names must be unique within your organization.

## Create a Store

```
mxbai store create <name>
```

| Flag | Description |
|------|-------------|
| `--description` | Human-readable description of the store |
| `--expires-after` | Number of days after which the store expires and is deleted |
| `--metadata` | Arbitrary JSON metadata attached to the store |
| `--public` | Make the store publicly accessible |
| `--contextualization` | Enable contextualization. Use `true` for automatic or a comma-separated list of fields (e.g., `title,author`) |

### Examples

Create a basic store:

```bash
mxbai store create my-docs
```

Create a store with a description and expiration:

```bash
mxbai store create my-docs --description "Product documentation" --expires-after 90
```

Create a public store with metadata:

```bash
mxbai store create my-docs --public --metadata '{"team": "engineering", "project": "api"}'
```

Create a store with automatic contextualization:

```bash
mxbai store create my-docs --contextualization true
```

Create a store with specific contextualization fields:

```bash
mxbai store create my-docs --contextualization title,author,category
```

## Get Store Details

```
mxbai store get <name-or-id>
```

Retrieves full details for a single store, including its configuration, file count, and metadata.

### Examples

```bash
mxbai store get my-docs
```

```bash
mxbai store get str_abc123
```

## Update a Store

```
mxbai store update <name-or-id>
```

| Flag | Description |
|------|-------------|
| `--name` | Rename the store (must follow naming rules) |
| `--description` | Update the description |
| `--expires-after` | Update the expiration period in days |
| `--metadata` | Replace the store metadata with new JSON |
| `--public` | Toggle public accessibility |

### Examples

Rename a store:

```bash
mxbai store update my-docs --name my-documentation
```

Update description and metadata:

```bash
mxbai store update my-docs --description "Updated docs" --metadata '{"version": 2}'
```

Make a store public:

```bash
mxbai store update my-docs --public
```

## List Stores

```
mxbai store list
```

| Flag | Description |
|------|-------------|
| `--filter` | Filter stores by name or other attributes |
| `--limit` | Maximum number of stores to return |

### Examples

List all stores:

```bash
mxbai store list
```

List with a filter:

```bash
mxbai store list --filter "docs"
```

List with a limit:

```bash
mxbai store list --limit 5
```

## Delete a Store

```
mxbai store delete <name-or-id>
```

Alias: `mxbai store rm`

| Flag | Description |
|------|-------------|
| `--yes` / `-y` | Skip the confirmation prompt |

Deleting a store permanently removes all files and data within it. This action cannot be undone.

### Examples

Delete with confirmation prompt:

```bash
mxbai store delete my-docs
```

Delete without confirmation (useful in scripts):

```bash
mxbai store delete my-docs --yes
```

Using the alias:

```bash
mxbai store rm my-docs -y
```

## Authentication

Commands authenticate using the following priority:

1. `--api-key` flag passed directly to the command
2. `MXBAI_API_KEY` environment variable
3. Config file (set via `mxbai config`)

```bash
# Using the flag
mxbai store list --api-key mxbai-...

# Using the environment variable
export MXBAI_API_KEY=mxbai-...
mxbai store list
```

## Common Patterns

Create a temporary store for a PR review:

```bash
mxbai store create pr-review-1234 \
  --description "Review artifacts for PR #1234" \
  --expires-after 7 \
  --metadata '{"pr": 1234, "repo": "myorg/myrepo"}'
```

Rename and update a store after a project change:

```bash
mxbai store update old-project-docs \
  --name new-project-docs \
  --description "Migrated documentation" \
  --metadata '{"migrated": true}'
```
