# Local retrieval performance

## Reproduce

From the repository root, run:

```bash
.venv/bin/python -m scripts.benchmark_retrieval
.venv/bin/python -m scripts.benchmark_retrieval --profile /tmp/preciso-retrieval.prof
```

The benchmark uses seeded synthetic vectors and temporary storage. It never
opens an existing graph, calls an external model, or requires API credentials.
It warms each operation once and reports the median of seven runs. Setup and
embedding generation are excluded from the timed operations.

## Measured changes — 2026-10-04

Configuration: 10,000 stored vectors, 500 requested evidence candidates, 256
dimensions. Local macOS arm64, Python 3.13.5, NumPy 2.4.6,
nano-vectordb 0.0.4.3. Baseline: runtime code at commit `2776741`.

| Operation | Before | After | Relative improvement |
|---|---:|---:|---:|
| Bulk metadata lookup | 31.050 ms | 0.491 ms | about 63× |
| Evidence selection, including vector lookup and cosine ranking | 45.213 ms | 6.427 ms | about 7× |

Profiling attributed 56 ms of a 73 ms combined baseline lookup/ranking sample
to NanoVectorDB's record lookup. Its scan checked every stored ID against a
list of requested IDs. Passing a set changes that membership work from
O(stored records × requested IDs) to O(stored records + requested IDs), without
maintaining another persistent index. The wrapper still restores requested
order, duplicate entries, and missing-ID placeholders.

After that change, cosine scoring became the main local ranking cost. The
query array and its norm are now calculated once and reused across candidates.
Tests compare results against the original scalar cosine calculation, including
zero vectors and stable tie ordering.

These are isolated local measurements, not end-to-end query speedups. External
embedding latency, answer generation, disk I/O, dimensions, candidate counts,
and machine load change the overall result. No dependencies or graph formats
were added or changed.

## Embedding concurrency

Embedding requests now share a semaphore with a default limit of four per
server runtime, across entity, relationship, chunk, and query embeddings.
Batch size remains eight texts. Set `GRAPHRAG_EMBEDDING_CONCURRENCY` in the
server environment to override the limit; it must be positive. This bounds
in-flight requests, not the total ingestion payload or accumulated vectors.
Four is a default selected by the user, not a benchmarked throughput optimum.

## Remaining optimization candidates

- Vector lookup still scans the stored records once. A maintained ID index may
  help at larger sizes, but costs memory and requires invalidation; benchmark
  that tradeoff before adding it.
- Local, global, and direct-chunk search branches currently run sequentially.
  Concurrent execution may help service-backed adapters; measure their latency
  before changing error handling and storage-access ordering.
- Ingestion persists complete graph/vector files. Profile realistic additive
  ingestions before changing storage formats or adding incremental persistence.
