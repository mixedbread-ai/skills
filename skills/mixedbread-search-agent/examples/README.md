# Examples

Runnable requests against `POST /v1/responses`, one per kind of search tool. Each mirrors a card in the platform's Agents playground, so a request copied from there lands on the same shape. Every file needs `MXBAI_API_KEY`; the store examples also take `MXBAI_STORE` (a store name or id you can read).

| Example | Tools | Shows |
|---------|-------|-------|
| `store-search` | The hosted store tools over one Store, `citations: true` | A search-grounded answer with `file_citation` annotations pointing at chunks |
| `web-search` | `search_corpus` over `mixedbread/web` | Searching the web with the same tool; a web hit's `filename` is its URL |
| `mcp-docs-search` | Three keyless `mcp` servers plus routing instructions | Server-side MCP calls and answers that cite doc pages as inline links |
| `function-tool-loop` | One client `function` tool | The `function_call` / `function_call_output` loop with `previous_response_id` |

Python: `pip install openai`, then `python store-search.py`. TypeScript: `npm install openai`, then `npx tsx store-search.ts`.
