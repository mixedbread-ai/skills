"""Optional Toast loop. Supply a search backend and a description of how to query it."""

import asyncio
import inspect
import json
import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    source: str = ""


@dataclass(frozen=True)
class Limits:
    rounds: int = 4  # includes the final turn; corrections are additional
    corrections: int = 2
    parallel: int = 8
    round_bytes: int = 24_000  # combined serialized tool content, not a token estimate
    top_k: int = 20
    timeout: float = 30


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def clip(text, limit):
    return text.encode("utf-8")[: max(0, limit)].decode("utf-8", errors="ignore")


@dataclass
class Evidence:
    seen: dict[str, Chunk] = field(default_factory=dict)

    def render(self, chunks, *, budget, expand=False):
        """Called serially after retrieval; register only results kept in the payload."""
        payload = {"results": [], "omitted": len(chunks)}
        kept = {}
        for index, chunk in enumerate(chunks):
            if chunk.chunk_id in kept or (not expand and chunk.chunk_id in self.seen):
                continue
            item = {"chunk_id": chunk.chunk_id, "text": "", "source": chunk.source, "truncated": True}
            candidate = {"results": [*payload["results"], item], "omitted": len(chunks) - len(kept) - 1}
            room = budget - len(encode(candidate).encode("utf-8"))
            # Prefer fewer useful passages; expansion spends more space on earlier IDs.
            share = max(8_192 if expand else 1_024, room // (len(chunks) - index))
            text = clip(chunk.text, min(room, share, 32_000 if expand else 8_000))
            while text:
                item.update(text=text, truncated=text != chunk.text)
                if len(encode(candidate).encode("utf-8")) <= budget:
                    break
                text = clip(text, len(text.encode("utf-8")) // 2)  # allow for JSON escaping
            if not text or len(text) < len(clip(chunk.text, 1_024)):
                continue
            payload = candidate
            kept[chunk.chunk_id] = chunk
        self.seen.update(kept)
        return encode(payload)


def function(name, description, properties, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def terminal_schema(require_answer, top_k):
    properties = {
        "chunks": {
            "type": "array",
            "maxItems": top_k,
            "items": {
                "type": "object",
                "properties": {
                    "chunk_id": {"type": "string"},
                    "relevance_score": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["chunk_id", "relevance_score"],
                "additionalProperties": False,
            },
        },
        "ranking_strategy": {"type": "string"},
    }
    if require_answer:
        properties["answer"] = {"type": "string", "minLength": 1}
    return function(
        "submit_ranking",
        "Finish with ranked evidence. Call this tool alone. "
        "Use known IDs without duplicates; ground any answer in retrieved evidence.",
        properties,
        ["chunks", *(["answer"] if require_answer else [])],
    )


def validate_terminal(arguments, evidence, *, require_answer, top_k):
    payload = json.loads(arguments)
    allowed = {"chunks", "ranking_strategy"} | ({"answer"} if require_answer else set())
    if not isinstance(payload, dict) or payload.keys() - allowed:
        raise ValueError("expected a terminal object with only the declared fields")
    chunks = payload.get("chunks")
    if not isinstance(chunks, list) or len(chunks) > top_k:
        raise ValueError(f"chunks must be a list with at most {top_k} items")
    ids = set()
    for chunk in chunks:
        if not isinstance(chunk, dict) or set(chunk) != {"chunk_id", "relevance_score"}:
            raise ValueError("each chunk needs chunk_id and relevance_score")
        handle, score = chunk["chunk_id"], chunk["relevance_score"]
        if not isinstance(handle, str) or handle not in evidence.seen or handle in ids:
            raise ValueError("use known chunk IDs without duplicates")
        if type(score) not in (int, float) or not 0 <= score <= 1 or not math.isfinite(score):
            raise ValueError("relevance_score must be a finite number in [0, 1]")
        ids.add(handle)
    if "ranking_strategy" in payload and not isinstance(payload["ranking_strategy"], str):
        raise ValueError("ranking_strategy must be a string when supplied")
    if require_answer and (not isinstance(payload.get("answer"), str) or not payload["answer"].strip()):
        raise ValueError("answer must be a non-empty string")
    return payload


def tool_message(call, content):
    return {"role": "tool", "tool_call_id": call.id, "content": content}


def error_content(message, budget):
    content = encode({"error": clip(message, max(0, (budget - 32) // 6))})
    return content if len(content.encode("utf-8")) <= budget else "{}"


async def execute_round(search, evidence, calls, limits):
    async def fetch(call):
        try:
            args = json.loads(call.function.arguments)
            if not isinstance(args, dict):
                raise TypeError("arguments must be an object")
            if call.function.name == "get_chunks":
                ids = args.get("chunk_ids")
                if set(args) != {"chunk_ids"} or not isinstance(ids, list) or not 1 <= len(ids) <= limits.top_k:
                    raise ValueError(f"chunk_ids must contain 1..{limits.top_k} known IDs")
                if any(not isinstance(i, str) or i not in evidence.seen for i in ids):
                    raise ValueError("unknown chunk ID; use IDs from earlier results")
                return [evidence.seen[i] for i in dict.fromkeys(ids)]
            if call.function.name != "search_corpus":
                raise ValueError("unknown tool")
            query, k = args.get("query"), args.get("top_k", min(5, limits.top_k))
            if args.keys() - {"query", "top_k"} or not isinstance(query, str) or not query.strip():
                raise ValueError("supply a non-empty query and optional top_k")
            if type(k) is not int or not 1 <= k <= limits.top_k:
                raise ValueError(f"top_k must be between 1 and {limits.top_k}")
            if inspect.iscoroutinefunction(search):
                hits = await search(query, k)
            else:
                hits = await asyncio.to_thread(search, query, k)
            if not isinstance(hits, list) or any(
                not isinstance(c, Chunk)
                or not isinstance(c.chunk_id, str)
                or not c.chunk_id
                or not isinstance(c.text, str)
                or not isinstance(c.source, str)
                for c in hits
            ):
                raise ValueError("backend must return a list of Chunk objects with stable string IDs")
            return hits[:k]
        except Exception as exc:  # noqa: BLE001 -- tool failures become protocol results
            return {"error": str(exc)}

    async def bounded(call):
        try:
            return await asyncio.wait_for(fetch(call), limits.timeout)
        except TimeoutError:
            return {"error": "retrieval timed out"}

    budget = limits.round_bytes // max(len(calls), 1)
    if budget < 32:
        raise RuntimeError("too many calls for the tool-result budget")
    values = await asyncio.gather(*(bounded(c) for c in calls[: limits.parallel]))
    values.extend({"error": "parallel call limit exceeded"} for _ in calls[limits.parallel :])
    messages = []
    for call, value in zip(calls, values, strict=True):
        content = (
            error_content(value["error"], budget)
            if isinstance(value, dict)
            else evidence.render(value, budget=budget, expand=call.function.name == "get_chunks")
        )
        messages.append(tool_message(call, content))
    return messages


async def run_episode(client, query, search, *, search_description, answer_mode="plain_text", limits=None):
    """Example policies: stored continuation, server pruning, duplicate rejection, bounded corrections."""
    limits = limits or Limits()
    if answer_mode not in ("plain_text", "none", "submit_ranking"):
        raise ValueError("answer_mode must be plain_text, none, or submit_ranking")
    if (
        limits.rounds < 1
        or limits.corrections < 0
        or limits.parallel < 1
        or limits.round_bytes < 256
        or limits.top_k < 1
        or limits.timeout <= 0
    ):
        raise ValueError("invalid limits")
    structured, require_answer = answer_mode != "plain_text", answer_mode == "submit_ranking"
    evidence, trace, previous, finishing, forced_attempts = Evidence(), [], None, False, 0
    search_tools = [
        function(
            "search_corpus",
            search_description,
            {
                "query": {"type": "string", "minLength": 1},
                "top_k": {"type": "integer", "minimum": 1, "maximum": limits.top_k, "default": min(5, limits.top_k)},
            },
            ["query"],
        ),
        function(
            "get_chunks",
            "Restore or expand previously retrieved chunks, in requested order. "
            "Request fewer IDs or concurrent calls for more context per chunk; some may be omitted to fit.",
            {"chunk_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": limits.top_k}},
            ["chunk_ids"],
        ),
    ]
    terminal = terminal_schema(require_answer, limits.top_k)
    ending = (
        "Call submit_ranking alone with known IDs, no duplicates, and scores in [0, 1]."
        if structured
        else "Finish with your answer in plain text and no tool calls."
    )
    if require_answer:
        ending += " Include your answer in the terminal payload."
    prompt = (
        f"Gather evidence for the query. Explore independent aspects in parallel, up to {limits.parallel} "
        f"calls per turn. You have at most {limits.rounds} turns including the final answer, "
        f"plus up to {limits.corrections} corrections. Finish early when evidence suffices. "
        "Search suppresses already shown chunks; get_chunks restores or expands them. "
        "Ground answers in retrieved evidence; acknowledge gaps. Rank by user intent, not raw search scores. " + ending
    )
    new = [{"role": "system", "content": prompt}, {"role": "user", "content": query}]
    for turn in range(limits.rounds + limits.corrections):
        forced = finishing or turn >= limits.rounds - 1
        if forced:
            forced_attempts += 1
            new.append({"role": "user", "content": "Finish now without further retrieval. " + ending})
        elif turn:
            new.append({"role": "user", "content": f"Search round {turn + 1} of max {limits.rounds}."})
        tools = ([terminal] if forced else [*search_tools, terminal]) if structured else search_tools
        choice = (
            ({"type": "function", "function": {"name": "submit_ranking"}} if structured else "none")
            if forced
            else "auto"
        )
        extra = {"context_management": {"edits": [{"type": "prune_context"}]}}
        if previous:
            extra["previous_completion_id"] = previous
        response = await client.chat.completions.create(
            model="toast-1",
            messages=new,
            tools=tools,
            tool_choice=choice,
            store=True,
            parallel_tool_calls=not forced,
            temperature=0.7,
            top_p=0.95,
            extra_body=extra,
        )
        previous = response.id
        result = response.choices[0]
        calls = list(result.message.tool_calls or [])
        trace.append(
            {
                "finish_reason": result.finish_reason,
                "usage": response.usage.model_dump() if response.usage else None,
                "context_management": (response.model_extra or {}).get("context_management"),
            }
        )
        retry_search = (
            not forced
            and result.finish_reason == "length"
            and bool(calls)
            and not any(c.function.name == "submit_ranking" for c in calls)
        )
        try:
            if result.finish_reason == "length":
                raise ValueError(
                    "response was cut off; retry with fewer or shorter tool calls"
                    if retry_search
                    else "response was cut off; produce a shorter final payload"
                )
            if result.finish_reason not in ("stop", "tool_calls"):
                raise ValueError("unexpected completion status")
            if structured and any(c.function.name == "submit_ranking" for c in calls):
                if len(calls) != 1:
                    raise ValueError("call submit_ranking alone")
                payload = validate_terminal(
                    calls[0].function.arguments, evidence, require_answer=require_answer, top_k=limits.top_k
                )
            elif (
                not structured
                and not calls
                and result.finish_reason == "stop"
                and (result.message.content or "").strip()
            ):
                payload = {"answer": result.message.content}
            elif not calls or forced:
                raise ValueError("supply the requested final answer")
            else:
                new = await execute_round(search, evidence, calls, limits)
                continue
            return {**payload, "evidence": dict(evidence.seen), "completion_id": previous, "trace": trace}
        except (ValueError, TypeError) as exc:
            budget = limits.round_bytes // max(len(calls), 1)
            if budget < 32:
                raise RuntimeError("too many calls for correction results") from exc
            new = [tool_message(c, error_content(str(exc), budget)) for c in calls]
            label = "Incomplete search turn" if retry_search else "Invalid ending"
            new.append({"role": "user", "content": f"{label}: {exc}. Correct it."})
            finishing = not retry_search
            if forced and forced_attempts > limits.corrections:
                break
    raise RuntimeError(f"no valid ending; last stored completion: {previous}")
