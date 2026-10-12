# Runtime resource baseline

Purpose: measure local storage, query latency, and a small rollback check.
Runs started on 2026-10-11 and completed on 2026-10-12.
All graph data was temporary. No Ollama inference or cloud call was made.

RSS means resident set size. RSS measures process memory held in physical memory.
MiB means 1,048,576 bytes. Process peak RSS is a cumulative high-water measurement.
The 95th percentile is the value at rank 19 among 20 sorted query durations.

## Core storage measurements

Environment: Linux arm64 in Docker Desktop, Python 3.12.15. The runtime used its
bundled tokenizer cache. Networking was disabled. Each case ran in a fresh process.
One embedding worker and one numerical-library thread were used.

The corpus contained short evidence chunks without graph entities or relationships.
Synthetic vectors had 1,024 dimensions. The query matched known source content.
Each case used one warm-up query and 20 measured queries.

| Measurement | 100 chunks | 1,000 chunks |
|---|---:|---:|
| Initialization after script imports | 0.586 s | 0.305 s |
| Empty storage RSS | 127.01 MiB | 127.17 MiB |
| RSS after ingestion | 130.41 MiB | 143.23 MiB |
| Process peak after ingestion | 130.30 MiB | 185.93 MiB |
| Warm query median | 0.229 ms | 0.398 ms |
| Warm query 95th percentile | 0.346 ms | 0.531 ms |
| Ingestion and persistence | 0.0540 s | 0.2241 s |
| Artifact bytes | 887,766 | 8,872,175 |
| Verified backup | 0.0022 s | 0.0117 s |
| Restore copy and checks | 0.0015 s | 0.0104 s |

Memory samples and peak counters were read at different times. Small differences
between those readings are not evidence that the peak counter is an exact sample
of the later RSS reading. The 1,000-chunk ingestion peak shows transient allocation
above the steady state. This result does not identify the allocation bottleneck.

The raw float32 matrix calculation is:

```text
1,000 records × 1,024 dimensions × 4 bytes = 4,096,000 bytes
4,096,000 / 1,048,576 = 3.91 MiB
```

Total artifact size was 8.46 MiB. Metadata, serialized vectors, and evidence explain
why raw matrix size alone is not the storage budget. Runtime memory also includes
Python, libraries, the tokenizer, records, and temporary arrays.

These measurements exclude the MCP server, transport, model inference, and answer
generation. The restore time excludes reopening and subsequent verification queries.
Both restored graphs passed their known-evidence query after reopening.

## Actual MCP server measurements

A separate run started the installed MCP server with lexical fallback embeddings.
The run used 1,000 short chunks and eight-dimensional vectors. It included MCP
transport. The client process was separate from the measured server process.

| Measurement | Observed result |
|---|---:|
| Process launch to MCP handshake | 1.024 s |
| Idle server RSS | 151.40 MiB |
| Server RSS after ingestion | 153.33 MiB |
| Server RSS after warm queries | 153.65 MiB |
| Ingestion through MCP | 0.0518 s |
| Warm query median through MCP | 1.177 ms |
| Warm query 95th percentile through MCP | 1.344 ms |

These RSS samples do not measure the server's transient peak. Fallback embedding
cost does not represent the installed semantic model. Do not combine this table
with the synthetic-vector table to claim a measured production memory budget.

## Host initialization outlier

The macOS source run used Python 3.13.5. Its first initialization took 66.899 seconds.
The second case initialized in 0.460 seconds. The cause was not traced. Tokenizer
cache preparation is a hypothesis, not a verified root cause.

The Docker run completed initialization with networking disabled and a bundled
cache. This establishes the offline image path. It does not explain the host outlier.
Keep the outlier in the record until a traced cold-start run explains it.

## Reproduce

From an installed source checkout, run the core measurement:

```sh
.venv/bin/python -m scripts.benchmark_runtime
```

On macOS, the command needs permission to run `ps` for its own process. The report
is stored in `evals/results/runtime-baseline.json`. Generated reports are ignored.

To reproduce the offline image measurement, mount scripts read-only:

```sh
docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount type=bind,source=/absolute/repository/scripts,target=/app/scripts,readonly \
  --entrypoint python preciso-graphrag:local \
  -m scripts.benchmark_runtime --output /tmp/runtime-baseline.json
```

Use `-m scripts.benchmark_mcp_memory` with the same container options for the MCP
measurement. Both commands create and remove temporary graph directories.

## Rollback check

The current image came from application commit `2116c76`. The previous image was
built from commit `b8a67ea`. Both images used Linux arm64 and Python 3.12.

The current image created a one-document fallback graph in a disposable volume.
The previous image then reopened that graph. The previous image accepted an identical
ingestion replay, restarted, and retrieved persisted evidence. Both smoke runs passed.

This verifies one release pair with an unchanged artifact format. It does not
verify schema migration, arbitrary old releases, semantic model changes, or rollback
against a representative production corpus. Preserve a verified backup before a
real release change.

## Remaining budget checks

1. Use representative graph entities, relationships, and evidence lengths.
2. Measure the full MCP server peak with the selected semantic model.
3. Measure Ollama memory separately from the application container.
4. Run cold queries and concurrent request load.
5. Trace persistence allocations before making memory optimizations.
6. Test selected container limits under that workload.

The current results establish a baseline. They do not establish safe production
CPU, memory, disk, or latency limits. No runtime defaults were changed.
