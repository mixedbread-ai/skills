# Mixedbread Skills

Agent skills for building search, RAG, and document parsing with [Mixedbread](https://www.mixedbread.com).

## Repository Structure

- `skills/` — Each subdirectory is a self-contained skill with a `SKILL.md`
  - `skills/mxbai-cli/` — CLI tool usage
  - `skills/mixedbread-search/` — Stores API & SDKs
  - `skills/mixedbread-parsing/` — Parsing API & OCR
  - `skills/mixedbread-search-agent/` — Toast-1 completions API, tool contracts & Stores wiring
  - `skills/mixedbread-search-agent-harness/` — Custom search-model harness design
- `.claude-plugin/` — Claude Code plugin configuration
- `.cursor-plugin/` — Cursor plugin configuration
- `.mcp.json` — MCP server configuration
- `gemini-extension.json` — Gemini CLI extension configuration
- `agents/AGENTS.md` — Fallback instructions for Codex/OpenAI agents
- `SKILL_TREE.md` — Navigable index of all skills
- `benchmark.sh` — Blind A/B comparison of agent output with and without the skills

## Conventions

- Each skill's `SKILL.md` uses YAML frontmatter with `name` and `description` fields
- The `description` field determines when the agent activates the skill — write it as a trigger condition
- Open with docs links and close with a Troubleshooting table. Everything between is up to the skill — name sections after what they actually cover rather than forcing a fixed template
- Do not group guidance by severity. Where a reference table already carries the constraint, let it; where the constraint is a mistake to avoid, state it as a flat "Don't" list
- Prefer tables and code over prose. State the fact and the fix; cut the explanation of why unless the agent gets it wrong without it
- Keep `SKILL.md` under 500 lines. Past that, move detail into `references/` and say in the pointer *when* to read each file
- Do not duplicate broad public API reference docs. Bundle focused behavioral references when a skill depends on non-obvious product or harness contracts, and link public docs for the general surface.
- Keep the search-model guidance backend-agnostic and isolate the Mixedbread wiring in its own reference. The model brings no retrieval of its own, so a skill that only shows Stores-backed tools teaches the wrong contract.
- Skills install as separate plugins, so a relative path into a sibling skill does not resolve. When two skills need the same reference — `tool-contracts.md` is the current case — duplicate the file in full rather than summarizing it in one of them, and update both copies together.
- The served model id is `toast-1`.
- SDK-facing examples normally cover both Python and TypeScript. Stores and parsing use the first-party SDKs (`mixedbread`, `@mixedbread/sdk`); the search agent uses the official OpenAI clients against Mixedbread's base URL. Harness-internal guidance may stay Python.
- The two OpenAI clients carry Mixedbread's protocol extensions differently — Python requires `extra_body`, Node takes them inline with a type cast — so write each language reference from a verified example rather than translating the other.
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
8. Bump the marketplace-level minor version when adding a skill

## Testing a Skill

- **Run the examples as written.** A skill can be internally consistent and still assert things the API no longer does. A snippet that raises `TypeError` on an unsupported keyword is a defect no amount of review catches.
- **Compare with and without the skill.** `./benchmark.sh --model sonnet` runs a blind LLM-judge comparison of full task output with and without the plugin. Anything that comes out the same either way is measuring the base model, not the skill.

Feed failures back as gotchas rather than as new rules. When an agent gets something wrong, the fix is usually one concrete correction in the skill's rules or troubleshooting table, not another paragraph of prose.

## Distribution and Versioning

- `main` is the rolling release source for `npx skills add mixedbread-ai/skills`; this repository does not publish an npm package or create GitHub releases automatically.
- Existing installations update through `npx skills check` and `npx skills update`.
- New marketplace plugins start at `1.0.0`.
- Bump an existing plugin's semantic version whenever its shipped skill content changes: patch for fixes, minor for backward-compatible capability additions, and major for breaking workflow changes.
- Bump the marketplace-level version when its plugin catalog or overall packaged capabilities change.

## Key Links

- Docs: https://www.mixedbread.com/docs
- API Reference: https://www.mixedbread.com/api-reference
- CLI: https://www.mixedbread.com/cli
- Platform: https://platform.mixedbread.com
- GitHub: https://github.com/mixedbread-ai
