# Production readiness assessment

Date: 2026-10-04. Reviewed core-only branch `core-graphrag`.
Scope: assessment and implementation gates; no production hardening is claimed
as implemented by this document.

## Recommended production scope

Start with one private, client-launched MCP container and one active process per
graph directory. Keep existing local graph/vector storage and an explicitly
configured external or host embedding provider. Separate Qdrant, Neo4j, and
Ollama containers are excluded following the user's decision.

Production readiness means evidence that supported operations preserve data,
recover from failure, respect resource/security boundaries, and can be upgraded
and rolled back. A small multi-stage image is one part of that work.

The deployment audience is not yet confirmed. The private stdio scope below is
the initial assumption; shared/public access has additional mandatory gates.

## Existing foundations

- Offline tests, Python 3.11–3.13 CI, compilation, and summary integrity guards
  already exist in `.github/workflows/ci.yml`.
- Ingestion has a POSIX file lock; storage namespaces are isolated by directory.
- Embedding results are validated for count, dimension, and finite values.
- Four embedding requests can run concurrently across a server runtime.
- Vector persistence failures now propagate to the ingestion result.
- Runtime status reports degraded embedding configurations and artifact counts.
- Local lookup/ranking optimizations have a reproducible synthetic benchmark.

These are useful foundations, not proof of crash durability, safe multiple
processes, live semantic quality, or a production container.

## Release blockers, in priority order

| Priority | Verified repository gap | Required change | Release evidence |
|---|---|---|---|
| P0 | `write_json` and NetworkX graph writes overwrite destination files directly | Write temporary files on the same filesystem, flush/fsync, replace atomically, and sync the parent directory where supported; audit NanoVectorDB persistence too | Interruption at write boundaries preserves a readable prior or new file; disk-full/permission failures never report success |
| P0 | `load_json` returns `None` on malformed existing JSON; KV initialization uses `or {}` | Distinguish missing files from corrupt/unreadable authoritative stores; fail closed and preserve the bad file for recovery | Corrupt KV input prevents normal writable startup without overwriting existing data |
| P0 | Ingestion saves chunk, graph, vector, and provenance stores separately | Introduce a recoverable commit across authoritative stores, not merely atomic individual files; ensure readers see a committed revision | Failure between any two saves restores the previous committed graph or completes the new one; references and vectors remain consistent |
| P0 | Mutations change in-memory stores before all embedding/persistence work succeeds | Stage changes or reliably restore state after failure; protect queries from partial mutation; define exact replay/idempotency behavior | Failure, cancellation, and identical replay do not duplicate descriptions or expose incomplete evidence |
| P0 | Vector compatibility checks dimensions; the manifest records but does not enforce model compatibility | Validate a persisted embedding fingerprint before opening indexes: provider/model revision, dimension, preprocessing, and query/document mode | Different models with the same dimension are rejected; upgrades require explicit rebuild into a fresh directory |
| P0 | Embedding adapters and synchronous startup probe have no explicit application deadline policy | Add bounded connect/read/overall deadlines, asynchronous startup probing, cancellation, and capped transient retries with backoff | Unreachable/hanging provider exits startup or the request within its configured deadline; permits and locks are released |
| P0 | File tools accept absolute/relative paths without a configured containment boundary; reconciliation builds an output path using document IDs | Constrain input/output roots, resolve paths/symlinks, enforce file type/size, and use generated safe output names | Traversal, symlink escapes, oversized inputs, and unsafe document IDs are rejected before reading/writing |
| P0 | Validator accepts null document IDs and non-finite relationship weights | Enforce actual string types, finite numeric values, collection/text limits, and strict source references for production ingestion | Invalid payloads are rejected before mutation; acceptance of partial data is explicit and consistent across tools |
| P0 | No container build, dependency lock, or container recovery tests; server overrides configured workdir with a hardcoded path | Implement the minimal locked multi-stage image, configurable volume path, non-root permissions, and attached stdio launcher | Clean installed wheel, real MCP handshake, ingest/query/restart, tokenizer cache, and shutdown pass on supported Linux platforms |

Evidence locations: `core/utils.py`, `core/storage/kv_store.py`,
`core/storage/graph_store.py`, `core/storage/vector_store.py`,
`ingest/pipeline.py`, `ingest/validator.py`, `config.py`,
`preciso_mcp/tools/ingest_from_file_tool.py`,
`preciso_mcp/tools/reconcile_tool.py`, and `preciso_mcp/server.py`.

Small disposable probes on the review date confirmed:

```text
Existing malformed JSON -> load_json returns None
document_id=None -> top-level validation returns no errors
relationship weight=NaN -> relationship validation returns valid
```

These are reproduced validation/load behaviors. No crash or data-loss experiment
has yet been run; durability risks above follow from the write/commit code paths.

## Smallest sound data-safety design

Keep local storage for the initial target. First separate strict authoritative
loads from best-effort cache/diagnostic reads. Then implement atomic individual
artifact saves and a recoverable document commit.

A candidate is staging a complete artifact generation, validating it, and
publishing one committed-generation pointer atomically. Never overwrite the
last committed generation while preparing a new one. Readers use a single
committed revision, and an operation reports success only after durable publish.
Clean abandoned staging directories on recovery, retaining a known-good backup.
Measure temporary disk space and full-copy cost before adopting this mechanism.
A journal with recovery is an alternative, but it must meet the same failure tests.

Until transaction isolation is implemented, serialize reads against mutations
or serve the prior immutable snapshot; an error response alone is insufficient
if partially modified in-memory data remains available to later queries.

Acquire a process-lifetime exclusive ownership guard for the graph directory
and reject a second MCP runtime initially. The current ingestion-only lock and
in-process revision counters do not establish cross-process cache coherence.
This conservative scope avoids introducing a database just for concurrency.

Document how corrections work: current ingestion is additive; identical replay
is recovery, not document replacement. Rebuild a fresh graph from the complete
valid corpus for corrections until replacement/deletion is explicitly supported.

## Operational requirements before private production

1. **Backup and recovery:** back up a coherent committed revision plus embedding
   fingerprint and reviewed inputs. Provide restore verification, retention,
   restricted access, and off-host copies where data matters. Agree recovery
   time and acceptable data-loss windows before release. A live directory copy
   taken between separate saves is not a verified backup.
2. **Bounded resource use:** limit ingestion bytes/records, text lengths, pending
   requests, graph candidates, and output tokens. Replace eager embedding task
   creation with a bounded worker/window. Add cache retention/size limits and
   disk headroom checks. Measure peak RSS before choosing CPU/memory/PID limits.
   Docker has no resource limits by default; configure them explicitly using
   [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/).
3. **Container boundaries:** non-root user, read-only application filesystem,
   writable data volume and bounded temporary storage, dropped capabilities,
   no Docker socket, no privileged mode, and no unnecessary host mounts/ports.
   Verify the configuration against
   [Docker's security guidance](https://docs.docker.com/engine/security/).
4. **Provider readiness:** distinguish process health from semantic retrieval
   readiness. Reject unsupported model/configuration combinations. Keep lexical
   fallback explicitly opt-in for testing; never silently advertise it as normal
   semantic retrieval. Give read-only diagnostics useful failure information.
5. **Observability:** structured stderr logs with operation ID, duration, stage,
   revision, error category, and retry count. Redact keys and document content.
   Track query latency, embedding failures, ingestion failures, lock wait,
   memory/disk headroom, and pending summaries. Start with logs and a lightweight
   status tool; no dedicated monitoring stack is necessary for the local scope.
   Avoid copying/scanning all chunk data for every cheap health check.
6. **Shutdown and cancellation:** stop accepting mutations, bound drain time,
   complete or abandon staged commits safely, release ownership/resources, and
   exit cleanly on SIGTERM/client disconnect. Do not claim recovery solely from
   graceful shutdown; SIGKILL must also preserve committed data.
7. **Releases and rollback:** version the artifact schema and package, document
   compatible versions, keep migration/rebuild instructions, and test old-image
   rollback against compatible data. Pin dependencies/base image and maintain
   a reviewed update cadence. CI should build wheels and images, lint, run
   container MCP smoke tests and failure tests, and scan shipped dependencies.
   Existing offline CI does not exercise real provider integration.
8. **Retrieval quality:** freeze a reviewed evidence corpus and held-out questions.
   Measure evidence recall, complete bridge evidence, citation correctness,
   unsupported-answer behavior, tokens, p95 latency, and memory. Use a pinned real
   embedding provider for quality evaluation. Treat retrieved text as untrusted
   content rather than instructions when passed to a generating model/agent.

## Additional gates for shared/public deployment

Do not expose the current local tools directly as a public service. If that
deployment is selected, add an explicit supported network MCP transport,
TLS, MCP-compatible authentication, authorization per tool, per-user/workspace
isolation, quotas, and audit logging. Restrict outbound export destinations and
administrative/destructive operations; tool-supplied URLs/credentials must not
become an unrestricted way to access internal services.

Use the [MCP security best practices](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices)
for the transport/access design. Load-test concurrent users and prove workspace
isolation before release. Revisit storage ownership before adding replicas.
These requirements depend on the deployment audience; they are not needed to
publish a port for the private stdio container because that container needs no port.

## Implementation and acceptance sequence

1. Fix strict load/validation/path boundaries and embedding fingerprint checks.
2. Implement durable artifact writes and transaction recovery; prove crash,
   failed embedding, disk-full, cancellation, and replay behavior.
3. Add provider deadlines, bounded admission/embedding work, process ownership,
   readiness, and shutdown behavior.
4. Build the locked minimal container with persistent volume and MCP launcher.
5. Add restore drills, release/rollback checks, structured logs, and CI gates.
6. Benchmark and improve retrieval without violating the durability/resource gates.

Before claiming production readiness, attach results for each P0 acceptance gate,
one backup/restore drill, one forced-termination recovery run, one provider-outage
run, and representative ingestion/query load measurements. Set numerical latency,
memory, recovery, and quality budgets from the target workload before release.
No unmeasured image-size target or universal availability guarantee is asserted.

See [the lightweight Docker and retrieval plan](lightweight-docker-retrieval-plan.md)
for build and quality experiments. This assessment adds the safety and operational
gates that must precede a production release.
