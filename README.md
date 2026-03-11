<div align="center">
  <a href="https://github.com/mixedbread-ai/mgrep">
    <img src="public/logo_mb.svg" alt="Mixedbread Logo" width="96" height="96" />
  </a>
  <h1>Mixedbread Skills</h1>
  <p><em>All Mixedbread Skills you ever need.</em></p>
</div>

Agent skills for building search, RAG, and document parsing with [Mixedbread](https://www.mixedbread.com). Compatible with Claude Code, Cursor, Codex, and Gemini CLI.

## Installation

### Claude Code

Install individual skills from the marketplace:

```bash
claude install-skill mixedbread-ai/mixedbread-skills mxbai-cli
claude install-skill mixedbread-ai/mixedbread-skills mixedbread-search
claude install-skill mixedbread-ai/mixedbread-skills mixedbread-parsing
```

### Cursor

Add this repository as a plugin in your Cursor settings, or clone and reference the `.cursor-plugin/` directory.

### Codex

Copy the `agents/AGENTS.md` file into your project, or reference skill files directly:

```bash
cp agents/AGENTS.md .agents/AGENTS.md
```

### Gemini CLI

Reference the `gemini-extension.json` for extension configuration, or use the `.mcp.json` for MCP server integration.

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
