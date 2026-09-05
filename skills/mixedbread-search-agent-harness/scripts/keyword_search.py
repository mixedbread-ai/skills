"""Optional local BM25 example for users who prefer keyword search over text files."""

import argparse
import asyncio
import json
import math
import os
import re
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from search_loop import Chunk, run_episode


class KeywordSearch:
    def __init__(self, directory):
        self.chunks = []
        for path in sorted(Path(directory).iterdir()):
            if path.is_file() and path.suffix in (".md", ".txt"):
                for index, paragraph in enumerate(re.split(r"\n\s*\n", path.read_text(encoding="utf-8"))):
                    if paragraph.strip():
                        self.chunks.append(Chunk(f"{path.name}:{index}", paragraph, str(path)))
        if not self.chunks:
            raise ValueError("corpus needs at least one non-empty .md or .txt file")
        self.counts = [Counter(re.findall(r"\w+", c.text.lower())) for c in self.chunks]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = max(1, sum(self.lengths) / len(self.chunks))
        df = Counter(term for counts in self.counts for term in counts)
        self.idf = {t: math.log(1 + (len(self.chunks) - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def __call__(self, query, top_k):
        terms = set(re.findall(r"\w+", query.lower()))
        scored = []
        for chunk, counts, length in zip(self.chunks, self.counts, self.lengths, strict=True):
            norm = 1.5 * (0.25 + 0.75 * length / self.average)
            score = sum(self.idf[t] * counts[t] * 2.5 / (counts[t] + norm) for t in terms if t in counts)
            if score > 0:
                scored.append((score, chunk))
        return [chunk for _, chunk in sorted(scored, key=lambda hit: -hit[0])[:top_k]]


async def main():
    from openai import AsyncOpenAI

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("query")
    parser.add_argument("--answer-mode", choices=("plain_text", "none", "submit_ranking"), default="plain_text")
    args = parser.parse_args()
    async with AsyncOpenAI(base_url="https://api.mixedbread.com/v1", api_key=os.environ["MXBAI_API_KEY"]) as client:
        result = await run_episode(
            client,
            args.query,
            KeywordSearch(args.corpus),
            answer_mode=args.answer_mode,
            search_description="Keyword search over local text files using BM25. Send focused keyword queries; "
            "this tool does not match semantic paraphrases. Returns chunks with stable IDs.",
        )
    result["evidence"] = {key: asdict(chunk) for key, chunk in result["evidence"].items()}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
