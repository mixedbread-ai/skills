"""Offline regression checks for the optional harness example."""

import asyncio
import copy
import importlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/mixedbread-search-agent-harness/scripts"))
from keyword_search import KeywordSearch
from search_loop import (
    Chunk,
    Evidence,
    Limits,
    execute_round,
    run_episode,
    validate_terminal,
)


def reply(content=None, calls=(), reason=None):
    tools = [
        NS(id=f"call_{i}", function=NS(name=name, arguments=args if isinstance(args, str) else json.dumps(args)))
        for i, (name, args) in enumerate(calls)
    ]
    return NS(
        choices=[
            NS(
                message=NS(content=content, tool_calls=tools),
                finish_reason=reason or ("tool_calls" if tools else "stop"),
            )
        ],
        usage=NS(model_dump=lambda: {"prompt_tokens": 100, "completion_tokens": 20}),
        model_extra={},
    )


class Scripted:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []
        self.chat = NS(completions=NS(create=self.create))

    async def create(self, **request):
        self.requests.append(copy.deepcopy(request))
        response = next(self.responses)
        response.id = f"completion_{len(self.requests)}"
        return response


class LoopTests(unittest.IsolatedAsyncioTestCase):
    async def run_example(self, client, mode="plain_text", **kwargs):
        return await run_episode(
            client,
            "question",
            lambda query, k: [Chunk("c1", "evidence", "doc")],
            search_description="Search the configured corpus.",
            answer_mode=mode,
            **kwargs,
        )

    async def test_incomplete_and_blank_prose_are_corrected(self):
        for first in (reply("cut off", reason="length"), reply("   "), reply()):
            with self.subTest(first=first):
                client = Scripted([first, reply("complete answer")])
                result = await self.run_example(client)
                self.assertEqual(result["answer"], "complete answer")
                self.assertEqual(len(client.requests), 2)
                self.assertEqual(client.requests[1]["tool_choice"], "none")

    async def test_three_modes_and_stored_continuation(self):
        for mode in ("plain_text", "none", "submit_ranking"):
            with self.subTest(mode=mode):
                payload = {"chunks": [{"chunk_id": "c1", "relevance_score": 0.9}]}
                if mode == "submit_ranking":
                    payload["answer"] = "grounded answer"
                end = reply("grounded answer") if mode == "plain_text" else reply(calls=[("submit_ranking", payload)])
                client = Scripted([reply(calls=[("search_corpus", {"query": "evidence"})]), end])
                result = await self.run_example(client, mode)
                self.assertIn("c1", result["evidence"])
                self.assertEqual(client.requests[1]["extra_body"]["previous_completion_id"], "completion_1")
                self.assertEqual([m["role"] for m in client.requests[1]["messages"]], ["tool", "user"])
                for request in client.requests:
                    self.assertTrue(request["store"])
                    self.assertEqual(
                        request["extra_body"]["context_management"], {"edits": [{"type": "prune_context"}]}
                    )

    async def test_truncated_search_can_recover_before_the_cap(self):
        searches = []

        def search(query, k):
            searches.append(query)
            return [Chunk("c1", "The renewal agreement expires in 2027.")]

        for mode in ("plain_text", "none", "submit_ranking"):
            with self.subTest(mode=mode):
                searches.clear()
                payload = {"chunks": [{"chunk_id": "c1", "relevance_score": 0.9}]}
                if mode == "submit_ranking":
                    payload["answer"] = "The agreement expires in 2027."
                end = (
                    reply("The agreement expires in 2027.")
                    if mode == "plain_text"
                    else reply(calls=[("submit_ranking", payload)])
                )
                client = Scripted(
                    [
                        reply(
                            calls=[("search_corpus", {"query": "first"}), ("search_corpus", '{"query":"cut')],
                            reason="length",
                        ),
                        reply(calls=[("search_corpus", {"query": "renewal"})]),
                        end,
                    ]
                )
                result = await run_episode(
                    client, "When does it expire?", search, search_description="Search agreements.", answer_mode=mode
                )
                self.assertEqual(searches, ["renewal"])
                self.assertIn("c1", result["evidence"])
                self.assertEqual(client.requests[1]["tool_choice"], "auto")
                self.assertEqual(
                    [m["tool_call_id"] for m in client.requests[1]["messages"] if m["role"] == "tool"],
                    ["call_0", "call_1"],
                )

    async def test_truncated_search_does_not_extend_the_search_budget(self):
        client = Scripted([reply(calls=[("search_corpus", '{"query":"cut')], reason="length") for _ in range(4)])
        with self.assertRaisesRegex(RuntimeError, "no valid ending"):
            await self.run_example(client, limits=Limits(rounds=3, corrections=1))
        self.assertEqual([r["tool_choice"] for r in client.requests], ["auto", "auto", "none", "none"])

    async def test_malformed_and_truncated_terminals_are_corrected(self):
        for first in (
            reply(calls=[("submit_ranking", "[]")]),
            reply(calls=[("submit_ranking", "{broken")]),
            reply(calls=[("submit_ranking", {"chunks": []})], reason="length"),
        ):
            with self.subTest(first=first):
                client = Scripted([first, reply(calls=[("submit_ranking", {"chunks": []})])])
                result = await self.run_example(client, "none")
                self.assertEqual(result["chunks"], [])
                self.assertEqual(client.requests[1]["messages"][0]["tool_call_id"], "call_0")
                self.assertEqual(client.requests[1]["tool_choice"]["function"]["name"], "submit_ranking")

    async def test_cap_and_corrections_are_bounded(self):
        client = Scripted([reply(calls=[("search_corpus", {"query": "evidence"})]), reply(" "), reply(" ")])
        with self.assertRaisesRegex(RuntimeError, "no valid ending"):
            await self.run_example(client, limits=Limits(rounds=2, corrections=1))
        self.assertEqual(len(client.requests), 3)
        self.assertEqual(client.requests[1]["tool_choice"], "none")

    async def test_parallel_retrieval_deduplicates_after_join(self):
        arrived = 0
        ready = asyncio.Event()

        async def search(query, k):
            nonlocal arrived
            arrived += 1
            if arrived == 2:
                ready.set()
            await ready.wait()
            return [Chunk("same", "shared evidence")]

        calls = (
            reply(calls=[("search_corpus", {"query": "a"}), ("search_corpus", {"query": "b"})])
            .choices[0]
            .message.tool_calls
        )
        evidence = Evidence()
        messages = await execute_round(search, evidence, calls, Limits())
        self.assertEqual(arrived, 2)
        self.assertEqual([m["tool_call_id"] for m in messages], ["call_0", "call_1"])
        self.assertEqual(sum(len(json.loads(m["content"])["results"]) for m in messages), 1)

    async def test_aggregate_expansion_budget_and_restoration(self):
        chunks = [Chunk(f"c{i}", "multi-byte evidence 🥖 " * 3000) for i in range(20)]
        evidence = Evidence({c.chunk_id: c for c in chunks})  # previously presented, possibly pruned
        calls = reply(calls=[("get_chunks", {"chunk_ids": list(evidence.seen)})] * 8).choices[0].message.tool_calls
        messages = await execute_round(None, evidence, calls, Limits())
        self.assertLessEqual(sum(len(m["content"].encode("utf-8")) for m in messages), 24_000)
        self.assertTrue(all(json.loads(m["content"])["results"] for m in messages))
        self.assertEqual(len(evidence.seen), 20)

    async def test_wide_search_keeps_useful_passages_and_leaves_dropped_hits_unseen(self):
        def search(query, k):
            return [Chunk(f"{query}:{i}", "Useful evidence about the renewal agreement. " * 1000) for i in range(k)]

        calls = (
            reply(calls=[("search_corpus", {"query": str(i), "top_k": 20}) for i in range(8)])
            .choices[0]
            .message.tool_calls
        )
        evidence = Evidence()
        messages = await execute_round(search, evidence, calls, Limits())
        results = [item for m in messages for item in json.loads(m["content"])["results"]]
        self.assertLessEqual(sum(len(m["content"].encode("utf-8")) for m in messages), 24_000)
        self.assertTrue(all(json.loads(m["content"])["results"] for m in messages))
        self.assertLess(len(results), 160)
        self.assertTrue(all(len(item["text"].encode("utf-8")) >= 1024 for item in results))
        self.assertEqual(set(evidence.seen), {item["chunk_id"] for item in results})
        dropped = next(c for c in search("0", 20) if c.chunk_id not in evidence.seen)
        later = json.loads(evidence.render([dropped], budget=3000))
        self.assertEqual(later["results"][0]["chunk_id"], dropped.chunk_id)

    async def test_multi_chunk_expansion_provides_additional_context(self):
        chunks = [Chunk(f"c{i}", "evidence " * 3000) for i in range(5)]
        evidence = Evidence()
        search_calls = reply(calls=[("search_corpus", {"query": "renewal", "top_k": 5})]).choices[0].message.tool_calls
        searched = await execute_round(lambda query, k: chunks, evidence, search_calls, Limits())
        first = {c["chunk_id"]: c["text"] for c in json.loads(searched[0]["content"])["results"]}
        self.assertEqual(len(first), 5)
        calls = reply(calls=[("get_chunks", {"chunk_ids": list(first)})]).choices[0].message.tool_calls
        expanded = await execute_round(None, evidence, calls, Limits())
        payload = json.loads(expanded[0]["content"])
        self.assertTrue(payload["results"])
        self.assertGreater(payload["omitted"], 0)
        for chunk in payload["results"]:
            self.assertGreater(len(chunk["text"]), len(first[chunk["chunk_id"]]))
            self.assertTrue(chunk["text"].startswith(first[chunk["chunk_id"]]))
        self.assertLessEqual(len(expanded[0]["content"].encode("utf-8")), 24_000)

    async def test_errors_and_rejected_calls_get_results(self):
        calls = (
            reply(
                calls=[
                    ("search_corpus", {"query": []}),
                    ("unknown", {}),
                    ("get_chunks", {"chunk_ids": ["missing"]}),
                    ("search_corpus", {"query": "rejected"}),
                ]
            )
            .choices[0]
            .message.tool_calls
        )
        messages = await execute_round(None, Evidence(), calls, Limits(parallel=3))
        self.assertEqual(len(messages), 4)
        self.assertTrue(all("error" in json.loads(m["content"]) for m in messages))
        self.assertIn("parallel call limit", messages[-1]["content"])

    @unittest.skipUnless(importlib.util.find_spec("openai"), "optional OpenAI SDK is not installed")
    async def test_real_sdk_with_mock_transport(self):
        import openai

        # Follow the SDK's HTTP client module across supported SDK releases.
        http = importlib.import_module(openai.DefaultAsyncHttpxClient.__mro__[1].__module__.split(".")[0])
        requests = []

        def respond(request):
            requests.append(json.loads(request.content))
            message = {"role": "assistant", "content": "Complete grounded answer."}
            if len(requests) == 1:
                message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "lookup",
                            "type": "function",
                            "function": {"name": "search_corpus", "arguments": '{"query":"evidence"}'},
                        }
                    ],
                }
            return http.Response(
                200,
                json={
                    "id": f"sdk_{len(requests)}",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "toast-1",
                    "choices": [
                        {
                            "index": 0,
                            "message": message,
                            "finish_reason": "tool_calls" if len(requests) == 1 else "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
                    "context_management": {"applied_edits": [{"type": "prune_context", "cleared_input_tokens": 20}]},
                },
            )

        async with openai.AsyncOpenAI(
            base_url="https://example.test/v1",
            api_key="test-key",
            http_client=openai.DefaultAsyncHttpxClient(transport=http.MockTransport(respond)),
        ) as client:
            result = await self.run_example(client)
        self.assertEqual(result["answer"], "Complete grounded answer.")
        self.assertEqual(requests[1]["previous_completion_id"], "sdk_1")
        self.assertEqual(requests[1]["messages"][0]["tool_call_id"], "lookup")
        self.assertIn("context_management", requests[1])
        self.assertEqual(result["trace"][1]["context_management"]["applied_edits"][0]["cleared_input_tokens"], 20)


class EvidenceTests(unittest.TestCase):
    def test_serialized_budget_handles_escaping_and_short_complete_chunks(self):
        evidence = Evidence()
        chunks = [Chunk("long", '🥖 "quoted" \\text\n' * 3000), Chunk("short", "A complete short fact.")]
        body = evidence.render(chunks, budget=3000)
        self.assertLessEqual(len(body.encode("utf-8")), 3000)
        results = {c["chunk_id"]: c for c in json.loads(body)["results"]}
        self.assertTrue(results["long"]["truncated"])
        self.assertEqual(results["short"]["text"], chunks[1].text)
        self.assertFalse(results["short"]["truncated"])

    def test_discarded_results_stay_unseen(self):
        evidence = Evidence()
        body = evidence.render(
            [Chunk("discarded", "text", "large source " * 1000), Chunk("kept", "useful text")], budget=1024
        )
        self.assertEqual(list(evidence.seen), ["kept"])
        self.assertEqual(json.loads(body)["omitted"], 1)
        body = evidence.render([Chunk("discarded", "text", "short source")], budget=1024)
        self.assertEqual(json.loads(body)["results"][0]["chunk_id"], "discarded")

    def test_terminal_validation_matches_schema(self):
        evidence = Evidence({"c1": Chunk("c1", "text")})
        invalid = [
            [],
            None,
            {"chunks": [None]},
            {"chunks": [{}]},
            {"chunks": [], "ranking_strategy": 2},
            {"chunks": [], "unexpected": True},
            {"chunks": [{"chunk_id": "unknown", "relevance_score": 1}]},
        ]
        invalid += [
            {"chunks": [{"chunk_id": "c1", "relevance_score": s}]} for s in (True, float("nan"), float("inf"), 10**400)
        ]
        invalid += [{"chunks": [{"chunk_id": "c1", "relevance_score": 0.5}] * 2}]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_terminal(json.dumps(payload), evidence, require_answer=False, top_k=20)
        self.assertEqual(validate_terminal('{"chunks": []}', evidence, require_answer=False, top_k=20), {"chunks": []})
        with self.assertRaises(ValueError):
            validate_terminal('{"chunks": [], "answer": " "}', evidence, require_answer=True, top_k=20)

    def test_keyword_adapter_uses_stable_ids_and_handles_empty_corpus(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                KeywordSearch(directory)
            Path(directory, "docs.md").write_text(
                "Renewal agreement expires in 2027.\n\nUnrelated installation guide.", encoding="utf-8"
            )
            backend = KeywordSearch(directory)
            self.assertEqual(backend("renewal", 1)[0].chunk_id, backend("agreement", 1)[0].chunk_id)
            self.assertEqual(backend("unknown", 1), [])


if __name__ == "__main__":
    unittest.main()
