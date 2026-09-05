# Optional Python loop

[search_loop.py](../scripts/search_loop.py) is a small executable example with a pluggable retrieval
function. Read it when a Python starting point helps; using this layout is not necessary for Toast
performance. The public [toast-harness](https://github.com/mixedbread-ai/toast-harness) contains the
full training harness, prompts, and other API examples.

## Connect your backend

Put `search_loop.py` on your Python import path. Supply a synchronous or asynchronous
`search(query, top_k) -> list[Chunk]`, with `Chunk(chunk_id, text, source)` entries in relevance order.
Use stable backend identities; retain the full text in each entry so the example's expansion tool
can restore it. Large backends can replace that in-memory cache with their own lookup.

```python
from search_loop import Chunk, run_episode

async def search(query, top_k):
    hits = await your_backend.search(query, top_k=top_k)
    return [Chunk(str(hit.id), hit.text, hit.source) for hit in hits]

result = await run_episode(
    client, "Which agreement governs the renewal?", search,
    search_description="Search the corpus by meaning. Use a focused natural-language question for each aspect.",
)
```

Use an OpenAI `AsyncOpenAI` client with base URL `https://api.mixedbread.com/v1` and an explicit
`MXBAI_API_KEY`. The declaration is a client function named `search_corpus`, so it calls your backend.
Update its description to match that backend. The example's tool names, envelopes, and policies
can be changed together; the two tool functions are not a required tool set.

The default result is a prose answer. `answer_mode="none"` returns ranked evidence;
`answer_mode="submit_ranking"` adds an answer to that ranking. In this example, `ranking_strategy`
is optional, duplicate ranking IDs are rejected, and the terminal validates IDs and score ranges.

## One local keyword-search example

For users who prefer keyword search, [keyword_search.py](../scripts/keyword_search.py) supplies a
local BM25 backend over `.md` and `.txt` files. It is a standalone demonstration of one retrieval
choice, not the training harness's retrieval backend. From this skill's directory:

```bash
pip install openai
python scripts/keyword_search.py ./docs "renewal agreement expiry"
python scripts/keyword_search.py ./docs "renewal agreement expiry" --answer-mode submit_ranking
```

The same adapter supports all three answer modes. No additional keyword-search implementation
is needed elsewhere in a harness; replace this adapter and its description when using another backend.

## Example policies and limits

`Limits` configures four total turns including the final turn, up to two additional corrections,
eight concurrent calls, and 24,000 UTF-8 bytes of combined tool content per round. These are example
budgets, not model requirements. Per-call shares keep one large result from consuming the entire
round. Within each call, prefer fewer useful passages over tiny fragments; short complete chunks
can still fit. Retrieval runs concurrently; deduplication and registration happen serially after
clipping, so discarded chunks are not marked as seen. Expansion allocates more space to earlier
requested IDs and may omit later ones; request fewer IDs or concurrent calls for more context.
An interrupted search tool turn can retry within the remaining search turns. Invalid endings
use bounded terminal correction without reopening retrieval.

Byte limits bound serialized payload size; they are not exact token accounting or a guarantee that
arbitrary prompts, tools, and larger budgets fit the context window. Keep headroom and use actual
token accounting when tuning larger runs. Async backends can support cancellation; timing out a
synchronous backend call does not stop its worker thread, so configure backend timeouts too.

The example follows our recommendation to enable server-side pruning and continue stored
completions, sending only new messages. Its return value includes `completion_id`, evidence, and
usage/context-edit traces. Storage is explicit (`store=True`); a stateless implementation can send
`store=False` and replay its history, retaining any desired context edits itself. See the API skill
or [API documentation](https://www.mixedbread.com/docs/agent/chat-completions) for those contracts.

Regression tests are in this repository's `tests/test_search_loop.py` and use scripted responses
and temporary corpora without API calls. They cover interrupted searches, malformed and truncated
endings, continuation, parallel duplicates, useful payload sizes, and expansion. Live task evaluations
are still needed when changing retrieval or prompts.
