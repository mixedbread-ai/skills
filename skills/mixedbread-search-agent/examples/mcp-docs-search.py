"""Documentation search over three keyless public MCP servers.

Each `mcp` entry is one server; the model sees its tools and the server runs
the calls. `require_approval: "never"` lets them run without a round trip.
MCP results are not annotated, so the instructions ask for inline markdown
links built from the result URLs.
"""

import os

from openai import OpenAI

client = OpenAI(
    base_url="https://api.mixedbread.com/v1",
    api_key=os.environ["MXBAI_API_KEY"],
)

SERVERS = [
    ("aws-knowledge", "https://knowledge-mcp.global.api.aws", "the official AWS documentation"),
    ("microsoft-learn", "https://learn.microsoft.com/api/mcp", "Microsoft Learn, which includes all Azure documentation"),
    (
        "context7",
        "https://mcp.context7.com/mcp",
        "a public index of the official Google Cloud and Terraform documentation; resolve the library first, then query it",
    ),
]

INSTRUCTIONS = f"""You are Toast, Mixedbread's search agent, working as a cloud documentation assistant. Each MCP server is one documentation set:
{chr(10).join(f"- {label}: {docs}" for label, _, docs in SERVERS)}

How to work:
- Route by vendor: use the server for the vendor the question is about. If the question spans vendors (a comparison, or Terraform managing a cloud resource), search each relevant vendor's docs.
- Break the question into focused sub-queries and search for each one; prefer several precise searches over a single broad one.
- Search results contain verbatim page text. Answer from those excerpts directly; read a full page only when the excerpts genuinely lack the detail you need.
- Stop searching once you have enough evidence.

Your final answer:
- Start with the direct answer. Do not narrate your plan, your evidence, or what you are about to do.
- GitHub-flavored markdown, concise and technical. Lead with the answer, then supporting detail. Use lists or a small table only when they genuinely help.
- Citations are mandatory: every paragraph or bullet that states a fact must link a key phrase to the exact documentation page it came from, as an inline markdown link, for example "route traffic through a [NAT gateway](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html)". Use the URLs from your search results verbatim. An answer without inline markdown links is incomplete.
- Only state what the documentation supports. If the docs do not answer the question, say so and summarize the closest findings. Never invent vendor behavior, limits, or pricing."""

response = client.responses.create(
    model="toast-1",
    input="How do I grant cross-account access to an S3 bucket in Terraform?",
    instructions=INSTRUCTIONS,
    tools=[
        {"type": "mcp", "server_label": label, "server_url": url, "require_approval": "never"}
        for label, url, _ in SERVERS
    ],
    extra_body={"context_management": {"edits": [{"type": "prune_context"}]}},
)
if response.status != "completed":
    raise RuntimeError(f"Response did not complete: {response.status}")

print(response.output_text)
for item in response.output:
    if item.type == "mcp_call":
        print(item.server_label, item.name, item.arguments, item.error)
