# Mixedbread Skills

Agent skills for building search, RAG, and document intelligence with [Mixedbread](https://www.mixedbread.com).

## Repository Structure

- `skills/` — Each subdirectory is a self-contained skill with a `SKILL.md` and `references/`
- `.claude-plugin/` — Claude Code plugin configuration
- `.cursor-plugin/` — Cursor plugin configuration
- `.mcp.json` — MCP server configuration
- `agents/AGENTS.md` — Fallback instructions for Codex/OpenAI agents

## Conventions

- Each skill's `SKILL.md` uses YAML frontmatter with `name` and `description` fields
- The `description` field determines when the agent activates the skill — write it as a trigger condition
- Reference docs go in `references/` and are loaded on demand
- SKILL.md contains a quick-reference overview; `references/` files have deep-dive docs
- Code examples use both Python (`mixedbread` package) and TypeScript (`@mixedbread/sdk`)
- API base URL: `https://api.mixedbread.com/`
- API key env var: `MXBAI_API_KEY`
- CLI tool: `mxbai` (installed via `npm install -g @mixedbread/cli`)

## Adding a New Skill

1. Create a directory under `skills/` with a kebab-case name
2. Add a `SKILL.md` with YAML frontmatter (`name`, `description`) and instructions
3. Add reference docs in `references/` as needed
4. Update `.claude-plugin/marketplace.json` with the new skill entry
5. Update the skills table in `README.md`

## Key Links

- Docs: https://www.mixedbread.com/docs
- API Reference: https://www.mixedbread.com/api-reference
- CLI: https://www.mixedbread.com/cli
- Platform: https://platform.mixedbread.com
- GitHub: https://github.com/mixedbread-ai
