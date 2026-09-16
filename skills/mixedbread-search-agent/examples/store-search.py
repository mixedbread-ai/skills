"""A search-grounded answer over one Mixedbread Store, with citations.

The server runs the whole search loop: the model picks among the hosted
store tools, reads the chunks, and answers. `citations: true` ships the
answer with `file_citation` annotations pointing at the cited chunks.
"""

import os

from openai import OpenAI

client = OpenAI(
    base_url="https://api.mixedbread.com/v1",
    api_key=os.environ["MXBAI_API_KEY"],
)
STORE = os.environ.get("MXBAI_STORE", "my-store")

response = client.responses.create(
    model="toast-1",
    input="Which asset manager grew AUM fastest last quarter, and what drove it?",
    tools=[
        {"type": "search_corpus", "store_identifiers": [STORE], "citations": True},
        {"type": "grep", "store_identifiers": [STORE], "citations": True},
        {"type": "inspect_metadata", "store_identifiers": [STORE]},
        {"type": "filter_chunks", "store_identifiers": [STORE], "citations": True},
        {"type": "get_chunks", "store_identifiers": [STORE]},
    ],
    include=["search_corpus_call.results"],
    extra_body={"context_management": {"edits": [{"type": "prune_context"}]}},
)
if response.status != "completed":
    raise RuntimeError(f"Response did not complete: {response.status}")

print(response.output_text)

# Each annotation carries file_id, filename, index (a character offset into
# the answer), chunk_id ("<file_id>:<chunk_index>") and store_id.
for item in response.output:
    if item.type == "message":
        for part in item.content:
            for annotation in getattr(part, "annotations", None) or []:
                print(annotation.model_dump())
