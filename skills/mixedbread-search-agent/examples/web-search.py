"""Search the web with the same hosted tool, by naming the web store.

`mixedbread/web` is a store identifier `search_corpus` accepts; combine it
with your own stores in one entry to search both. Only `search_corpus`
reads it: the chunk tools (grep, filter_chunks, get_chunks) skip it. A web
hit is cited like any chunk, with the page URL as its `filename`.
"""

import os

from openai import OpenAI

client = OpenAI(
    base_url="https://api.mixedbread.com/v1",
    api_key=os.environ["MXBAI_API_KEY"],
)

response = client.responses.create(
    model="toast-1",
    input=(
        "What did the Federal Reserve decide at its most recent FOMC meeting, "
        "and how did Treasury yields and equities react? "
        "Cite the Fed's statement and one market report."
    ),
    tools=[
        {"type": "search_corpus", "store_identifiers": ["mixedbread/web"], "citations": True},
    ],
    extra_body={"context_management": {"edits": [{"type": "prune_context"}]}},
)
if response.status != "completed":
    raise RuntimeError(f"Response did not complete: {response.status}")

print(response.output_text)
for item in response.output:
    if item.type == "message":
        for part in item.content:
            for annotation in getattr(part, "annotations", None) or []:
                print(annotation.filename)  # the cited page's URL
