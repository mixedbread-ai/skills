# Harness architecture

Round-by-round mechanics for a search-model harness. Components, budgets, and rules live in SKILL.md; this is how a round actually runs. The loop can serve as a fast search sub-agent doing knowledge work for any orchestrator; orchestration itself stays outside the harness.

## Round choreography

Before the final round:

1. Build non-terminal tools. For a structured deliverable, also append the terminal with evidence-ID enums derived from currently visible evidence.
2. Apply the configured context-management policy when its pressure threshold is crossed. For the recommended pruning policy, append the budget notice before requesting the turn.
3. Request one turn with `tool_choice="auto"` and parallel calls enabled.
4. Content with no calls → the run finished; accept it when prose is the deliverable.
5. Terminal as the only call → validate and finish.
6. Terminal mixed with other calls → return a structured invalid-terminal error, or reject the turn per policy.
7. Cap accepted non-terminal calls, execute concurrently, append one result message per emitted call, and use structured errors for excess or unknown calls.
8. Clip combined payloads to the remaining prompt headroom.
9. Stop early when the evidence suffices. A round ceiling is not a target.

Final round:

1. Remove retrieval tools. Prose → send no tools at all. Structured → offer only the terminal and force it by name.
2. Append: "Do not search further. Make exactly one terminal call with no parallel calls."
3. Return the text directly, or validate submitted IDs, cardinality, ordering fields, and score range.
4. Retry an invalid payload a small fixed number of times without reopening retrieval.

## Parallel execution

| Concern | Approach |
|---------|----------|
| Independent calls | Async-native I/O with `gather`/task groups |
| Message ordering | Preserve the model's call order even when completion order differs |
| Payload allocation | Water-fill: small payloads keep full size, remaining budget splits among larger siblings |
| Shared state | Duplicate suppression and ID assignment must be concurrency-safe |
| Throughput | Track provider QPS separately from model-visible call width |
| Cancellation | Cancel in-flight calls when the episode is cancelled |

## Context management semantics

Prefer pruning stale payloads because it preserves a stable prompt prefix and evidence identities. If an application uses compaction instead, define its identity, restoration, and cache behavior explicitly rather than silently changing the history.

On prune:

- remove matching content from old tool-result messages;
- retain the registry entries and IDs;
- allow an explicit expansion call to restore the content;
- permit the terminal to rank a pruned ID, since the model already evaluated it.

This differs from truncation. A result dropped **before** the model ever saw it must leave the visible registry entirely and may be returned by a later search.

## Duplicate suppression

As an independent backend optimization, optionally suppress chunks already shown to the agent so repeated queries produce more diverse evidence. This is recommended for search quality but is not part of pruning semantics and is not required for a valid harness.
