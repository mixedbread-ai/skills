# Python loop

A complete, runnable harness for toast-1 over the Chat Completions API in one file: bounded rounds, concurrent tool execution, stable handles, stored-completion continuation with declared `context_management`, the three answer modes, a validated `submit_ranking` terminal with bounded corrections, and an offline self-test. Two local tools — BM25 and regex grep over a directory of `.md`/`.txt` files — stand in for your backend.

```bash
pip install openai
python loop.py --selftest --corpus ./docs                                          # scripted client, no completions spent
MXBAI_API_KEY=... python loop.py --corpus ./docs "question"                         # plain_text: the prose reply is the answer
MXBAI_API_KEY=... python loop.py --answer-mode submit_ranking --corpus ./docs "question"   # ranked chunks + answer
MXBAI_API_KEY=... python loop.py --answer-mode none --corpus ./docs "question"             # ranked chunks only
MXBAI_API_KEY=... python loop.py --forget --corpus ./docs "question"                # delete the stored chain afterwards
```

Every request after the first names the previous completion as `previous_completion_id` and sends only the new messages — the tool results and the round label — so the conversation stays on the server, where the declared `context_management` lets the model prune tool results it no longer needs. The local `transcript` is a record, never resent. On the sample corpus every mode finishes in three generations: two search rounds, then the model's own `submit_ranking` call or its prose answer; the forced turn and its corrections are the round-cap fallback, exercised by the self-test.

## What to replace

| Part | Replace with |
|------|--------------|
| `load_corpus`, `BM25`, `Tools.bm25_search`, `Tools.grep`, `Tools.get_chunks` | Your backend. Keep the envelopes and route every result through `Evidence.show` so handles stay stable and deduplicated |
| `SYSTEM_PROMPT`, `OUTPUT_RULES` | Your task description. Keep the tool contracts, the round line, and one OUTPUT block per answer mode; the full production prompt is in [reference-harness.md](reference-harness.md) |
| `terminal_schema` / `validate_terminal` | Your payload. Keep the registry validation, the enum of visible handles, and the `require_answer` switch |
| `CONTEXT_MANAGEMENT`, the `previous_completion_id` chain | Keep both. A loop that must not store conversations sends `store=False`, resends the full transcript every request, and prunes it itself — see [reference-harness.md](reference-harness.md) for the budget notice |
| `MAX_ROUNDS`, `MAX_PARALLEL_CALLS`, `CLIP_CHARS` | Your budgets; the defaults are the reference harness's |

## The listing

```python
"""A bounded, parallel harness for toast-1 over the Chat Completions API, in one file.

Two local tools (BM25 and regex grep over a directory of text files) stand in
for your retrieval backend: replace their bodies in ``Tools`` and keep the rest.

    MXBAI_API_KEY=... python loop.py [--corpus DIR] [--answer-mode MODE] [--forget] "question"
    python loop.py --selftest      # scripted fake client; spends no completions

``openai`` is the only dependency. Every request after the first continues the
stored completion (``previous_completion_id``) and sends only the new messages;
declared ``context_management`` lets the model prune tool results it no longer
needs on the server, and the response reports what it cleared.
``--answer-mode`` picks the ending: ``plain_text`` (default) takes the model's
prose reply; ``submit_ranking`` a validated ``submit_ranking`` call carrying
ranked chunks and an ``answer``; ``none`` the same call with the ranking only.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import inspect
import itertools
import json
import math
import os
import re
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal, get_args, get_origin, get_type_hints

MODEL = "toast-1"
BASE_URL = "https://api.mixedbread.com/v1"
SAMPLING = {"temperature": 0.7, "top_p": 0.95}
CONTEXT_MANAGEMENT = {"edits": [{"type": "prune_context"}]}   # server-side prune_context over your tool results

MAX_ROUNDS = 4                 # generations per episode, the terminal turn included
MAX_PARALLEL_CALLS = 8         # tool calls honored per turn; the rest get an error
MAX_TERMINAL_RETRIES = 2       # corrections after an invalid forced terminal
TOP_K_MAX = 20
CLIP_CHARS = 8_000             # ~2,000 tokens per search result
EXPAND_CLIP_CHARS = 4 * CLIP_CHARS
TERMINAL = "submit_ranking"    # the trained name
ANSWER_MODES = ("plain_text", "submit_ranking", "none")   # prose / ranking + answer / ranking only

SYSTEM_PROMPT = f"""You are a search agent in a document retrieval pipeline. Gather evidence with the \
search tools, then finish.

TOOLS:
- bm25_search matches keywords: send keyword-heavy queries, not questions. It returns only \
chunks you have not seen.
- grep matches a regular expression against literal text: identifiers, codes, dates, phrases.
- get_chunks returns the full text of chunks you have already seen, by chunk_id.

WORKFLOW:
- Plan first, then fan out: up to {MAX_PARALLEL_CALLS} tool calls per turn that chase \
different aspects, entities and wording. Follow-ups pivot to what is still missing.
- You have at most {MAX_ROUNDS} rounds; the final turn is one of them. From the second round \
on, a "Search round N of max {MAX_ROUNDS}." line marks the round. It is a ceiling, not a quota.
"""
RANKING_RULES = f"""
OUTPUT:
- When the evidence is sufficient, call {TERMINAL} in its own turn: the relevant chunk_ids \
ranked most-relevant first with a relevance_score in [0, 1], and a ranking_strategy. Use only \
chunk_ids that appeared in tool results.
"""
RANKING_WITH_ANSWER_RULES = RANKING_RULES + """\
- Include answer: your final answer to the query, based only on retrieved evidence. If the \
evidence is insufficient, say so.
"""
PROSE_RULES = """
OUTPUT:
- When the evidence is sufficient, reply in plain text with no tool calls: the answer, \
based only on retrieved evidence. If the evidence is insufficient, say so.
"""
OUTPUT_RULES = {"none": RANKING_RULES, "submit_ranking": RANKING_WITH_ANSWER_RULES, "plain_text": PROSE_RULES}
FINAL_STRUCTURED = f"You have reached the search limit. Do NOT search further. Call {TERMINAL} now."
FINAL_PROSE = (
    "You have reached the search limit. Do NOT search further. You must now reply with your final "
    "answer to the user query as plain text, with NO tool calls. Base it only on retrieved "
    "evidence; if the evidence is insufficient to answer, say so."
)


# --- corpus and evidence registry -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str
    filename: str
    chunk_index: int
    text: str


def load_corpus(directory: Path) -> list[Chunk]:
    """One chunk per paragraph of every .md/.txt file; handles are minted once, in file order."""
    chunks: list[Chunk] = []
    for path in sorted(p for p in directory.iterdir() if p.suffix in (".md", ".txt")):
        heading, index = "", 0
        for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")):
            paragraph = block.strip()
            if not paragraph:
                continue
            if all(line.startswith("#") for line in paragraph.splitlines()):
                heading += paragraph + "\n"
                continue
            chunks.append(Chunk(f"c{len(chunks) + 1}", path.name, index, heading + paragraph))
            heading, index = "", index + 1
    return chunks


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class BM25:
    """Okapi BM25 over the chunks (k1 = 1.5, b = 0.75)."""

    def __init__(self, chunks: list[Chunk], *, k1: float = 1.5, b: float = 0.75) -> None:
        self._chunks, self._k1, self._b = chunks, k1, b
        self._counts = [Counter(tokenize(c.text)) for c in chunks]
        self._lengths = [sum(counts.values()) for counts in self._counts]
        self._avg = sum(self._lengths) / max(len(chunks), 1)
        df = Counter(term for counts in self._counts for term in counts)
        self._idf = {t: math.log(1 + (len(chunks) - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def search(self, query: str) -> list[tuple[Chunk, float]]:
        scored = []
        for chunk, counts, length in zip(self._chunks, self._counts, self._lengths, strict=True):
            norm = self._k1 * (1 - self._b + self._b * length / self._avg)
            score = sum(
                self._idf[t] * counts[t] * (self._k1 + 1) / (counts[t] + norm)
                for t in tokenize(query)
                if t in counts
            )
            if score > 0:
                scored.append((chunk, score))
        return sorted(scored, key=lambda hit: -hit[1])


@dataclass
class Evidence:
    """Stable handles: minted once per chunk identity, never reassigned, tracked as seen."""

    chunks: dict[str, Chunk]
    seen: dict[str, Chunk] = field(default_factory=dict)

    def visible_ids(self) -> list[str]:
        return list(self.seen)

    def show(self, chunk: Chunk, *, clip: int = CLIP_CHARS) -> dict[str, Any]:
        self.seen[chunk.chunk_id] = chunk
        text = chunk.text[:clip] + (" ...[truncated]" if len(chunk.text) > clip else "")
        return {"chunk_id": chunk.chunk_id, "filename": chunk.filename,
                "chunk_index": chunk.chunk_index, "text": text}


# --- tools: docstrings and Annotated hints are the schema the model reads --------------------


class Tools:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.evidence = Evidence({c.chunk_id: c for c in chunks})
        self._bm25 = BM25(chunks)
        self._chunks = chunks

    def by_name(self) -> dict[str, Callable[..., dict[str, Any]]]:
        return {t.__name__: t for t in (self.bm25_search, self.grep, self.get_chunks)}

    def bm25_search(
        self,
        query: Annotated[str, "Space-separated keywords, no questions, no boolean operators. "
                              "Example: 'firmware modbus tcp ethernet'"],
        top_k: Annotated[int, f"Number of chunks to return, max {TOP_K_MAX}."] = 5,
        mode: Annotated[Literal["chunks", "documents"],
                        "chunks ranks every chunk; documents keeps the best chunk per document."] = "chunks",
    ) -> dict[str, Any]:
        """Keyword-based BM25 search over the corpus. Matches keywords only: send
        keyword-heavy queries, not questions. Use for rare terms, names, codes and exact
        vocabulary; use grep for regular expressions and literal phrases. Returns up to
        top_k unseen chunks with stable chunk_id handles."""
        _check_top_k(top_k)
        hits = [(c, s) for c, s in self._bm25.search(query) if c.chunk_id not in self.evidence.seen]
        if mode == "documents":
            best: dict[str, tuple[Chunk, float]] = {}
            for chunk, score in hits:
                best.setdefault(chunk.filename, (chunk, score))
            hits = list(best.values())
        results = [{**self.evidence.show(c), "score": round(s, 2)} for c, s in hits[:top_k]]
        return {"query": query, "candidate_count": len(hits), "results": results}

    def grep(
        self,
        pattern: Annotated[str, "A regular expression in Python re syntax, case-insensitive."],
        top_k: Annotated[int, f"Number of chunks to return, max {TOP_K_MAX}."] = 10,
    ) -> dict[str, Any]:
        """Find chunks whose literal text matches a regular expression. No semantic
        matching: use it for exact tokens, identifiers, codes, dates and literal phrases;
        use bm25_search for keyword relevance. Chunks with the most matches come first,
        seen or not. Returns up to top_k chunks with stable chunk_id handles."""
        _check_top_k(top_k)
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"invalid regular expression: {exc}") from exc
        hits = sorted(((c, n) for c in self._chunks if (n := len(regex.findall(c.text)))),
                      key=lambda hit: -hit[1])
        results = [{**self.evidence.show(c), "match_count": n} for c, n in hits[:top_k]]
        return {"pattern": pattern, "candidate_count": len(hits), "results": results}

    def get_chunks(
        self,
        chunk_ids: Annotated[list[str], "chunk_id handles from earlier results, max 20."],
    ) -> dict[str, Any]:
        """Return the full text of chunks you have already seen, including pruned ones.
        Accepts only chunk_id handles that appeared in earlier tool results."""
        known = [i for i in chunk_ids[:20] if i in self.evidence.seen]
        unknown = [i for i in chunk_ids if i not in self.evidence.seen]
        results = [self.evidence.show(self.evidence.chunks[i], clip=EXPAND_CLIP_CHARS) for i in known]
        return {"results": results, "candidate_count": len(results), "unknown_ids": unknown}


def _check_top_k(top_k: int) -> None:
    if not isinstance(top_k, int) or not 1 <= top_k <= TOP_K_MAX:
        raise ValueError(f"top_k must be an integer between 1 and {TOP_K_MAX}, got {top_k!r}")


def tool_schema(tool: Callable[..., Any]) -> dict[str, Any]:
    """Function schema for ``tool``: docstring -> description, Annotated -> parameters."""
    hints = get_type_hints(tool, include_extras=True)
    properties, required = {}, []
    for name, parameter in inspect.signature(tool).parameters.items():
        hint, description = get_args(hints[name])[:2]
        properties[name] = {**_type_schema(hint), "description": description}
        if parameter.default is inspect.Parameter.empty:
            required.append(name)
        else:
            properties[name]["default"] = parameter.default
    return {"type": "function", "function": {
        "name": tool.__name__,
        "description": " ".join(inspect.cleandoc(tool.__doc__ or "").split()),
        "parameters": {"type": "object", "properties": properties, "required": required}}}


def _type_schema(hint: Any) -> dict[str, Any]:
    if get_origin(hint) is Literal:
        return {"type": "string", "enum": list(get_args(hint))}
    if get_origin(hint) is list:
        return {"type": "array", "items": _type_schema(get_args(hint)[0])}
    return {"type": {str: "string", int: "integer", float: "number", bool: "boolean"}[hint]}


def terminal_schema(visible_ids: list[str], *, require_answer: bool) -> dict[str, Any]:
    """The structured terminal, constrained to handles the model was shown."""
    properties: dict[str, Any] = {
        "chunks": {"type": "array", "maxItems": TOP_K_MAX, "items": {"type": "object", "properties": {
            "chunk_id": {"type": "string", "enum": visible_ids or ["none"]},
            "relevance_score": {"type": "number", "minimum": 0, "maximum": 1}},
            "required": ["chunk_id", "relevance_score"]}},
        "ranking_strategy": {"type": "string"}}
    required = ["chunks", "ranking_strategy"]
    deliverable = "the ranked evidence"
    if require_answer:                       # answer_mode="submit_ranking"
        properties["answer"] = {"type": "string", "description": "Your final answer to the query, "
                                "based only on retrieved evidence; if it is insufficient, say so."}
        required.append("answer")
        deliverable = "the ranked evidence and your answer"
    return {"type": "function", "function": {
        "name": TERMINAL,
        "description": f"Submit {deliverable} and end the search. Call it alone, never beside another tool.",
        "parameters": {"type": "object", "properties": properties, "required": required}}}


def validate_terminal(arguments: str, evidence: Evidence, *, require_answer: bool) -> dict[str, Any]:
    """Validate against the registry, never against the enum alone."""
    try:
        payload = json.loads(arguments or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"arguments are not valid JSON: {exc}") from exc
    chunks = payload.get("chunks")
    if not isinstance(chunks, list):
        raise ValueError("chunks must be a list")
    ids = [c.get("chunk_id") for c in chunks if isinstance(c, dict)]
    if unknown := [i for i in ids if i not in evidence.seen]:
        raise ValueError(f"unknown chunk_ids {unknown}; use only handles from tool results")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate chunk_ids")
    if any(not isinstance(c.get("relevance_score"), (int, float)) or not 0 <= c["relevance_score"] <= 1
           for c in chunks):
        raise ValueError("relevance_score must be a number in [0, 1]")
    if require_answer and (not isinstance(payload.get("answer"), str) or not payload["answer"].strip()):
        raise ValueError("answer must be a non-empty string")
    return payload


# --- the loop ------------------------------------------------------------------------------


@dataclass
class Episode:
    tools: Tools
    transcript: list[dict[str, Any]] = field(default_factory=list)   # local record; never resent
    completion_id: str | None = None                                  # the completion the next request continues
    context_edits: list[dict[str, Any]] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)


def user(content: str) -> dict[str, Any]:
    return {"role": "user", "content": content}


def tool_message(call: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, ensure_ascii=False)}


async def complete(client: Any, episode: Episode, new: list[dict[str, Any]], *,
                   tools: list[dict[str, Any]], tool_choice: Any) -> Any:
    """One request continuing the stored completion; only ``new`` messages are sent."""
    extension: dict[str, Any] = {"context_management": CONTEXT_MANAGEMENT}   # extension fields ride in extra_body
    if episode.completion_id is not None:
        extension["previous_completion_id"] = episode.completion_id
    response = await client.chat.completions.create(
        model=MODEL, messages=new, tools=tools, tool_choice=tool_choice,
        parallel_tool_calls=tool_choice == "auto", extra_body=extension, **SAMPLING)
    episode.completion_id = response.id                       # stored by default: the next request continues here
    choice = response.choices[0]
    applied = (getattr(response, "context_management", None) or {}).get("applied_edits") or []
    episode.context_edits.extend(applied)
    episode.trace.append({"finish_reason": choice.finish_reason,
                          "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                          "calls": [c.function.name for c in (choice.message.tool_calls or [])],
                          "pruned_tokens": sum(e.get("cleared_input_tokens", 0) for e in applied)})
    episode.transcript.extend([*new, choice.message.model_dump(exclude_none=True)])
    return choice


async def safe_execute(tools: Tools, call: Any) -> dict[str, Any]:
    """Every failure comes back as data; an exception here would break the next request."""
    tool = tools.by_name().get(call.function.name)
    if tool is None:
        return {"error": f"unknown tool {call.function.name}", "code": "unknown_tool", "retryable": True}
    try:
        arguments = json.loads(call.function.arguments or "{}")
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be a JSON object")
        return await asyncio.to_thread(tool, **arguments)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc), "code": "invalid_arguments", "retryable": True}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "code": "server_error", "retryable": True}


async def execute_round(tools: Tools, calls: list[Any]) -> list[dict[str, Any]]:
    """Run accepted calls concurrently; answer every call, in the model's order."""
    accepted, rejected = calls[:MAX_PARALLEL_CALLS], calls[MAX_PARALLEL_CALLS:]
    results = await asyncio.gather(*(safe_execute(tools, c) for c in accepted))
    errors = [{"error": f"round limit is {MAX_PARALLEL_CALLS} calls", "code": "parallel_call_limit_exceeded",
               "retryable": True} for _ in rejected]
    return [tool_message(call, result) for call, result in zip(calls, [*results, *errors], strict=True)]


def terminal_errors(calls: list[Any], error: str) -> list[dict[str, Any]]:
    return [tool_message(c, {"error": error, "code": "invalid_terminal", "retryable": True}) for c in calls]


async def run_episode(client: Any, query: str, *, corpus: Path, answer_mode: str = "plain_text") -> dict[str, Any]:
    if answer_mode not in ANSWER_MODES:
        raise ValueError(f"answer_mode must be one of {ANSWER_MODES}")
    structured = answer_mode != "plain_text"
    require_answer = answer_mode == "submit_ranking"
    tools = Tools(load_corpus(corpus))
    evidence = tools.evidence
    episode = Episode(tools)
    search_tools = [tool_schema(t) for t in tools.by_name().values()]
    new = [{"role": "system", "content": SYSTEM_PROMPT + OUTPUT_RULES[answer_mode]}, user(query)]

    for round_index in range(1, MAX_ROUNDS):            # the terminal turn is round MAX_ROUNDS
        if round_index > 1:
            new.append(user(f"Search round {round_index} of max {MAX_ROUNDS}."))
        terminal = [terminal_schema(evidence.visible_ids(), require_answer=require_answer)] if structured else []
        choice = await complete(client, episode, new, tools=[*search_tools, *terminal], tool_choice="auto")
        calls = list(choice.message.tool_calls or [])
        if structured and any(c.function.name == TERMINAL for c in calls):
            if len(calls) != 1:
                new = terminal_errors(calls, f"{TERMINAL} must be the only call in its turn")
                continue
            try:
                return _done(episode, validate_terminal(calls[0].function.arguments, evidence,
                                                        require_answer=require_answer))
            except ValueError as exc:
                new = terminal_errors(calls, str(exc))
                continue
        if not calls:                                    # prose: the model is done
            if not structured and choice.message.content:
                return _done(episode, {"answer": choice.message.content})
            new = []                                     # structured: force the terminal now
            break
        new = await execute_round(tools, calls)          # concurrent; one tool message per call

    return await finish(client, episode, new, answer_mode=answer_mode)


async def finish(client: Any, episode: Episode, new: list[dict[str, Any]], *, answer_mode: str) -> dict[str, Any]:
    """The terminal turn: prose with tools off, or the terminal forced by name. Bounded retries."""
    structured = answer_mode != "plain_text"
    require_answer = answer_mode == "submit_ranking"
    evidence = episode.tools.evidence
    search_tools = [tool_schema(t) for t in episode.tools.by_name().values()]
    new = [*new, user(FINAL_STRUCTURED if structured else FINAL_PROSE)]
    for attempt in range(1 + MAX_TERMINAL_RETRIES):
        if structured:
            choice = await complete(client, episode, new,
                                    tools=[terminal_schema(evidence.visible_ids(), require_answer=require_answer)],
                                    tool_choice={"type": "function", "function": {"name": TERMINAL}})
        else:
            choice = await complete(client, episode, new, tools=search_tools, tool_choice="none")
        calls = list(choice.message.tool_calls or [])
        if choice.finish_reason == "length":
            error = "the response was cut off by the output limit; answer more briefly"
        elif not structured:
            if (choice.message.content or "").strip() and not calls:
                return _done(episode, {"answer": choice.message.content})
            error = "reply with the answer as plain text and no tool calls"
        elif len(calls) == 1 and calls[0].function.name == TERMINAL:
            try:
                return _done(episode, validate_terminal(calls[0].function.arguments, evidence,
                                                        require_answer=require_answer))
            except ValueError as exc:
                error = str(exc)
        else:
            error = f"make exactly one {TERMINAL} call"
        new = terminal_errors(calls, error) if calls else []
        new.append(user(f"Your previous response was invalid: {error}. Try again."))
    raise RuntimeError(f"no valid ending after {MAX_TERMINAL_RETRIES} corrections")


def _done(episode: Episode, submission: dict[str, Any]) -> dict[str, Any]:
    return {**submission, "seen": episode.tools.evidence.visible_ids(), "completion_id": episode.completion_id,
            "context_edits": episode.context_edits, "trace": episode.trace, "transcript": episode.transcript}


# --- offline self-test: a scripted stand-in for chat.completions.create ---------------------


class Scripted:
    """Plays back responses; each item may be a callable of the request it answers."""

    def __init__(self, responses: list[Any]) -> None:
        self.requests: list[dict[str, Any]] = []
        self.responses: list[Any] = []
        self._responses = list(responses)
        self.chat = type("Chat", (), {})()
        self.chat.completions = type("Completions", (), {"create": self._create})()

    async def _create(self, **request: Any) -> Any:
        request = copy.deepcopy(request)           # snapshot: the loop reuses its lists
        self.requests.append(request)
        scripted = self._responses.pop(0)
        response = scripted(request) if callable(scripted) else scripted
        self.responses.append(response)
        return response


_ids = itertools.count(1)


def fake_response(*, content: str | None = None, calls: list[tuple[str, dict[str, Any]]] = (),
                  finish_reason: str | None = None, pruned_tokens: int = 0) -> Any:
    from types import SimpleNamespace as NS

    tool_calls = [NS(id=f"call_{i}", type="function",
                     function=NS(name=name, arguments=json.dumps(args))) for i, (name, args) in enumerate(calls)]
    message = NS(content=content, tool_calls=tool_calls or None,
                 model_dump=lambda exclude_none=False: {
                     "role": "assistant", **({"content": content} if content is not None else {}),
                     **({"tool_calls": [{"id": c.id, "type": "function", "function": {
                         "name": c.function.name, "arguments": c.function.arguments}} for c in tool_calls]}
                        if tool_calls else {})})
    edits = {"applied_edits": [{"type": "prune_context", "calls": 1, "cleared_input_tokens": pruned_tokens}]}
    return NS(id=f"chatcmpl_{next(_ids)}", context_management=edits if pruned_tokens else None,
              choices=[NS(finish_reason=finish_reason or ("tool_calls" if tool_calls else "stop"), message=message)],
              usage=NS(prompt_tokens=1000, completion_tokens=50))


async def selftest(corpus: Path) -> None:
    def first_handle(request: dict[str, Any]) -> str:
        for message in request["messages"]:
            if message["role"] == "tool":
                payload = json.loads(message["content"])
                if payload.get("results"):
                    return payload["results"][0]["chunk_id"]
        raise AssertionError("no results in the request")

    def tool_messages(request: dict[str, Any]) -> list[dict[str, Any]]:
        return [m for m in request["messages"] if m["role"] == "tool"]

    # ranking + answer: 10 calls (2 over the cap) -> terminal beside a search -> prose -> forced with 2 corrections
    handle: dict[str, str] = {}
    client = Scripted([
        fake_response(calls=[("bm25_search", {"query": "firmware modbus tcp", "top_k": 3}),
                             ("grep", {"pattern": "ETH-1"}),
                             ("grep", {"pattern": "("}),           # invalid regex -> error as data
                             *[("grep", {"pattern": "x"})] * 7]),  # 10 calls: the last 2 are rejected
        lambda r: fake_response(calls=[(TERMINAL, {"chunks": [{"chunk_id": handle.setdefault("c", first_handle(r)),
                                                               "relevance_score": 0.9}],
                                                   "ranking_strategy": "s", "answer": "a"}),
                                       ("grep", {"pattern": "y"})], pruned_tokens=900),
        fake_response(content="I think it is firmware 3.2."),
        fake_response(calls=[(TERMINAL, {"chunks": [{"chunk_id": "c999", "relevance_score": 0.9}],
                                         "ranking_strategy": "s", "answer": "a"})]),
        lambda r: fake_response(calls=[(TERMINAL, {"chunks": [{"chunk_id": handle["c"], "relevance_score": 0.9}],
                                                   "ranking_strategy": "s"})]),          # answer missing
        lambda r: fake_response(calls=[(TERMINAL, {"chunks": [{"chunk_id": handle["c"], "relevance_score": 0.9}],
                                                   "ranking_strategy": "top hit", "answer": "Firmware 3.2"})]),
    ])
    result = await run_episode(client, "Which firmware adds Modbus TCP?", corpus=corpus, answer_mode="submit_ranking")
    assert result["answer"] == "Firmware 3.2" and result["chunks"][0]["chunk_id"] in result["seen"]
    first, second = client.requests[0], client.requests[1]
    assert [m["role"] for m in first["messages"]] == ["system", "user"] and "store" not in first, "stored by default"
    assert first["extra_body"] == {"context_management": CONTEXT_MANAGEMENT}
    chained = [r["extra_body"].get("previous_completion_id") for r in client.requests]
    assert chained == [None, *(r.id for r in client.responses[:-1])], "each request continues the last completion"
    assert len(tool_messages(second)) == 10 and second["messages"][-1] == user("Search round 2 of max 4."), \
        "only the new messages: one tool message per emitted call, then the round label"
    assert "invalid regular expression" in tool_messages(second)[2]["content"]
    assert "parallel_call_limit_exceeded" in tool_messages(second)[-1]["content"]
    assert [m["role"] for m in result["transcript"][:4]] == ["system", "user", "assistant", "tool"]
    assert result["context_edits"] == [{"type": "prune_context", "calls": 1, "cleared_input_tokens": 900}]
    forced = client.requests[3]
    assert forced["tool_choice"]["function"]["name"] == TERMINAL and forced["tools"][0]["function"]["name"] == TERMINAL
    assert forced["messages"] == [user(FINAL_STRUCTURED)] and forced["parallel_tool_calls"] is False
    assert "answer" in forced["tools"][0]["function"]["parameters"]["required"]
    assert "unknown chunk_ids" in client.requests[4]["messages"][-2]["content"]
    assert "answer must be" in client.requests[5]["messages"][-2]["content"]
    assert [t["finish_reason"] for t in result["trace"]] == ["tool_calls"] * 2 + ["stop"] + ["tool_calls"] * 3

    # ranking only: the terminal carries no answer, and a payload without one validates
    client = Scripted([
        fake_response(calls=[("grep", {"pattern": "ETH-1"})]),
        lambda r: fake_response(calls=[(TERMINAL, {"chunks": [{"chunk_id": first_handle(r), "relevance_score": 0.8}],
                                                   "ranking_strategy": "grep hit"})]),
    ])
    result = await run_episode(client, "Where is ETH-1 mentioned?", corpus=corpus, answer_mode="none")
    assert "answer" not in result and result["chunks"][0]["relevance_score"] == 0.8
    schema = client.requests[1]["tools"][-1]["function"]
    assert schema["name"] == TERMINAL and "answer" not in schema["parameters"]["properties"]

    # prose: one search, then an answer; plus the length-cut ending on the forced turn
    client = Scripted([
        fake_response(calls=[("bm25_search", {"query": "ethernet module price"})]),
        fake_response(content="The ETH-1 module costs 240."),
    ])
    result = await run_episode(client, "What does the Ethernet module cost?", corpus=corpus, answer_mode="plain_text")
    assert result["answer"].startswith("The ETH-1") and client.requests[0]["tools"][0]["function"]["name"] == "bm25_search"
    assert result["transcript"][-1] == {"role": "assistant", "content": "The ETH-1 module costs 240."}
    client = Scripted([
        *[fake_response(calls=[("grep", {"pattern": "ETH"})])] * (MAX_ROUNDS - 1),
        fake_response(content="The ETH-1 module co", finish_reason="length"),
        fake_response(content="240."),
    ])
    result = await run_episode(client, "What does the Ethernet module cost?", corpus=corpus, answer_mode="plain_text")
    final, retry = client.requests[-2], client.requests[-1]
    assert [m["role"] for m in final["messages"]] == ["tool", "user"] and final["messages"][-1] == user(FINAL_PROSE)
    assert final["tool_choice"] == "none" and final["parallel_tool_calls"] is False and len(final["tools"]) == 3
    assert result["answer"] == "240." and retry["messages"] == [user(
        "Your previous response was invalid: the response was cut off by the output limit; answer more briefly. Try again.")]
    print("selftest OK")


# --- entry point ---------------------------------------------------------------------------


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?")
    parser.add_argument("--corpus", type=Path, default=Path("corpus"), help="a directory of .md/.txt files")
    parser.add_argument("--answer-mode", choices=ANSWER_MODES, default="plain_text")
    parser.add_argument("--forget", action="store_true", help="delete the stored completion chain afterwards")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        await selftest(args.corpus)
        return 0
    if not args.query:
        parser.error("a query is required unless --selftest")
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url=BASE_URL, api_key=os.environ["MXBAI_API_KEY"])
    result = await run_episode(client, args.query, corpus=args.corpus, answer_mode=args.answer_mode)
    if args.forget:                                            # chain-wide: every turn joined by previous_completion_id
        await client.delete(f"/chat/completions/{result['completion_id']}", cast_to=object)
    print(json.dumps({k: v for k, v in result.items() if k != "transcript"}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

## Reading the loop

| Where | What it does |
|-------|--------------|
| `ANSWER_MODES`, `OUTPUT_RULES` | `plain_text` (prose reply, no terminal), `submit_ranking` (terminal with a required `answer`), `none` (terminal with the ranking only). The mode selects the OUTPUT block of the prompt, whether the terminal is offered, and whether `answer` is in the schema and the validator |
| `run_episode` | Search rounds `1..MAX_ROUNDS-1` under `tool_choice="auto"`, the terminal offered in the two structured modes. `submit_ranking` alone in its turn ends the episode — the normal ending; beside other calls, or invalid, it gets a tool error per call and the round continues. No calls means prose: the answer under `plain_text`, otherwise straight to `finish` |
| `finish` | Round `MAX_ROUNDS`: prose with `tool_choice="none"` and the search tools still declared, or the terminal forced by name with nothing else declared. Two corrections for an invalid payload, a missing `answer`, an empty reply, or `finish_reason="length"`, then `RuntimeError` |
| `execute_round` | Concurrent execution of the first `MAX_PARALLEL_CALLS` calls, structured errors for the rest, one tool message per emitted call in the model's order — the whole payload of the next request |
| `complete` | Sends only the new messages with `previous_completion_id` and `context_management` in `extra_body`; `parallel_tool_calls` only under `auto`; records `finish_reason`, `prompt_tokens`, call names, and the tokens the server pruned (`context_management.applied_edits`); appends the sent messages and the assistant turn to the local transcript |
| `Scripted` / `fake_response` / `selftest` | The offline client and the assertions a harness should hold, one script per answer mode: stored by default and each request continuing the last, only the new messages sent, one tool message per call, over-cap calls rejected as data, invalid regex returned as data, applied edits collected, terminal forced by name at the cap with `parallel_tool_calls=False`, `answer` required only under `submit_ranking`, corrections after an unknown handle or a missing answer, the `length` recovery |
