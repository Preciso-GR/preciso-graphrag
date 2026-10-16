# Engineering decisions

Scope: the core-only branch. Supply-chain features and service containers are excluded.

## Stable reconciliation retries — 2026-10-16

Merge review reproduced a revision conflict when identical reconciled input was
retried after the clock advanced. Reconciliation inserted the current time into
the extraction, which changed the ledger payload hash. It now preserves a source
timestamp when supplied and omits the field otherwise. The ledger still records
ingestion time separately when it is absent from the input.

The regression advances time by one day, checks replay without a revision change,
then checks that changed evidence still produces a revision conflict. Both source
timestamp cases pass. All 253 local tests and lint passed. Existing reconciled
records with generated timestamps require their saved unified extraction for
exact replay; this fix does not rewrite existing ledger records.

## Merge verification: workflow syntax — 2026-10-16

GitHub rejected the CI workflow at line 26 before creating jobs. Local YAML
parsing reproduced the error: the unquoted pip option `--only-binary=:all:`
contains a colon followed by a space. A folded block now preserves the command
as a string. Both workflow jobs parse. Two extra trailing blank lines in lifecycle
tests were removed so the complete branch passes `git diff --check`.

Before this fix, 252 local tests, lint, compilation, both integrity guards, and
the offline MCP document and summary workflows passed. Hosted CI must run on
the corrected workflow before the main-branch merge is recommended.

## Summary maintenance — 2026-10-16

Summary submission previously coordinated core policy and persistence inside the
MCP adapter. It also imported private ledger state. The core workflow now owns
listing, freshness checks, summary application, vector publication, and queue
updates. The MCP adapter keeps compatibility imports of the public functions.

Description partitioning and pending-work policy live in `core.summary`. Merge
and submit use that same policy. `core.summary_maintenance` coordinates the
workflow with the existing transaction. It reads rebuild generation through a
public ledger accessor instead of importing private state. No new dependency,
model call, or persisted format was introduced.

Two new tests inject a pending-queue publication failure after graph and vector
writes. Entity and relationship cases restore the prior artifact bytes, graph,
and pending work, then permit a successful retry. The new offline MCP smoke checks
both summary kinds, restart, replacement, stale-token rejection, and fresh work.
CI now runs that smoke. Its shared tool-call helper accepts tool fields named
`name` without conflicting with the positional tool-name argument.

The summary guide now describes the current agent-written workflow. It removes
outdated claims of automatic language-model compression and unconditional field
size bounds. Summary freshness, budgets, recent-description retention, and MCP
result shapes remain unchanged by this refactor.

Verification: 252 tests passed locally and in the locked Linux container.
Compilation, lint, both integrity guards, the document lifecycle MCP smoke, and
the new summary MCP smoke passed. Shared policy logic also passed a syntax-tree
equivalence check after normalizing moved names and documentation. Test data was
temporary, with deterministic offline embeddings.

## Ingestion coordination — 2026-10-16

The public ingestion path called Contribution Ledger code, which imported a
private function back from ingestion. Full Rebuild had to skip public ingestion
to avoid another transaction. This made mutation ordering depend on knowledge
across both modules.

The Contribution Ledger module now owns public ingestion validation and
transaction coordination. `ingest/_materialize.py` holds the existing extraction
writes as an internal implementation. Creates and Full Rebuild use those writes
without re-entering public ingestion. MCP adapters import the coordinator directly.
The old `ingest.pipeline.ingest_extracted_json` import points to the same public
function for existing callers.

The moved extraction functions passed a syntax-tree equivalence check after
normalizing the function name and documentation. Existing lifecycle rollback
tests now inject failure through the evidence store adapter after chunk vectors
have been written. They verify actual partial-write recovery instead of patching
a private ingestion function. The legacy-data test uses the public ingestion
interface with an adapter set that has no ledger.

The refactor adds no dependency or storage format. Full Rebuild cost and locking
behavior are unchanged. It improves locality of coordination; no runtime speed or
memory improvement is claimed.

Verification: all 250 tests passed locally and in the locked Linux container.
Compilation, lint, both integrity guards, and the MCP lifecycle smoke passed.
The smoke used temporary data and offline embeddings. It checked 10 initial
documents, three additions, replay, replacement, deletion, stale revision,
isolation, restart, restoration, and corrected evidence retrieval.

## Ingestion result preservation — 2026-10-16

File and reconciliation adapters reconstructed ingestion results and discarded
revision, replay, document identity, and error information. The adapters now
retain the core result and add their existing file details and counter fields.
File ingestion keeps its extraction `file_path`; `source_file_path` preserves the
core source path. Future result fields also pass through without an allowlist.

Inline and file adapters also relabelled committed partial ingestion as validation
failure. They now return the actual core status. Partial ingestion remains disabled
by default. This is an intentional status correction for clients that explicitly
enable legacy partial ingestion.

Regression tests exercise all ingestion adapters with controlled core results.
Temporary offline graphs also verify actual replay, revision conflicts, unchanged
evidence after a rejected change, and truthful partial-commit results. No new
dependency or module was required.

Verification: 250 tests passed locally and in the locked Linux container,
including 17 result-preservation cases.
Lint, compilation, and both integrity guards passed. A real stdio MCP session
verified file ingestion, replay, revision conflict, and source-path preservation
with a temporary graph and offline embeddings.

## Document lifecycle series — 2026-10-16

The five-stage series adds contribution tracking, document maintenance, graph
editing, MCP discovery, and workflow verification. See
[document lifecycle](document-lifecycle.md) for commands and limits.

The ledger retains reviewed extraction JSON. Destructive operations replay the
complete retained corpus within the existing transaction. This is a correctness
baseline. It is not a claim that full replay is optimal for large collections.
No LlamaIndex, LangGraph, LangChain, new service, or new dependency was added.

Graph isolation withholds cited passages and their chunk vectors. Disconnection
only removes the graph edge. Shared-passage tests exposed that distinction and
prevent accidental loss of endpoint nodes. Node labels remain separate from the
existing canonical name IDs. Explicit aliases persist after an entity merge.

Lifecycle tests also exposed a vector clearing defect. Clearing NanoVectorDB's
record metadata left its embedding matrix populated. The adapter now uses the
dependency's deletion method to clear both aligned structures. Query regressions
check that obsolete vector results disappear after replacement and deletion.

Rebuilds invalidate summaries and advance a rebuild generation. Summary content
tokens bind pending work to its description and generation. A stale submission
cannot pass merely because the replacement has the same description count.

The standalone MCP smoke checks 10 initial documents, three later documents,
replay, invalid input, replacement, deletion, stale revisions, node isolation,
process restart, restoration, and retrieval of corrected evidence. It uses a
temporary workspace and deterministic embeddings. User graph files are not inputs
to these checks. No real embedding model is run for this series.

Compatibility changes are intentional: changed content under a tracked document
ID now requires explicit replacement; reserved document IDs start with `__`;
managed lifecycle calls require complete claims with local chunk references;
legacy or incomplete ledgers reject destructive edits. Do not use an older runtime
to write a ledger-enabled workspace. Large-corpus performance, client-specific
agent behavior, temporal claims, and team authorization remain unverified.

PRECISO stores document evidence in a local graph and vector index. An MCP client
uses tools to add documents and retrieve evidence. The supported runtime owns one
graph directory. A second runtime cannot open the same directory for service use.

## Documentation method

These documents use ASD-STE100 writing conventions. Use short sentences, active
voice, consistent technical terms, and one action per procedure step. Separate
instructions from explanations. Define conditions before instructions.

The [official standard](https://www.asd-ste100.org/about_STE.html) includes a
controlled dictionary and writing rules. These documents have not received a full
dictionary audit. They do not claim certified compliance.

| Technical term | Meaning |
|---|---|
| Artifact | A file that stores graph, vector, or document data |
| Commit | Publication of a complete, durable mutation |
| Journal | Files that permit recovery of an interrupted mutation |
| Embedding | A numeric vector that represents text for retrieval |
| Fingerprint | Saved information that identifies the embedding configuration |
| Worker | An asynchronous task that processes successive embedding batches |
| MCP | The protocol that connects a client to PRECISO tools |

## Decisions and verification

| Commit | Problem | Decision | Verification |
|---|---|---|---|
| `9c6ca95` | Corrupt JSON could look like an empty store | Reject malformed existing data during startup | Strict loading and retry tests |
| `e073410` | Invalid types and non-finite weights could enter storage | Validate extraction structure before mutation; limit bytes and records | Invalid input leaves stores unchanged |
| `3cce378` | Direct writes could destroy the previous artifact | Write a temporary file, sync it, replace the destination, and sync its directory | Serialization, replacement, and sync failure tests |
| `ca5d80b` | File tools could read outside configured inputs | Resolve paths within input roots; bound reads; generate safe output names | Traversal, symlink, extension, and size tests |
| `fac85e1` | Large inputs created a task for each embedding batch | Use a fixed worker pool; apply queue and provider deadlines | Ordering, cancellation, timeout, and task-count tests |
| `842eae0` | Different models could share a vector dimension | Save and enforce the embedding fingerprint inside each index | Same-dimension model and revision mismatch tests |
| `c34450d` | Separate artifact saves could leave an incomplete graph | Keep a recoverable journal; restore disk and memory after failure; serialize reads | Failed save, cancellation, replay, interrupted recovery, and subprocess termination tests |

### Why local storage remains

A new database adds deployment, migration, and failure paths. Current measurements
do not establish a need for that cost. Keep NetworkX, JSON, and NanoVectorDB.
Measure representative corpus sizes before changing the storage backend.

### Why the journal uses hard links

Atomic artifact writes replace files instead of editing their previous contents.
The journal can retain those previous files with hard links on the same filesystem.
Preparation does not copy the complete corpus. The next write retains both versions
until commit or rollback finishes. Provision disk space for changed artifacts.

The prepared journal restores the previous revision after interruption. A committed
journal retains the new revision. Cleanup renames the journal before deleting it.
This prevents interrupted cleanup from appearing to be an incomplete transaction.

If rollback fails, supported operations reject further access. Repair the storage
failure before restarting. Never remove the journal to bypass recovery.

### Why reads wait for mutations

Ingestion changes several in-memory stores. A query must not see half of that change.
Supported reads acquire the same session lock as mutations. This simple design
trades concurrent query throughput for a consistent revision. Shared deployment
requires separate measurements and a storage design that supports its workload.

### Why four workers remain

Four is a configuration default, not a measured throughput optimum. The worker pool
limits scheduled batches as well as provider calls. With 8,000 texts, the paused
provider probe decreased additional pending tasks from 1,001 to 5.
This result measures task count. It does not establish memory or latency gains.

### Why the image has three stages

The builder installs locked dependencies and builds the project wheel. The test
stage adds development checks. The runtime copies the installed environment and
tokenizer cache. It excludes the repository, development tools, and model weights.

Core dependencies have hash-locked versions. Optional cloud and export SDKs are
excluded from this image. Build an explicit variant if those features are required.
Never add all optional dependencies to the default image without a demonstrated need.

## Numeric input follow-up

The review reproduced two additional failures. A zero embedding passed validation
and became `NaN` during cosine normalization. JSON loading accepted non-finite
constants and numbers that exceeded the finite floating-point range.

Embedding validation now rejects zero vectors before index mutation. JSON loading
rejects `NaN`, infinity constants, and numeric overflow. Tests verify unchanged
index data, successful retry, runtime error recovery, and preservation of invalid
files. The local and Linux arm64 container suites passed 198 tests.

## Remaining work

1. Verify a coherent backup and restore procedure.
2. Measure peak memory, startup time, and query latency with representative inputs.
3. Evaluate retrieval with a pinned semantic model and reviewed source spans.
4. Define log redaction, cache retention, and a release compatibility policy.
5. Establish bounded request admission and lock waiting for the selected workload.

Keep each change reversible. Record its baseline, result, and limitations here.

## Local Ollama integration result

On 2026-10-06, the one-document MCP test passed with `mxbai-embed-large`.
Ollama returned active status and 1,024-dimensional embeddings. The test verified
handshake, ingestion, restart persistence, and retrieval. It made four successful
embedding requests: two startup probes, one document request, and one query request.
Application embedding concurrency was set to one. The temporary graph was removed
after completion. This host test does not verify Docker connectivity or ranking quality.

## Retrieval pilot result

On 2026-10-07, a six-question synthetic pilot compared lexical fallback and local
Ollama with concurrency one. Complete required evidence appeared in three of five
answerable cases with fallback and five of five with `mxbai-embed-large`.
Both providers returned related evidence for an unsupported question. No retrieval
setting was changed from this small sample. See [retrieval pilot](retrieval-pilot.md)
for the fixture, measurements, and limitations.

## Source layout and development lifecycle

The application moved to `src/` without changing Python module names. Manual checks
moved to `tests/manual/`. The domain glossary and summary design moved into `docs/`.
Runtime data paths remain stable. Source launchers, package discovery, Docker, CI,
and documented commands were updated together.

The source layout separates installed code from repository files. A wheel must
include the application explicitly. Tests must not succeed only because the
working directory exposes uninstalled source. The runtime container provides
that installed-wheel boundary; source tests also exercise the editable checkout.

The obsolete divide-warning filter was removed. The 198-test local suite passes
with runtime warnings treated as errors. Lint and both manual integrity guards
also pass. The MCP guide uses ASD-STE100 writing conventions and matches all 11
advertised tool names. Full controlled-dictionary conformance has not been audited.

Folder cleanup is not production certification. Restoration, release rollback,
resource budgets, provider revision pinning, and broader retrieval evaluation
remain release gates. See [production readiness](production-readiness.md).

The locked Linux arm64 test image passed 198 tests and both integrity guards
after the source move. The source launcher passed ingestion, restart persistence,
and retrieval with a disposable graph. The system layer diagram was created
with MCP Excalidraw and saved as editable source and a standalone SVG.

## Offline backup verification

On 2026-10-10, offline backup and restoration were added without a database or
provider call. The command acquires runtime and mutation ownership, rejects an
unfinished journal, and copies only supported artifacts. A versioned manifest
records byte counts and SHA-256 hashes. Restoration checks copied bytes and
publishes a fresh directory. It never intentionally overwrites an existing target.

The drill verifies exact artifact bytes, graph reopening, saved embedding identity,
and retrieval of a known evidence chunk. Failure tests cover changed data, links,
unsafe filenames, active writers, journals, existing targets, and interrupted copying.
The CLI is packaged in the runtime wheel for Docker operation.

Checksums detect changed bytes, not authenticity. Retention, separate storage,
representative restore timing, and old-image rollback remain operational gates.
See [backup and restoration](backup-recovery.md).

Verification: 210 tests passed locally and in the locked Linux arm64 test image.
Lint and both integrity guards passed. The installed runtime CLI completed backup,
verification, and restoration with networking disabled and a read-only root.
All drill data was temporary. No existing user graph or Ollama model was used.

## Resource and rollback baseline

The 2026-10-11/12 measurement used 100 and 1,000 short chunks with 1,024-dimensional
synthetic vectors. The Docker 1,000-chunk case used about 143 MiB of resident memory
after ingestion and reached about 186 MiB of process peak memory. Warm core query
latency had a 0.531 ms 95th percentile across 20 measured queries.

A separate actual MCP server run used lexical fallback. The server used about
154 MiB after queries. Its warm query 95th percentile was 1.344 ms, including transport.
The source run had an unexplained 66.899-second initialization outlier. The offline
image run did not reproduce that outlier. No model inference was used.

The runtime from `b8a67ea` reopened and queried disposable data produced by `2116c76`.
An identical replay and restart also passed. The artifact format did not change
between these releases. This is a limited compatibility check, not migration proof.

See [runtime baseline](runtime-baseline.md) for methods, measurements, and limits.
No performance optimization or production resource limit was selected from these runs.

## Mechanism 0: document preparation

The entry-point review found no upload endpoint or built-in raw-document parser.
An external agent reads sources and produces reviewed extractions. This boundary
is now documented separately from graph ingestion.

The three extraction skills had chunking instructions inside JSON examples. Those
examples now parse as JSON. Character and token guidance no longer claims an
approximate equivalence. The general skill no longer instructs agents to infer
missing values or create every named concept as an entity.

A shared preparation guide separates extraction-only work from authorized ingestion.
It defines evidence wording, uncertainty, identity collisions, and source review.
The guide does not add automatic claim verification. The worked example passed
existing shape and strict-reference validators. Each example chunk occurs in the
synthetic source. No graph was ingested and no model inference was run.
