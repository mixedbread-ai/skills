# Python loop pattern

This pattern shows the search-model-specific control flow. Adapt tool implementations and endpoint configuration to the application.

## Contents

- [Completion call](#completion-call)
- [Async round executor](#async-round-executor)
- [Episode controller](#episode-controller)
- [Evidence registry invariants](#evidence-registry-invariants)

## Completion call

```python
import os

from openai import AsyncOpenAI


client = AsyncOpenAI(
    base_url="https://api.mixedbread.com/v1",
    api_key=os.environ["MXBAI_API_KEY"],
)

# Any name except `submit_answer`, which the endpoint reserves.
TERMINAL_TOOL_NAME = "report_evidence"


def terminal_tool_schema(visible_chunk_ids: list[str]) -> dict:
    """Harness terminal; define one only when the caller needs structured evidence."""
    return {
        "type": "function",
        "function": {
            "name": TERMINAL_TOOL_NAME,
            "description": (
                "Submit the complete evidence-grounded answer and end the episode. "
                "Call this exactly once and never beside another tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "Complete final answer ready to show to the user.",
                    },
                    "ranking_strategy": {
                        "type": "string",
                        "description": "How evidence relevance and constraints determined the order.",
                    },
                    "chunks": {
                        "type": "array",
                        "description": "Ranked evidence, most relevant first; do not pad weak results.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "chunk_id": {
                                    "type": "string",
                                    "enum": visible_chunk_ids,
                                },
                                "relevance_score": {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 1,
                                },
                            },
                            "required": ["chunk_id", "relevance_score"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["answer", "ranking_strategy", "chunks"],
                "additionalProperties": False,
            },
        },
    }


async def complete(
    messages: list[dict],
    tools: list[dict],
    *,
    final_round: bool = False,
    terminal_tool: dict | None = None,
):
    """Complete one round; `tools` contains only non-terminal client functions."""
    if any(
        tool.get("function", {}).get("name") == "submit_answer" for tool in tools
    ):
        raise ValueError("submit_answer is a reserved tool name")

    request = dict(
        model="toast-1",
        messages=messages,
        temperature=0.7,
        top_p=0.95,
        max_completion_tokens=4096,
        store=False,
    )
    if final_round and terminal_tool:
        request.update(
            tools=[terminal_tool],
            tool_choice={
                "type": "function",
                "function": {"name": TERMINAL_TOOL_NAME},
            },
            parallel_tool_calls=False,
        )
    elif not final_round:
        request.update(
            tools=[*tools, *([terminal_tool] if terminal_tool else [])],
            tool_choice="auto",
            parallel_tool_calls=True,
        )

    # A prose-only final round intentionally omits tools and tool_choice.
    return await client.chat.completions.create(**request)
```

Every retrieval tool is a client-executed `function` the harness runs itself. Pass only non-terminal schemas in `tools` and let `complete()` attach the terminal.

Two facts shape the terminal design:

- `submit_answer` is a reserved tool name: declaring it fails the request with HTTP 422 (`'submit_answer' is reserved`). Name the harness terminal anything else; `TERMINAL_TOOL_NAME` above exists so the schema, the reminder text, and the executor cannot drift apart.
- The model's default prose ending is ordinary assistant text, so a prose-only run never arrives as a `tool_call`. A controller that recognizes only tool terminals will exhaust its round budget and fall through to the failure branch. Treat a `finish_reason="stop"` message with `content` as the prose ending; when a structured terminal is offered and selected as the only call, accept it on any round.

Before calling `complete(..., final_round=True)`, append the final-round instruction to the controller's persistent history; do not add it to a request-local copy that disappears before a correction attempt. When the deliverable is prose, pass `terminal_tool=None` and omit `tools`, `tool_choice`, and `parallel_tool_calls` entirely; do not send `tools=[]` with `tool_choice="none"`, because OpenAI-compatible backends may reject that combination. When the caller needs ranked evidence, pass a terminal schema built from currently visible evidence IDs — and force it by name on the final round. Named forcing is not optional: prompt instructions alone lose to a plain prose ending most of the time, and `tool_choice="required"` still returns assistant text with no visible call.

Mixedbread's completion service keeps thinking disabled. If a harness also targets a self-hosted copy of the checkpoint, preserve that behavior explicitly there:

```python
extra_body={
    "chat_template_kwargs": {
        "enable_thinking": False,
        "preserve_thinking": False,
    }
}
```

Do not pass process policy such as `max_rounds`, pruning thresholds, or retry counts as model sampling fields.

The model is served at a sequence length of 131,072 tokens and generation is capped at 4,096 per completion, so `max_completion_tokens` above 4,096 buys nothing. Keep each request's input under ~130,000: the reservation still comes out of the same sequence budget, and a prompt that fits with 4,096 reserved can fail once the reservation grows.

Overflow returns an opaque HTTP 500 rather than a context-length error, so the controller cannot detect it after the fact — hold a ceiling with real headroom and clip round payloads into it.

## Async round executor

```python
import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


MAX_ROUNDS = 4                 # terminal round included
MAX_TERMINAL_CORRECTIONS = 2   # retries after the first failed ending
MAX_PARALLEL_CALLS = 8
PRUNE_REMINDER_TOKENS = 50_000
HARD_PROMPT_TOKENS = 100_000
MODEL_SEQUENCE_TOKENS = 131_072  # served sequence length; keep input under ~130k
RESERVED_OUTPUT_TOKENS = 4_096  # subtracted from the prompt ceiling

# The harness owns pruning; Mixedbread ships no pruning tool. Name it whatever
# suits the domain and keep the name consistent across the schema, the reminder,
# and the executor.
PRUNE_TOOL_NAME = "discard_evidence"

ToolFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class Episode:
    messages: list[dict[str, Any]]
    tools: dict[str, ToolFn]
    evidence: "EvidenceRegistry"
    trace: list[dict[str, Any]] = field(default_factory=list)


async def safe_execute(name: str, arguments: str, fn: ToolFn) -> dict[str, Any]:
    try:
        parsed = json.loads(arguments or "{}")
        if not isinstance(parsed, dict):
            raise ValueError("arguments must be a JSON object")
        result = await fn(parsed)
        return result if isinstance(result, dict) else {"error": "tool must return an object"}
    except ValueError as exc:
        return {"error": str(exc), "code": "invalid_arguments", "retryable": True}
    except PermissionError as exc:
        return {"error": str(exc), "code": "permission_denied", "retryable": False}
    except Exception as exc:
        return {"error": str(exc), "code": "server_error", "retryable": True}


async def execute_round(episode: Episode, calls: list[Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any] | None] = [None] * len(calls)
    executable: list[tuple[int, Any, ToolFn]] = []

    for index, call in enumerate(calls):
        name = call.function.name
        if index >= MAX_PARALLEL_CALLS:
            results[index] = {
                "error": f"round limit is {MAX_PARALLEL_CALLS} calls",
                "code": "parallel_call_limit_exceeded",
                "retryable": True,
            }
            continue

        fn = episode.tools.get(name)
        if fn is None:
            results[index] = {
                "error": f"unknown tool: {name}",
                "code": "unknown_tool",
                "retryable": True,
            }
            continue

        executable.append((index, call, fn))

    executed = await asyncio.gather(
        *[
            safe_execute(call.function.name, call.function.arguments, fn)
            for _, call, fn in executable
        ]
    )
    for (index, _, _), result in zip(executable, executed, strict=True):
        results[index] = result

    # Emit exactly one tool message per model call, including rejected calls.
    tool_messages = []
    for call, result in zip(calls, results, strict=True):
        if result is None:
            raise AssertionError("missing tool result")
        tool_messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
            }
        )
    return tool_messages
```

Keep every emitted call in the assistant transcript and return one matching tool message for each. Execute known calls only within the first `MAX_PARALLEL_CALLS` emitted positions; represent excess and unknown calls as structured errors so the next completion request remains protocol-valid and the model can recover.

## Episode controller

Fetch bootstrap facets and seed results before entering the controller loop. Register retained seed evidence before presenting it, then put the bootstrap payloads in an ordinary user-context message, not in synthetic assistant tool calls or `role="tool"` messages. Bootstrap is pre-round context, so the first completion still has `attempt_index == 0`.

```python
def build_initial_messages(
    query: str,
    metadata_facets: dict[str, Any],
    seed_results: list[dict[str, Any]],
) -> list[dict[str, str]]:
    bootstrap = {
        "metadata_facets": metadata_facets,
        "seed_search_results": seed_results,
    }
    return [
        {
            "role": "user",
            "content": (
                f"User query:\n{query}\n\n"
                "Pre-round bootstrap context follows. It was fetched before search "
                "round 1, is not a tool result, and consumes no search round.\n"
                f"{json.dumps(bootstrap, ensure_ascii=False)}"
            ),
        }
    ]


def final_round_message(structured_terminal: bool) -> dict[str, str]:
    instruction = (
        "Make exactly one terminal call with no other or parallel calls."
        if structured_terminal
        else "Return the final answer now."
    )
    return {
        "role": "user",
        "content": (
            "You have reached the search limit. Do not search further. "
            f"{instruction}"
        ),
    }


def terminal_error_messages(message: Any, calls: list[Any], error: str) -> list[dict[str, Any]]:
    """Keep a rejected terminal turn protocol-complete for a correction request."""
    return [
        message.model_dump(exclude_none=True),
        *[
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(
                    {
                        "error": error,
                        "code": "invalid_terminal",
                        "retryable": True,
                    }
                ),
            }
            for call in calls
        ],
    ]


async def run_episode(query: str, *, structured_terminal: bool = False) -> dict[str, Any]:
    metadata_facets, seed_results = await asyncio.gather(
        fetch_metadata_facets(query),
        seed_search(query),
    )
    evidence = EvidenceRegistry()
    seed_results = budget_and_register_bootstrap(seed_results, evidence)
    episode = Episode(
        messages=build_initial_messages(query, metadata_facets, seed_results),
        tools=tool_implementations(),
        evidence=evidence,
    )

    force_terminal = False
    terminal_corrections = 0

    for attempt_index in range(MAX_ROUNDS + MAX_TERMINAL_CORRECTIONS):
        final_round = force_terminal or attempt_index == MAX_ROUNDS - 1

        # Persist the instruction that this response answers. If the response is
        # invalid, replaying it with the assistant/tool messages keeps role order
        # valid for the next correction request.
        if final_round:
            episode.messages.append(final_round_message(structured_terminal))

        token_count = estimate_prompt_tokens(episode.messages)
        if token_count >= PRUNE_REMINDER_TOKENS and not final_round:
            episode.messages.append(
                {
                    "role": "user",
                    "content": (
                        "Context budget notice: your current prompt is estimated at "
                        f"{token_count} tokens, over your context budget. Include "
                        f"{PRUNE_TOOL_NAME} among your tool calls this round to remove content "
                        "you no longer need -- it may run in parallel with other tools -- "
                        "or submit if done."
                    ),
                }
            )
        if token_count >= HARD_PROMPT_TOKENS:
            prune_stale_tool_payloads(episode.messages, episode.evidence)

        # Build only non-terminal client schemas; complete() attaches the terminal.
        schemas = build_tool_schemas(episode.evidence)
        terminal_tool = (
            terminal_tool_schema(episode.evidence.visible_chunk_ids())
            if structured_terminal
            else None
        )
        response = await complete(
            episode.messages,
            schemas,
            final_round=final_round,
            terminal_tool=terminal_tool,
        )
        choice = response.choices[0]
        message = choice.message
        calls = list(message.tool_calls or [])
        episode.trace.append(trace_turn(attempt_index, response))

        terminal_calls = [call for call in calls if call.function.name == TERMINAL_TOOL_NAME]
        if structured_terminal and terminal_calls:
            if len(calls) != 1:
                episode.messages.extend(
                    terminal_error_messages(
                        message,
                        calls,
                        f"{TERMINAL_TOOL_NAME} must be the only call in its turn",
                    )
                )
                terminal_corrections += 1
                if terminal_corrections > MAX_TERMINAL_CORRECTIONS:
                    break
                force_terminal = True
                continue
            try:
                submission = validate_terminal(terminal_calls[0], episode.evidence)
            except (TypeError, ValueError) as exc:
                episode.messages.extend(
                    terminal_error_messages(message, calls, str(exc))
                )
                terminal_corrections += 1
                if terminal_corrections > MAX_TERMINAL_CORRECTIONS:
                    break
                force_terminal = True
                continue
            return {"submission": submission, "trace": episode.trace}

        if not calls:
            # A finished run arrives as assistant text, never as a tool call.
            if not structured_terminal and choice.finish_reason == "stop" and message.content:
                return {"answer": message.content, "trace": episode.trace}
            if structured_terminal and choice.finish_reason == "stop" and message.content:
                # The model considers itself done but answered in prose. Force the
                # structured terminal instead of accepting an unstructured answer.
                # This failed ending consumes the same bounded correction budget as
                # an invalid terminal payload.
                episode.messages.append(message.model_dump(exclude_none=True))
                terminal_corrections += 1
                if terminal_corrections > MAX_TERMINAL_CORRECTIONS:
                    break
                force_terminal = True
                continue
            if final_round:
                episode.messages.append(message.model_dump(exclude_none=True))
                terminal_corrections += 1
                if terminal_corrections > MAX_TERMINAL_CORRECTIONS:
                    break
                force_terminal = True
            continue

        if final_round:
            episode.messages.extend(
                terminal_error_messages(
                    message,
                    calls,
                    "final correction turns may contain only the terminal call",
                )
            )
            terminal_corrections += 1
            if terminal_corrections > MAX_TERMINAL_CORRECTIONS:
                break
            force_terminal = True
            continue

        episode.messages.append(message.model_dump(exclude_none=True))
        tool_messages = await execute_round(episode, calls)
        tool_messages = budget_and_register(tool_messages, episode.evidence)
        if len(tool_messages) != len(calls):
            raise AssertionError("budgeting must preserve one message per tool call")
        episode.messages.extend(tool_messages)

    raise RuntimeError("the model did not produce a valid terminal after bounded corrections")
```

Every tool call returns as `finish_reason="tool_calls"`, and the next API request must replay the assistant message plus one matching tool message per call.

Leave `structured_terminal` off when the user-ready answer is the artifact; the model supplies it as text. Turn it on when the caller needs validated evidence IDs, scores, or any other structured payload. The terminal remains available on every retrieval round and may end the episode early. If the model instead ends in prose, the harness records that assistant message, charges it against the bounded correction budget, appends a persistent user correction, and forces the terminal rather than accepting unstructured output.

## Evidence registry invariants

Implement these invariants even if the surrounding class differs:

- Allocate one short handle per corpus chunk identity and never reassign it.
- Deduplicate ordinary search results against the agent's seen set before returning them.
- Clip text before serializing the tool result.
- Clip or replace oversized tool-message content, but never drop the message envelope for an emitted call.
- Register only results actually kept after round-budget truncation.
- Mark pruned evidence separately from unseen/discarded evidence.
- Expose currently visible chunk IDs so each terminal schema can constrain submissions to evidence the model was shown.
- Allow the chunk-expansion tool to restore pruned content, but reject unknown handles.
- Build the terminal's `chunk_id` enum from IDs the model was shown, and still validate the submission against the registry.
- Resolve the final ranking strictly from the registry; do not replace an invalid or missing submission with search-score order.
