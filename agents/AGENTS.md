# Mixedbread Skills

Agent skills for building search, RAG, and document intelligence with Mixedbread.

## Available Skills

### mxbai-cli
Manage stores, upload files, search, and sync documents using the `mxbai` CLI tool. Covers store creation, file operations, semantic search, question answering, and git-native sync for CI/CD workflows.
- Skill file: [skills/mxbai-cli/SKILL.md](../skills/mxbai-cli/SKILL.md)

### mixedbread-search
Build and query managed search indexes (Stores) using the Mixedbread Python and TypeScript SDKs. Create stores, upload files, perform semantic search, ask questions, and manage metadata.
- Skill file: [skills/mixedbread-search/SKILL.md](../skills/mixedbread-search/SKILL.md)


## Setup

1. Get an API key at https://platform.mixedbread.com
2. Set the environment variable: `export MXBAI_API_KEY=your-api-key`
3. Install the CLI (optional): `npm install -g @mixedbread/cli`
4. Install the SDK: `pip install mixedbread` (Python) or `npm install @mixedbread/sdk` (TypeScript)
