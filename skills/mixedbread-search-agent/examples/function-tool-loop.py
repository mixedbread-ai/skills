"""One client function tool, run in a loop.

The corpus lives behind your own function: the model returns a
`function_call` item, you run it and send a `function_call_output` with
`previous_response_id`, and repeat until the response carries no calls. The
stub below stands in for your backend; replace `search_tickets` with a real
lookup and keep the loop.
"""

import json
import os

from openai import OpenAI

client = OpenAI(
    base_url="https://api.mixedbread.com/v1",
    api_key=os.environ["MXBAI_API_KEY"],
)

TICKETS = [
    {"id": "T-1042", "title": "Checkout times out on Safari", "status": "open", "area": "payments"},
    {"id": "T-1071", "title": "Invoice PDF missing VAT line", "status": "closed", "area": "billing"},
]


def search_tickets(query: str, status: str | None = None) -> list[dict]:
    """The stub; a real backend would query a database or an API."""
    words = query.lower().split()
    return [
        t
        for t in TICKETS
        if (status is None or t["status"] == status) and any(w in t["title"].lower() for w in words)
    ]


TOOL = {
    "type": "function",
    "name": "search_tickets",
    "description": "Search the support ticket tracker by keyword. Returns id, title, status and area.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keywords to look for in ticket titles."},
            "status": {"type": "string", "enum": ["open", "closed"]},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}
CONTEXT = {"context_management": {"edits": [{"type": "prune_context"}]}}

response = client.responses.create(
    model="toast-1",
    input="Which open tickets are about checkout problems?",
    tools=[TOOL],
    extra_body=CONTEXT,
)
for _ in range(8):  # bound the loop; a run that never answers is a bug to surface
    calls = [item for item in response.output if item.type == "function_call"]
    if not calls:
        break
    outputs = []
    for call in calls:
        try:
            result = search_tickets(**json.loads(call.arguments or "{}"))
        except Exception as exc:  # never let a tool raise past the executor
            result = {"error": str(exc), "retryable": True}
        outputs.append({"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(result)})
    response = client.responses.create(
        model="toast-1",
        previous_response_id=response.id,
        input=outputs,
        tools=[TOOL],
        extra_body=CONTEXT,
    )
if response.status != "completed":
    raise RuntimeError(f"Response did not complete: {response.status}")

print(response.output_text)
