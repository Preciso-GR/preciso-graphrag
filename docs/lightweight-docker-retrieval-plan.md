# Lightweight Docker deployment and retrieval improvement plan

Date: 2026-10-04. Baseline: `core-graphrag` at `b0a32b4`.
Status update, 2026-10-05: configuration, input boundaries, recovery, embedding
identity, bounded workers, and the locked three-stage Docker build are implemented.
The remaining sections describe experiments and acceptance criteria. Retrieval
quality changes remain pending a reviewed baseline. See [engineering decisions](engineering-log.md)
and [container operation](container-guide.md) for implemented behavior.

Production release also requires the data-safety, recovery, security, and
operational gates in [production-readiness.md](production-readiness.md).

## Objective and decision

Keep PRECISO a small, local-first MCP application with reproducible container
builds, persistent data, bounded resource use, and better evidence retrieval.
Preserve the core-only scope without supply-chain integration.

Assume the initial deployment is one local user and one active MCP process per
graph. A shared, always-on service would need a separate transport, access-control,
and concurrent-storage design; it is not necessary for the first container.

Use one Python application container with persistent local storage. Skip the
Qdrant, Neo4j, and Ollama service-container phase. Connect to an existing embedding
provider through configuration. Keep local storage as the default until
measurements justify a backend migration. Docker packaging alone does not
improve retrieval.

## What the repository establishes

| Area | Current behavior | Consequence |
|---|---|---|
| Runtime | Python MCP server; `mcp.run()` defaults to stdio | Client must attach stdin/stdout to the container |
| Storage | NetworkX graph, JSON stores, NanoVectorDB | The graph directory must survive container replacement |
| Data location | `GRAPHRAG_MCP_WORKDIR` overrides `GRAPH_IS_HERE` | The container sets `/data/graph` |
| Qdrant / Neo4j | Optional export adapters | Starting their containers does not route queries through them |
| Dependencies | Hash-locked core, build, and development dependencies | Optional SDKs remain outside the runtime image |
| Embeddings | Four concurrent requests; batches of eight texts | A fixed worker pool bounds scheduled embedding batches |
| Retrieval | Entity, relationship, and direct-chunk candidates; final cosine selection | Evaluate whether final selection loses necessary bridge evidence |
| Reranking | Existing optional hook, not enabled by the MCP default | Reuse the hook only if measured gains justify its cost |
| Containers | Builder, test, and runtime Docker stages; no Compose | Verify the image and persistent MCP operation |

The previous optimizations measured local metadata lookup at 31.050 → 0.491 ms
and evidence selection at 45.213 → 6.427 ms on the synthetic benchmark. These
exclude embedding and generation latency; see [performance.md](performance.md).

## Phase 1 — establish the baseline and simplify configuration

1. Record dependency sizes, clean-install startup time, idle RSS, ingestion peak
   RSS, query p50/p95 latency, and persistence time. Use fixed small and larger
   corpora, a pinned embedding model, and repeatable cold/warm runs.
2. Centralize environment parsing in the existing configuration path. Add
   `GRAPHRAG_MCP_WORKDIR`, retaining `GRAPH_IS_HERE` for existing local users and
   setting `/data/graph` in Docker. Validate configuration once at startup.
3. Audit installed-package behavior: build a wheel, install it into a clean
   environment, and run `python -m preciso_mcp.server` outside the checkout.
   Include any required templates/resources explicitly in package metadata.
4. Lock core dependencies and optional extras for the chosen Python/platforms.
   Keep development tools separate. Audit unused dependencies/imports before
   removing anything; NumPy and token counting currently serve real functions.
5. Confirm MCP logs go to stderr and stdout contains protocol messages only.
   Confirm startup and shutdown release resources and preserve persisted data.

Primary files: `src/config.py`, `src/preciso_mcp/server.py`, `pyproject.toml`,
`requirements.txt`, `.env.example`, and `scripts/mcp_launcher.sh`.

Acceptance: clean installation and MCP handshake work; old default data paths
still work; explicit data paths work; the existing regression suite passes.

## Phase 2 — implement a normal multi-stage Docker build

Start with a supported official Python slim Debian image; Python 3.12 is a
candidate to validate, not an already tested runtime choice. Pin a reviewed
base-image digest and resolved dependencies, with an intentional update process.
Validate Linux arm64 and amd64 separately. Choose Alpine only if wheel support
and actual image/runtime measurements make it better.

Use one Dockerfile with named stages:

| Stage | Purpose | Included in final runtime? |
|---|---|---|
| `builder` | Build the project wheel and resolve locked dependency wheels | Only required artifacts |
| `test` | Install development checks and run relevant tests | No |
| `runtime` | Install core wheels and packaged resources | Yes |
| Future export variant | Not implemented; requires a demonstrated need | No |

Match builder/runtime Python and platform. Prefer binary dependency wheels;
if a compiler is necessary, keep it in the builder. Order dependency layers
before frequently changing application code. Explicitly run the `test` target
in CI: an independent test stage can be skipped when building only runtime.
Selective artifact copying is the purpose of
[Docker multi-stage builds](https://docs.docker.com/build/building/multi-stage/).

Runtime requirements:

- Run as a non-root user with an exec-form Python entrypoint.
- Copy the installed application and runtime dependencies; exclude development
  environments, Git metadata, tests, caches, credentials, corpora, and model weights.
- Add `.dockerignore` for those large/private inputs. Keep tests available to the
  build context if the test stage uses them, but never copy them into runtime.
- Pre-cache the required tiktoken encoding during the build; verify tokenization
  works without a runtime download or silently falling back to whitespace counts.
- Mount `/data/graph` writable and input/extraction files read-only. Provide a
  writable temporary directory and document volume ownership for non-root use.
- Retain one process per graph initially. Do not infer safe replicated writers
  from the existing file lock; cross-process cache freshness needs separate work.

Include the MCP launcher and persistent volume instructions in this phase.
Launch the container with stdin attached and no TTY (`docker run -i`), and
verify stdout contains only protocol messages. Do not leave a second MCP writer
running on the same graph. For an existing host Ollama on macOS, document
`host.docker.internal` instead of `localhost` inside the container. Keep provider
credentials in runtime configuration.

Acceptance: record image size, layer contents, cold start, and RSS; verify no
secrets/model files entered the image; complete handshake, ingest/query, restart,
backup/restore, and interrupted-ingestion checks against mounted data.

## Phase 3 — reduce resource use where profiling proves value

Prioritize these experiments, retaining only measured improvements:

1. Replace ingestion's unbounded task scheduling with a small worker pool or
   windowed batches. Preserve the four-request embedding limit, result ordering,
   cancellation behavior, and error reporting. Measure peak RSS and throughput.
2. Stream or batch export preparation instead of retaining all upload records
   at once where the adapters currently materialize them.
3. Profile complete-file graph/vector persistence during additive ingestion.
   Reduce redundant writes before considering another storage format.
4. Bound graph expansion, candidate counts, and context tokens explicitly.
   Expose a small set of useful controls with validated defaults.
5. Benchmark independent retrieval branches before running them concurrently;
   local CPU work may not benefit from asyncio concurrency.
6. Add a maintained ID index only if repeated record scans remain a bottleneck
   and the measured RAM increase is acceptable.

Set resource limits after representative measurements. Report core-container
and complete-stack budgets separately, including model memory and persistent
data. No image-size or RAM target is yet established by a built container.

## Phase 4 — improve retrieval with an evidence benchmark

First create a reproducible benchmark of evidence retrieval, separate from
answer generation. Start with 20–30 reviewed questions and a small committed,
non-supply-chain corpus; expand to a held-out set before selecting defaults.
Cover exact identifiers, aliases, paraphrases, numeric facts, cross-document
bridges, contradictory versions, and questions with no supporting evidence.

Pin corpus, extraction artifacts, embedding model/version/dimension, and query
settings. Use real semantic embeddings for quality evaluation; the deterministic
test fallback is suitable for code checks, not semantic-quality conclusions.

Measure evidence recall@k, ranking quality, complete supporting-evidence coverage
for bridge questions, citation validity, no-answer behavior, context tokens,
query p50/p95 latency, embedding calls, and peak memory. Label required source
spans manually; generated extraction or answers are not gold labels by default.

Implement experiments in this order:

1. **Exact entity/alias candidates:** improve identifier/name matching where the
   benchmark reveals misses. Avoid fuzzy merges that change entity identity.
2. **Lexical candidates if needed:** compare a lexical baseline against dense
   retrieval for identifiers and numbers. Consider SQLite FTS5 only after
   checking availability in both container architectures; it provides full-text
   search and BM25 scoring in the
   [official FTS5 documentation](https://www.sqlite.org/fts5.html).
3. **Candidate fusion:** compare current merging with rank-based fusion of
   lexical, vector, and graph candidates. Do not add incompatible raw scores.
   Keep candidate caps and ablate each source to identify actual contributions.
4. **Bounded graph evidence:** experiment with one/two-hop expansion and explicit
   node/edge limits. Preserve the edges and source spans needed to substantiate
   a path when forming the final context. Test whether independent cosine
   selection currently drops bridge evidence; this is a hypothesis.
5. **Optional reranker:** reuse the existing hook before the final evidence cap
   if it helps the benchmark. Bound inputs, apply a timeout, retain a deterministic
   fallback, and measure added latency/cost. Keep large model dependencies outside
   the default image. Evaluate Jev separately if its model/API becomes specified.

Primary files: `src/core/query.py`, `src/core/utils.py`, query configuration,
`src/preciso_mcp/server.py`, `tests/test_evidence_selection.py`, and evaluation scripts.
Retain query modes and source references while adding backward-compatible options.

Acceptance: improvements beat the frozen baseline on held-out evidence metrics
without new citation/integrity failures; latency, memory, and token tradeoffs are
reported. Set numeric gates after the pilot, before examining held-out results.
Review existing README evaluation claims against reproducible runs.

## Phase 5 — decide whether live Qdrant retrieval earns its complexity

Only proceed if local vector storage misses the measured RAM/latency/corpus-size
requirements. Compare local storage and Qdrant using the same vectors, filters,
questions, hardware budget, and evidence pipeline.

A live backend needs a storage adapter and explicit lifecycle: collection naming,
model/dimension fingerprinting, stable IDs, updates, deletions, tenant filters,
batch limits, health failures, reindexing, and consistency after ingestion.
Keep local artifacts authoritative initially and treat Qdrant as a rebuildable
index, with explicit revision checks. An exported snapshot is not automatically
a current retrieval index. Test candidate parity before enabling it for queries.

Neo4j should remain an export/inspection option unless a separate query workload
demonstrates value. Replacing both storage systems at once makes correctness and
resource regressions harder to isolate.

## Delivery order

1. Configuration and clean-package checks; capture baseline.
2. Locked multi-stage build, persistent volume, MCP launcher, and smoke tests.
3. One measured ingestion/export memory improvement at a time.
4. Retrieval benchmark, then individual candidate/evidence experiments.
5. Optional live Qdrant adapter only after the comparison supports it; service
   containerization remains outside this plan.

Keep each step in a focused commit with verification results. Build/container
work and retrieval quality work have separate acceptance gates. No production
migration or destructive graph conversion is needed to start this plan.
