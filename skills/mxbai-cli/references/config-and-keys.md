# Configuration and API Key Management

Manage API keys, configure defaults, and set store aliases using `mxbai config`.

## API Key Management

### Add a Key

```bash
mxbai config keys add <key> [name]
```

Add an API key with an optional name. If no name is provided, one is generated automatically.

```bash
# Add a key with a name
mxbai config keys add mxb_xxxxx production

# Add a key (auto-named)
mxbai config keys add mxb_xxxxx
```

### List Keys

```bash
mxbai config keys list
```

Lists all saved API keys with their names and a masked preview.

### Set Default Key

```bash
mxbai config keys set-default <name>
```

Set which saved key is used by default when no `--api-key` or `--saved-key` flag is passed.

```bash
mxbai config keys set-default production
```

### Remove a Key

```bash
mxbai config keys remove <name>
```

| Flag | Description |
|------|-------------|
| `--yes` / `-y` | Skip the confirmation prompt |

```bash
mxbai config keys remove staging --yes
```

### Using Saved Keys

Reference a saved key by name on any command:

```bash
mxbai store list --saved-key production
mxbai store search my-docs "query" --saved-key staging
```

## Configuration Defaults

Set default values so you don't need to pass them on every command.

### Upload Defaults

```bash
# Set default parsing strategy
mxbai config set defaults.upload.strategy high_quality

# Set default parallelism (1-200)
mxbai config set defaults.upload.parallel 50
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `defaults.upload.strategy` | string | `fast` | Parsing strategy: `fast` or `high_quality` |
| `defaults.upload.parallel` | int | `100` | Concurrent uploads (1–200) |

### Search Defaults

```bash
# Set default number of results
mxbai config set defaults.search.top_k 20

# Enable reranking by default
mxbai config set defaults.search.rerank true
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `defaults.search.top_k` | int | `10` | Number of results to return |
| `defaults.search.rerank` | bool | `false` | Enable reranking by default |

### Reading Defaults

```bash
# Read a specific default
mxbai config get defaults.search.top_k

# Read all config
mxbai config get
```

## Store Aliases

Create short aliases for store names or IDs to use in commands.

```bash
# Set an alias
mxbai config set aliases.docs "my-documentation-store"
mxbai config set aliases.prod "str_abc123"

# Use the alias in commands
mxbai store search docs "how to deploy"
mxbai store upload prod "files/**/*.md"

# View aliases
mxbai config get aliases
```

Aliases are resolved before store name lookup. If an alias matches, the mapped store name or ID is used.

## Config File Location

The config file is stored at `~/.config/mxbai/config.json` by default. Override with:

```bash
export MXBAI_CONFIG_PATH=/custom/path/config.json
```

## Common Patterns

### CI/CD Setup

```bash
# Add a CI-specific key
mxbai config keys add $MXBAI_API_KEY ci

# Set CI defaults
mxbai config set defaults.upload.strategy high_quality
mxbai config set defaults.upload.parallel 20
```

### Multi-Environment Workflow

```bash
# Add keys for different environments
mxbai config keys add mxb_prod_xxxxx production
mxbai config keys add mxb_staging_xxxxx staging

# Set production as default
mxbai config keys set-default production

# Use staging for a specific command
mxbai store search staging-docs "query" --saved-key staging
```
