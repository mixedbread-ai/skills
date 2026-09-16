# Remote MCP servers

The Responses API can run the tools of a remote [Model Context Protocol](https://modelcontextprotocol.io) server on the model's behalf, the way it runs the hosted store tools. Declare an `mcp` entry per server; the server's tools are listed when the request starts and offered to the model, and each call runs server-side unless it needs your approval first. Chat Completions does not accept `mcp` entries.

Verify the wire contract against the [Responses API reference](https://www.mixedbread.com/api-reference/endpoints/responses/create-response) and the [Responses guide](https://www.mixedbread.com/docs/agent/responses).

## Tool entry

| Field | Required | Meaning |
|-------|----------|---------|
| `type` | yes | `"mcp"` |
| `server_label` | yes | Names the server in output items and in `tool_choice`; letters, digits, `_` and `-` |
| `server_url` | yes | The server's Streamable HTTP endpoint. `connector_id` is not supported |
| `server_description` | no | Shown to the model beside the server's tools |
| `require_approval` | no | `"always"` (**the default**: every call comes back as an approval request), `"never"`, or `{"never": {"tool_names": [...]}, "always": {...}}` filters; a filter can also match by tool annotation such as `{"read_only": true}` |
| `allowed_tools` | no | Tool names, or a filter, restricting which of the server's tools are offered |
| `headers`, `authorization` | no | Credentials sent to the server. Never stored or echoed, so a continuation with `previous_response_id` must declare the server again |

`tool_choice: {"type": "mcp", "server_label": "docs"}` forces a call to that server on the first turn; add `"name"` to force one of its tools.

Keyless public docs servers, as used by the [mcp-docs-search example](../examples/mcp-docs-search.py):

| Server | `server_url` | Covers |
|--------|--------------|--------|
| AWS Knowledge | `https://knowledge-mcp.global.api.aws` | The official AWS documentation |
| Microsoft Learn | `https://learn.microsoft.com/api/mcp` | Microsoft Learn, including Azure |
| Context7 | `https://mcp.context7.com/mcp` | A public index of many documentation sites, Google Cloud and Terraform among them; resolve the library first, then query it |

## What comes back

MCP items are ordinary `output` items, in emission order:

| Item `type` | Fields | When |
|-------------|--------|------|
| `mcp_list_tools` | `id`, `server_label`, `tools[]` (`name`, `description`, `input_schema`), `error` | Once per server, at the start of the run |
| `mcp_call` | `id`, `server_label`, `name` (the tool's name on the server), `arguments` (JSON string), `output`, `error`, `approval_request_id`, `status` | Once per executed call |
| `mcp_approval_request` | `id`, `server_label`, `name`, `arguments` | A call waiting for you; the run stops here |

To answer an approval request, continue the response with `previous_response_id` and an input item `{"type": "mcp_approval_response", "approval_request_id": "<id>", "approve": true}` (optional `reason`); the call then runs, or is refused, and the run resumes. With `require_approval: "never"` no request is ever raised.

MCP results are evidence the model reads and cites in prose. They do not produce `file_citation` annotations, so when answers should link to pages, say so in `instructions` and ask for inline markdown links built from the result URLs, as the example's instructions do.

## Gotchas

| Symptom | Cause | Fix |
|---------|-------|-----|
| The run ends with `mcp_approval_request` items and no answer | `require_approval` defaults to `"always"` | `"never"`, or a `{"never": ...}` filter for the safe tools |
| 422 naming `connector_id` | OpenAI service connectors are not supported | Pass `server_url` |
| 422 naming `server_url` | The entry has no endpoint | Every `mcp` entry needs `server_url` |
| A continuation cannot reach an authenticated server | `headers` / `authorization` are not stored | Declare the server with its credentials on every request in the chain |
| `mcp` entry rejected on Chat Completions | MCP is Responses-only | Use `POST /v1/responses` |
| Answer names facts without links | MCP evidence is not annotated | Instruct the model to cite as inline markdown links using result URLs |
