// Search the web with the same hosted tool, by naming the web store.
//
// `mixedbread/web` is a store identifier `search_corpus` accepts; combine it
// with your own stores in one entry to search both. Only `search_corpus`
// reads it: the chunk tools (grep, filter_chunks, get_chunks) skip it. A web
// hit is cited like any chunk, with the page URL as its `filename`.

import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://api.mixedbread.com/v1",
  apiKey: process.env.MXBAI_API_KEY!,
});

const response = await client.responses.create({
  model: "toast-1",
  input:
    "What did the Federal Reserve decide at its most recent FOMC meeting, " +
    "and how did Treasury yields and equities react? " +
    "Cite the Fed's statement and one market report.",
  tools: [
    { type: "search_corpus", store_identifiers: ["mixedbread/web"], citations: true },
  ],
  context_management: { edits: [{ type: "prune_context" }] },
} as never);
if (response.status !== "completed") {
  throw new Error(`Response did not complete: ${response.status}`);
}

console.log(response.output_text);
for (const item of response.output) {
  if (item.type !== "message") continue;
  for (const part of item.content) {
    if (part.type !== "output_text") continue;
    for (const annotation of part.annotations) {
      if (annotation.type === "file_citation") console.log(annotation.filename); // the cited page's URL
    }
  }
}
