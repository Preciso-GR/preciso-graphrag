# Engineering decisions

Scope: the core-only branch. Supply-chain features and service containers are excluded.

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
