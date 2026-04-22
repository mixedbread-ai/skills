<div align="center">
  <a href="https://github.com/mixedbread-ai/skills">
    <img src="public/logo_mb.svg" alt="Mixedbread Logo" width="96" height="96" />
  </a>
  <h1>Mixedbread Skills</h1>
  <p><em>All Mixedbread Skills you ever need.</em></p>
</div>

Agent skills for building search, RAG, and document parsing with [Mixedbread](https://www.mixedbread.com). Compatible with Claude Code, Cursor, Codex, Gemini CLI, and [20+ other agents](https://skills.sh/).

## Installation

Install all skills with one command (works with Claude Code, Cursor, Codex, Gemini CLI, and more):

```bash
npx skills add mixedbread-ai/skills
```

Or install globally for all projects:

```bash
npx skills add mixedbread-ai/skills -g
```

Browse on the registry: [skills.sh/mixedbread-ai/skills](https://skills.sh/mixedbread-ai/skills)

### Platform-Specific Alternatives

<details>
<summary>Claude Code</summary>

```bash
claude install-skill mixedbread-ai/skills mxbai-cli
claude install-skill mixedbread-ai/skills mixedbread-search
claude install-skill mixedbread-ai/skills mixedbread-parsing
```
</details>

<details>
<summary>Cursor</summary>

This repo ships as a Cursor marketplace with three separately-installable plugins (`mxbai-cli`, `mixedbread-search`, `mixedbread-parsing`). Install from the [Cursor marketplace](https://cursor.com/marketplace), or test locally by cloning into `~/.cursor/plugins/local`:

```bash
git clone https://github.com/mixedbread-ai/skills ~/.cursor/plugins/local/mixedbread-skills
```

Cursor reads `.cursor-plugin/marketplace.json` at the repo root.
</details>

<details>
<summary>Codex</summary>

```bash
cp agents/AGENTS.md .agents/AGENTS.md
```
</details>

<details>
<summary>Gemini CLI</summary>

Reference the `gemini-extension.json` for extension configuration, or use the `.mcp.json` for MCP server integration.
</details>

## Available Skills

| Skill | Description |
|-------|-------------|
| [`mxbai-cli`](skills/mxbai-cli/SKILL.md) | Manage stores, upload files, search, and sync using the `mxbai` CLI |
| [`mixedbread-search`](skills/mixedbread-search/SKILL.md) | Create and search managed knowledge bases using the Stores API and SDKs |
| [`mixedbread-parsing`](skills/mixedbread-parsing/SKILL.md) | Parse documents, extract structured content, and run OCR using the Parsing API |

See [SKILL_TREE.md](SKILL_TREE.md) for a navigable index of all skills.

## Repository Structure

```
mixedbread-skills/
├── .claude-plugin/          # Claude Code plugin config
├── .cursor-plugin/          # Cursor plugin config
├── .mcp.json                # MCP server config
├── gemini-extension.json    # Gemini CLI extension
├── agents/AGENTS.md         # Codex fallback
├── CLAUDE.md                # Project conventions
├── SKILL_TREE.md            # Navigable skill index
├── README.md
├── LICENSE
└── skills/
    ├── mxbai-cli/           # CLI tool usage
    ├── mixedbread-search/   # Stores API & SDKs
    └── mixedbread-parsing/  # Parsing API & OCR
```

## Links

- [Documentation](https://www.mixedbread.com/docs)
- [API Reference](https://www.mixedbread.com/api-reference)
- [CLI Guide](https://www.mixedbread.com/cli)
- [Platform (API Keys)](https://platform.mixedbread.com)
- [GitHub](https://github.com/mixedbread-ai)

## License

Apache-2.0 — see [LICENSE](LICENSE).
