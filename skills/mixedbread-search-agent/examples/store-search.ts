// A search-grounded answer over one Mixedbread Store, with citations.
//
// The server runs the whole search loop: the model picks among the hosted
// store tools, reads the chunks, and answers. `citations: true` ships the
// answer with `file_citation` annotations pointing at the cited chunks.

import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://api.mixedbread.com/v1",
  apiKey: process.env.MXBAI_API_KEY!,
});
const STORE = process.env.MXBAI_STORE ?? "my-store";

// Hosted tool types and context_management are Mixedbread extensions the
// OpenAI SDK's types do not know; the cast lets them through unchanged.
const response = await client.responses.create({
  model: "toast-1",
  input: "Which asset manager grew AUM fastest last quarter, and what drove it?",
  tools: [
    { type: "search_corpus", store_identifiers: [STORE], citations: true },
    { type: "grep", store_identifiers: [STORE], citations: true },
    { type: "inspect_metadata", store_identifiers: [STORE] },
    { type: "filter_chunks", store_identifiers: [STORE], citations: true },
    { type: "get_chunks", store_identifiers: [STORE] },
  ],
  include: ["search_corpus_call.results"],
  context_management: { edits: [{ type: "prune_context" }] },
} as never);
if (response.status !== "completed") {
  throw new Error(`Response did not complete: ${response.status}`);
}

console.log(response.output_text);

// Each annotation carries file_id, filename, index (a character offset into
// the answer), chunk_id ("<file_id>:<chunk_index>") and store_id.
for (const item of response.output) {
  if (item.type !== "message") continue;
  for (const part of item.content) {
    if (part.type === "output_text") console.log(part.annotations);
  }
}
