# Lightweight Docker deployment and retrieval improvement plan

Date: 2026-10-04. Baseline: `core-graphrag` at `b0a32b4`.
Status: proposed implementation sequence; Docker and retrieval changes below
have not been implemented or benchmarked.

## Objective and decision

Keep PRECISO a small, local-first MCP application with reproducible container
builds, persistent data, bounded resource use, and better evidence retrieval.
Preserve the core-only scope without supply-chain integration.

Assume the initial deployment is one local user and one active MCP process per
graph. A shared, always-on service would need a separate transport, access-control,
and concurrent-storage design; it is not necessary for the first container.

Use one Python application container. Make Qdrant, Neo4j, and Ollama separate,
optional Compose services. Keep local storage as the default until measurements
justify a backend migration. Docker packaging alone does not improve retrieval.

## What the repository establishes

| Area | Current behavior | Consequence |
|---|---|---|
| Runtime | Python MCP server; `mcp.run()` defaults to stdio | Client must attach stdin/stdout to the container |
| Storage | NetworkX graph, JSON stores, NanoVectorDB | The graph directory must survive container replacement |
| Data location | `preciso_mcp/server.py` hardcodes `GRAPH_IS_HERE` | Add an environment override before defining volume mounts |
| Qdrant / Neo4j | Optional export adapters | Starting their containers does not route queries through them |
| Dependencies | Core requirements plus cloud/export extras; no lockfile | Lock supported builds and install only selected extras |
| Embeddings | Four concurrent requests; batches of eight texts | Requests are bounded, but queued tasks/results can still consume memory |
| Retrieval | Entity, relationship, and direct-chunk candidates; final cosine selection | Evaluate whether final selection loses necessary bridge evidence |
| Reranking | Existing optional hook, not enabled by the MCP default | Reuse the hook only if measured gains justify its cost |
| Containers | No Dockerfile or Compose configuration | Establish a measured first image rather than promise a size |

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

Primary files: `config.py`, `preciso_mcp/server.py`, `pyproject.toml`,
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
| `runtime-exports` | Optional variant with export SDKs | Only when exports are requested |

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

Acceptance: record image size, layer contents, cold start, and RSS; verify no
secrets/model files entered the image; complete handshake, ingest/query, restart,
backup/restore, and interrupted-ingestion checks against mounted data.

## Phase 3 — optional service containers and MCP launch

Use one `compose.yaml` with named persistent volumes and optional profiles.
[Compose profiles](https://docs.docker.com/compose/how-tos/profiles/) allow users
to activate selected services instead of starting the entire stack.

| Service | Default | Role | Application address inside Compose |
|---|---|---|---|
| `preciso` | Client-launched | Core MCP runtime and local graph | Attached stdio |
| `qdrant` | Off; profile `qdrant` | Existing vector export target initially | `http://qdrant:6333` |
| `neo4j` | Off; profile `neo4j` | Existing graph export target initially | `bolt://neo4j:7687` |
| `ollama` | Off; profile `ollama` | Optional embedding service | `http://ollama:11434` |

Pin service versions, add readiness checks, and persist each service's data.
Do not require optional databases in the application's unconditional dependency
list. Keep host ports unpublished unless needed; bind local debugging ports to
loopback. Configure credentials at runtime and never bake them into images.

The following are intended commands after implementation, not commands that
work in the current checkout:

```bash
docker compose build preciso
docker compose run --rm --no-deps -T preciso
docker compose --profile qdrant up -d qdrant
docker compose --profile neo4j up -d neo4j
docker compose --profile ollama up -d ollama
```

Wire the MCP client launcher to the attached `run` command and confirm stdin
stays open, no TTY is allocated, and Compose emits no non-protocol stdout.
[`docker compose run`](https://docs.docker.com/reference/cli/docker/compose/run/)
provides `--no-deps`, `--rm`, and `-T`. Start optional services separately before
using them; do not leave a second detached MCP writer running on the same graph.

For an existing host Ollama on macOS, document `host.docker.internal` instead of
`localhost` inside the container. Measure host and container model serving
separately; do not assume equal acceleration or memory use.

Neo4j remains optional because its heap and page cache need their own budget;
the application image size does not describe whole-stack memory use. Configure
these settings using the
[Neo4j container documentation](https://neo4j.com/docs/operations-manual/current/docker/configuration/).
Follow [Qdrant's quickstart](https://qdrant.tech/documentation/quickstart/) for
its persistent storage setup, then test export/query inspection after restart.

## Phase 4 — reduce resource use where profiling proves value

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

## Phase 5 — improve retrieval with an evidence benchmark

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

Primary files: `core/query.py`, `core/utils.py`, query configuration,
`preciso_mcp/server.py`, `tests/test_evidence_selection.py`, and evaluation scripts.
Retain query modes and source references while adding backward-compatible options.

Acceptance: improvements beat the frozen baseline on held-out evidence metrics
without new citation/integrity failures; latency, memory, and token tradeoffs are
reported. Set numeric gates after the pilot, before examining held-out results.
Review existing README evaluation claims against reproducible runs.

## Phase 6 — decide whether live Qdrant retrieval earns its complexity

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
2. Locked multi-stage build and core MCP container smoke tests.
3. Optional database/model profiles, persistent volumes, and launcher documentation.
4. One measured ingestion/export memory improvement at a time.
5. Retrieval benchmark, then individual candidate/evidence experiments.
6. Optional live Qdrant adapter only after the comparison supports it.

Keep each step in a focused commit with verification results. Build/container
work and retrieval quality work have separate acceptance gates. No production
migration or destructive graph conversion is needed to start this plan.
