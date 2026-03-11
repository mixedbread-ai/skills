# Mixedbread Skills

Agent skills for building search, RAG, and document parsing with [Mixedbread](https://www.mixedbread.com).

## Repository Structure

- `skills/` — Each subdirectory is a self-contained skill with a `SKILL.md`
  - `skills/mxbai-cli/` — CLI tool usage
  - `skills/mixedbread-search/` — Stores API & SDKs
  - `skills/mixedbread-parsing/` — Parsing API & OCR
- `.claude-plugin/` — Claude Code plugin configuration
- `.cursor-plugin/` — Cursor plugin configuration
- `.mcp.json` — MCP server configuration
- `gemini-extension.json` — Gemini CLI extension configuration
- `agents/AGENTS.md` — Fallback instructions for Codex/OpenAI agents
- `SKILL_TREE.md` — Navigable index of all skills

## Conventions

- Each skill's `SKILL.md` uses YAML frontmatter with `name` and `description` fields
- The `description` field determines when the agent activates the skill — write it as a trigger condition
- SKILL.md contains decision trees, workflows, severity-rated rules, anti-patterns, and troubleshooting
- API reference docs are not bundled — agents fetch them at runtime via MCP, context7, or docs URLs (e.g., `https://www.mixedbread.com/docs.md`)
- Code examples use both Python (`mixedbread` package) and TypeScript (`@mixedbread/sdk`)
- API base URL: `https://api.mixedbread.com/`
- API key env var: `MXBAI_API_KEY`
- CLI tool: `mxbai` (installed via `npm install -g @mixedbread/cli`)

## Adding a New Skill

1. Create a directory under `skills/` with a kebab-case name
2. Add a `SKILL.md` with YAML frontmatter (`name`, `description`) and skill content (decision tree, workflows, rules, anti-patterns, troubleshooting)
3. Update `.claude-plugin/marketplace.json` with the new skill entry
4. Update `.cursor-plugin/marketplace.json` with the new skill entry
5. Update the skills table in `README.md`
6. Update `agents/AGENTS.md` with the new skill entry
7. Update `SKILL_TREE.md` with the new skill

## Key Links

- Docs: https://www.mixedbread.com/docs
- API Reference: https://www.mixedbread.com/api-reference
- CLI: https://www.mixedbread.com/cli
- Platform: https://platform.mixedbread.com
- GitHub: https://github.com/mixedbread-ai
