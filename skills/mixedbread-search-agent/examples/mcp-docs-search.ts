// Documentation search over three keyless public MCP servers.
//
// Each `mcp` entry is one server; the model sees its tools and the server runs
// the calls. `require_approval: "never"` lets them run without a round trip.
// MCP results are not annotated, so the instructions ask for inline markdown
// links built from the result URLs.

import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://api.mixedbread.com/v1",
  apiKey: process.env.MXBAI_API_KEY!,
});

const SERVERS = [
  { label: "aws-knowledge", url: "https://knowledge-mcp.global.api.aws", docs: "the official AWS documentation" },
  { label: "microsoft-learn", url: "https://learn.microsoft.com/api/mcp", docs: "Microsoft Learn, which includes all Azure documentation" },
  {
    label: "context7",
    url: "https://mcp.context7.com/mcp",
    docs: "a public index of the official Google Cloud and Terraform documentation; resolve the library first, then query it",
  },
];

const INSTRUCTIONS = `You are Toast, Mixedbread's search agent, working as a cloud documentation assistant. Each MCP server is one documentation set:
${SERVERS.map((s) => `- ${s.label}: ${s.docs}`).join("\n")}

How to work:
- Route by vendor: use the server for the vendor the question is about. If the question spans vendors (a comparison, or Terraform managing a cloud resource), search each relevant vendor's docs.
- Break the question into focused sub-queries and search for each one; prefer several precise searches over a single broad one.
- Search results contain verbatim page text. Answer from those excerpts directly; read a full page only when the excerpts genuinely lack the detail you need.
- Stop searching once you have enough evidence.

Your final answer:
- Start with the direct answer. Do not narrate your plan, your evidence, or what you are about to do.
- GitHub-flavored markdown, concise and technical. Lead with the answer, then supporting detail. Use lists or a small table only when they genuinely help.
- Citations are mandatory: every paragraph or bullet that states a fact must link a key phrase to the exact documentation page it came from, as an inline markdown link, for example "route traffic through a [NAT gateway](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html)". Use the URLs from your search results verbatim. An answer without inline markdown links is incomplete.
- Only state what the documentation supports. If the docs do not answer the question, say so and summarize the closest findings. Never invent vendor behavior, limits, or pricing.`;

const response = await client.responses.create({
  model: "toast-1",
  input: "How do I grant cross-account access to an S3 bucket in Terraform?",
  instructions: INSTRUCTIONS,
  tools: SERVERS.map((s) => ({
    type: "mcp",
    server_label: s.label,
    server_url: s.url,
    require_approval: "never",
  })),
  context_management: { edits: [{ type: "prune_context" }] },
} as never);
if (response.status !== "completed") {
  throw new Error(`Response did not complete: ${response.status}`);
}

console.log(response.output_text);
for (const item of response.output) {
  if (item.type === "mcp_call") console.log(item.server_label, item.name, item.arguments, item.error);
}
