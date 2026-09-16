// One client function tool, run in a loop.
//
// The corpus lives behind your own function: the model returns a
// `function_call` item, you run it and send a `function_call_output` with
// `previous_response_id`, and repeat until the response carries no calls. The
// stub below stands in for your backend; replace `searchTickets` with a real
// lookup and keep the loop.

import OpenAI from "openai";
import type { ResponseInputItem } from "openai/resources/responses/responses";

const client = new OpenAI({
  baseURL: "https://api.mixedbread.com/v1",
  apiKey: process.env.MXBAI_API_KEY!,
});

const TICKETS = [
  { id: "T-1042", title: "Checkout times out on Safari", status: "open", area: "payments" },
  { id: "T-1071", title: "Invoice PDF missing VAT line", status: "closed", area: "billing" },
];

// The stub; a real backend would query a database or an API.
function searchTickets(args: { query: string; status?: "open" | "closed" }) {
  const words = args.query.toLowerCase().split(/\s+/);
  return TICKETS.filter(
    (t) => (!args.status || t.status === args.status) && words.some((w) => t.title.toLowerCase().includes(w)),
  );
}

const TOOL = {
  type: "function",
  name: "search_tickets",
  description: "Search the support ticket tracker by keyword. Returns id, title, status and area.",
  parameters: {
    type: "object",
    properties: {
      query: { type: "string", description: "Keywords to look for in ticket titles." },
      status: { type: "string", enum: ["open", "closed"] },
    },
    required: ["query"],
    additionalProperties: false,
  },
} as const;
const CONTEXT = { context_management: { edits: [{ type: "prune_context" }] } };

let response = await client.responses.create({
  model: "toast-1",
  input: "Which open tickets are about checkout problems?",
  tools: [TOOL],
  ...CONTEXT,
} as never);
for (let round = 0; round < 8; round++) {
  // bound the loop; a run that never answers is a bug to surface
  const calls = response.output.filter((item) => item.type === "function_call");
  if (calls.length === 0) break;
  const outputs: ResponseInputItem[] = calls.map((call) => {
    let result: unknown;
    try {
      result = searchTickets(JSON.parse(call.arguments || "{}"));
    } catch (error) {
      // never let a tool raise past the executor
      result = { error: error instanceof Error ? error.message : String(error), retryable: true };
    }
    return { type: "function_call_output", call_id: call.call_id, output: JSON.stringify(result) };
  });
  response = await client.responses.create({
    model: "toast-1",
    previous_response_id: response.id,
    input: outputs,
    tools: [TOOL],
    ...CONTEXT,
  } as never);
}
if (response.status !== "completed") {
  throw new Error(`Response did not complete: ${response.status}`);
}

console.log(response.output_text);
