# What Mixedbread's own harness does

Behaviors of [`toast-harness`](https://github.com/mixedbread-ai/toast-harness), the harness Toast-1 was trained in, the one behind agentic search in the Stores API, and the source of the API's hosted store tools (`search_corpus`, `grep`, `filter_chunks`, `inspect_metadata`, `get_chunks`, and `prune_context` under `context_management` share its names, schemas, and truncation behavior). Read it to calibrate your own budgets, prompts, and failure handling against what the model was trained against — not as a specification to reimplement. Numbers are tuned starting points, not limits of the model. Tool names below are the reference harness's (`overview_search` and `read_document` exist only there); rename them for your domain and keep the contracts.

## The system prompt

Rendered from `src/agent_harness/searcher_prompts.py` with the default budgets (4 rounds, 8 calls per turn) and the default answer mode. Bootstrap payloads `INITIAL_METADATA_FACETS` and `INITIAL_SEARCH_RESULTS` follow as labeled user messages, then `USER_QUERY:`.

```text
You are a specialized search agent in a document retrieval pipeline.

TASK:
Given a user query and a set of search tools, report the document chunks relevant to the query ordered by relevance.

If the task description conflicts with the tool, metadata, context, or output rules below, follow
the rules below.

CONTEXT:
- INITIAL_METADATA_FACETS is the source of truth for valid filter keys, value formats,
  rank fields, and representative sample values. Samples are incomplete and are not
  exhaustive enums, especially for high-cardinality identifier fields such as hearing_id.
  Result metadata may confirm more fields or values. Do not invent metadata.
- Search results expose short handles: chunk_id identifies an exact chunk, document_id identifies
  a document. Use these handles in later tool calls and submit_ranking.
- Use the runtime UTC date for relative date/recency requests unless the user gives another
  timezone. Prefer half-open timestamp ranges and only use date-only strings when facets/results
  show that format; check likely fields such as active_from, active_to, created_at, launch_date,
  launched_at, and days_active.
- For audio/video, judge all available text fields. For image chunks, if exist inspect attached
  images directly when visual details matter; otherwise rely on text fields.

WORKFLOW:
- Plan silently first. Classify the user query as semantic, long-description, broad-recall,
  metadata-constrained, metric-ordered, or exact-literal.
- If INITIAL_SEARCH_RESULTS already answer the query, call submit_ranking immediately.
- Otherwise, choose matching tools: overview_search for orientation (include one for hard
  or multi-aspect queries), search_corpus for semantic meaning, grep for exact tokens,
  filter_chunks for metadata.
- Do not wait for first results before choosing the initial diverse search set.
- Use at most 8 total tool calls in one turn, including retrieval,
  document and pruning tools.
- Follow-up searches should pivot to new evidence gaps, not shallow paraphrases; when a promising
  phrasing is exhausted, overview_search on it beats a paraphrase. Use get_chunks for exact
  already-seen chunks and read_document when nearby context around a chunk matters.
- You have at most 4 rounds (the final submit_ranking turn is one of them); from the second round on, a
  "Search round N of max 4." line marks which round the tool results above
  came from. It is a ceiling, not a quota. End the episode yourself: call
  submit_ranking in its own turn as soon as the evidence you have supports it, at latest in
  your final round. Extra rounds are not free; do not search on after the evidence is sufficient,
  and never wait to be told to submit.

RETRIEVAL:
- overview_search gives a wide preview: up to 50 unseen chunk summaries for
  one query in a single call. Use it to map themes, terminology, and files; when a good phrasing
  stops returning new search_corpus results, re-issue it to overview_search.
- search_corpus is for focused semantic search. Each call returns up to 5
  new unseen chunks. Use natural language, one meaning/aspect per query, and preserve exact user
  clues, entities, scene details, and relationships. Avoid Boolean syntax, regex, quoted-term
  operators, and keyword dumps.
- For semantic/open-ended or long-description aspects, call multiple search_corpus queries that
  chase different facets, entities, dates, settings, roles, or remembered wording.
- For broad-recall aspects, pair overview_search with multiple focused search_corpus calls; avoid
  relying on one generic query.
- Put hard structured constraints in filter_by; keep the semantic query about meaning. Use
  metadata-filtered searches only when facets or result metadata confirm the
  exact key, value, and format.
- Use filter_chunks for metadata-first list/category/status/date tasks. Default k=10; raise it
  only when the user asks for more or broader coverage is needed, max 30.
- Omit rank_by unless the task asks for numeric ordering and the field is confirmed
  numeric by facets or result metadata.
- Use grep for keywords, regex, exact tokens, codes, identifiers, function names, SKUs, or literal
  phrases. grep matches literal chunk/generated text, not meaning, and returns up to
  10 chunks.
- search_corpus and grep deduplicate already retrieved chunks. If the same focused query/pattern is still
  promising and needs more depth, repeat it; prefer a new focused variant when the evidence gap differs.

Context management:
- Every tool result arrives as <tool-result id="r7"> wrapping numbered spans <s id="r7:s1">,
  <s id="r7:s2">. Removed content leaves a marker in its place: text on either side of a marker
  is not continuous, and a span marked as continuing another may begin mid-sentence or mid-record.
- prune_context takes those ids and nothing else: pruning r7 removes the whole result, pruning
  r7:s2 removes that one span. chunk_id and document_id fetch content with get_chunks and
  read_document; they are not accepted here.
- prune_context removes content, not IDs. Pruned chunks stay in your seen index and will not be
  returned again from normal searches. Only get_chunks can restore pruned chunk content again.
- Call prune_context to remove content irrelevant to your user query. Keep the context
  window small; you have a limited token budget.
- Once you receive a context budget notice, include prune_context among your tool calls that round
  to drop content you no longer need, or call submit_ranking if you are done. prune_context may
  run in parallel with searches in the same turn, so a budget notice never has to cost a search --
  you do not need a prune-only turn. prune_context counts toward the 8 call
  limit; do not exceed that limit.
- prune_context must include at least one valid result id or span id.

EXAMPLES:
- "environmental and economic impact of solar energy" -> search_corpus with the original aspect
  plus diverse angles: lifecycle emissions, manufacturing impact, jobs/economy, land use/wildlife.
- Long remembered clip/scene description -> search_corpus with variants that preserve details,
  dates, setting, roles, and remembered wording.
- "articles by joe smith about Medicaid" -> use confirmed author/byline facets, then combine
  metadata-filtered semantic retrieval with any needed filter_chunks checks.

RANKING:
- Before submit_ranking, compare the retrieved chunks with each other. Rank for the user's intent,
  not just search_score.
- For metric/order requests, compare the relevant metadata field or value stated in content and
  order by the requested direction. Example: "highest spend ads" ranks by spend descending.
- submit_ranking.chunks must include all chunks relevant to the user query; rank most-relevant first;
  relevance_score in [0, 1]. Use an empty chunk list only if no relevant chunks exist.
- ranking_strategy must state the interpretation, constraints, comparison basis, and final ordering rule.
- Use only chunk_id values that appeared in your tool results. Do not duplicate chunk_id values.

OUTPUT RULES:
- USE TOOLS ONLY. Never generate a plain text response.
- Call submit_ranking when you have enough evidence.
- submit_ranking must be the only tool call in its turn.
- For audio/video chunks, trust the search score as the relevance signal (the full media is not available to you).

Runtime context:
- Current UTC date: 2026-09-04.
- Relative date queries use this UTC date unless the user gives another timezone; yesterday is 2026-09-03.
```

Variants the reference harness renders from the same template:

| Setting | Changes |
|---------|---------|
| `strict_top_k=True, top_k=N` | TASK says "report exactly N document chunks"; RANKING requires exactly N chunks and says to fill a weak tail with the next-best retrieved chunks; `submit_ranking` gets `minItems`/`maxItems` |
| `answer_mode="submit_ranking"` | TASK adds "and answer the query from the retrieved evidence"; `submit_ranking` gains a required `answer` string, and RANKING adds: "submit_ranking.answer must give your final answer to the user query, based only on retrieved evidence; if the evidence is insufficient to answer, say so" |
| `answer_mode="plain_text"` | No `submit_ranking`. Every "call submit_ranking" becomes "reply with your final answer"; RANKING/OUTPUT become: "To finish, reply with your final answer to the user query as a plain-text message with NO tool calls; a plain-text reply without tool calls ends the episode. Until you answer, every response must contain tool calls. Do not report chunk lists, chunk_id values, or rankings; deliver the answer itself." |
| `additional_instructions` | Appended under TASK as "ADDITIONAL INSTRUCTIONS:"; the rules below still win on conflict |

The served model honors these rules and calls `submit_ranking` on its own once the evidence suffices. Should a turn arrive without tool calls anyway, the reference harness treats it as invalid and corrects it once (`"Your previous response was invalid. Use tools only. Do not include plain text content."`), then forces `submit_ranking` by name with up to two more corrections; the loop in [python-loop.md](python-loop.md) forces at once instead.

## Signal context pressure to the model

The reference harness resends the full history and prunes it client-side; over the API, declared `context_management` gives the model the same `prune_context` tool server-side. For a stateless loop that keeps pruning on the client, this is the contract. The harness never prunes silently and never waits for the ceiling. The system prompt sets the contract before any pressure exists (the "Context management" block above). Every round past the trigger then carries a user message:

> Context budget notice: your current prompt is estimated at 63400 tokens, over your context budget. Include prune_context among your tool calls this round to remove content you no longer need -- it may run in parallel with other tools -- or call submit_ranking if you are done.

| Clause | Why it is there |
|--------|-----------------|
| A concrete token count | The model weighs a number against the evidence it holds; "running low" gives it nothing |
| The tool named | No inference required |
| "May run in parallel with other tools" | Without it the model burns a whole turn pruning and searching nothing |
| "Or call submit_ranking if you are done" | Finishing is the other correct response to pressure |
| Identical at every pressure level | Escalating wording teaches the model to wait for the loud version |

A round past the trigger with neither a prune nor a submission is recorded and scored — signaling pressure is worth nothing if nothing measures the response.

State the persistence rule, which differs by harness shape:

| Shape | Rule |
|-------|------|
| One-shot searcher | Pruned chunks stay in the seen index, never return from normal search; only expansion restores content |
| Multi-turn conversation | The prune list clears on the next user message, so pruned chunks may resurface as fresh results |

## Label rounds without instructing

From round 2 on, a bare marker follows the previous round's tool results:

```
Search round 2 of max 4.
```

"of max", not "of" — a bound the model may stop short of, not a quota. No instruction attached: a per-round nudge to submit teaches it to wait for the countdown instead of stopping when the evidence is sufficient.

## Other behaviors

| Behavior | Detail |
|----------|--------|
| Bootstrap | Metadata facets + one seed search on the original query, fetched concurrently before round 1 and inserted as labeled ordinary context in stable facets-then-search order; never as a synthetic assistant/tool exchange, and the round counter stays at zero |
| Spread truncation | Oversized calls truncate in presentation order, earlier results keep more, every item keeps a 512-token floor, nothing is deferred |
| Grep windows | ±100 tokens (of the harness's tokenizer) around **every** match, not a head clip |
| Expansion clip | 4× the search clip, so expansion is worth calling |
| Published bounds | "maximum 20 chunk ids" in the description; without it the model guesses and the call is rejected |
| Prefix stability | Runtime date is a UTC date, never a clock time; prompt-rendered scores rounded to 2 significant figures without mutating the results |
| Width over depth | Raise parallel calls before rounds — a round already costs its slowest call |
| Terminal failure | Append the assistant message, a tool error, and a correction naming the validation error; retry twice, then return no ranking |
| Metadata gating | Filters only from bootstrap facets, an inspection result, or metadata on retrieved results; numeric ranking only on confirmed numeric fields |
| Score comparison | Scores from different tools are not comparable — rank by intent and evidence, not raw score |
| Token counting | Exact counts from the policy tokenizer (`AGENT_HARNESS_TOKENIZER`); `chars / 4` only as an opt-in fallback |

## Numbers at a glance

| Knob | Value | Note |
|------|------:|------|
| Searcher rounds | 4 | Ceiling; submit turn included and may happen earlier |
| Parallel calls per round | 8 | Pruning counts toward it |
| Chunk clip, search tools | 2,000 tokens | |
| Chunk clip, expansion tools | 8,000 tokens | 4× search |
| Grep match window | ±100 tokens | Around every match |
| Per-call payload ceiling | 30,000 / 40,000 / 32,000 | Semantic / metadata listing / expansion; sized so a default-shaped call never clips |
| Prune trigger | 50,000 | Notice fires every round past it |
| Hard prompt ceiling | 100,000 tokens | Round payloads truncate to stay under |
| Per-round payload ceiling | 96,000 tokens | Effective bound is usually headroom |
| Minimum item allocation | 512 tokens | Floor under spread truncation |
| Terminal retries | 2 | Then fail explicitly |
