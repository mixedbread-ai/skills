# Mixedbread Skills

Agent skills for building search, RAG, and document parsing with Mixedbread.

## Available Skills

### mxbai-cli
Manage stores, upload files, search, and sync documents using the `mxbai` CLI tool. Covers store management, file operations, semantic search, question answering, multipart uploads, API key management, and git-native sync for CI/CD workflows.
- Skill file: [skills/mxbai-cli/SKILL.md](../skills/mxbai-cli/SKILL.md)

### mixedbread-search
Build and query managed search indexes (Stores) using the Mixedbread Python and TypeScript SDKs. Create stores, upload files, perform semantic search, ask questions, use agentic multi-step retrieval, search the web, and manage metadata.
- Skill file: [skills/mixedbread-search/SKILL.md](../skills/mixedbread-search/SKILL.md)

### mixedbread-parsing
Parse documents, extract structured content, and run OCR using the Mixedbread Parsing API. Supports PDFs, Word documents, PowerPoint presentations, and images. Extract tables, forms, figures, and other elements with bounding boxes and confidence scores.
- Skill file: [skills/mixedbread-parsing/SKILL.md](../skills/mixedbread-parsing/SKILL.md)


## Setup

1. Get an API key at https://platform.mixedbread.com/platform?next=api-keys
2. Set the environment variable: `export MXBAI_API_KEY=your_api_key`
3. Install the CLI (optional): `npm install -g @mixedbread/cli`
4. Install the SDK: `pip install mixedbread` (Python) or `npm install @mixedbread/sdk` (TypeScript)
