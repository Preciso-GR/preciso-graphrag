# Container operation

Scope: one private MCP client and one runtime per graph directory. No network port
is required. Qdrant, Neo4j, and Ollama containers are outside this deployment.

## Build

Run these commands from the repository root.

1. Build the test stage.

   ```sh
   docker build --target test -t preciso-graphrag:test .
   ```

2. Build the runtime stage.

   ```sh
   docker build --target runtime -t preciso-graphrag:local .
   ```

The runtime build does not run the test stage automatically. CI runs both stages.
The image uses Python 3.12 and a pinned base digest. Review dependency and base-image
updates together. Regenerate lock files before testing a dependency update.

## Start the server

If Ollama runs on the Docker Desktop host, use `host.docker.internal` as its hostname.
`localhost` inside the container refers to the container itself.

Configure the MCP client to execute this command. Keep stdin attached. Do not add a TTY.

```sh
docker run --rm -i \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount type=volume,source=preciso-data,target=/data \
  -e GRAPHRAG_EMBEDDING_PROVIDER=ollama \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  preciso-graphrag:local
```

The graph is stored in `/data/graph`. The runtime user has UID and GID 10001.
A new Docker volume inherits ownership from the image directory. Existing volumes
and bind mounts must permit that user to write. Keep original source inputs separately.

To ingest files, mount a reviewed input directory read-only at `/inputs`. File tools
reject paths outside that directory. Reconciliation writes under the graph directory.
The application root remains read-only. The tokenizer cache is included in the image.

The runtime image contains core dependencies only. Cloud embeddings and remote
exports require their optional SDKs and a separately tested image variant.

Set CPU, memory, and PID limits after measuring the selected corpus and provider.
The command above does not establish a resource budget.

## Verify the protocol

Use a new, disposable volume. The following test starts the server twice.

```sh
.venv/bin/python -m scripts.smoke_mcp -- docker run --rm -i \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount type=volume,source=preciso-smoke,target=/data \
  -e GRAPHRAG_EMBEDDING_PROVIDER=fallback preciso-graphrag:local
```

The test verifies the MCP handshake, ingestion, restart persistence, and retrieval.
The fallback provider is a lexical test tool. It does not verify semantic quality.
Do not run this test against a graph that contains user data.

## Recover and correct data

On startup, the server recovers an interrupted transaction before opening stores.
Do not delete `.preciso-transaction` or edit files while the server runs.
If recovery fails, preserve the directory and investigate the reported storage error.

Stop the runtime before copying graph data for a backup. Preserve the entire graph
directory and the reviewed inputs. A live file copy can mix revisions. The journal
provides interruption recovery; it does not protect against volume loss.

Ingestion is additive. It is not document replacement. For source corrections,
build a fresh graph from the corrected complete corpus. Keep the previous graph
until verification succeeds. Model or revision changes also require a fresh index.

Partial ingestion is disabled by default. `GRAPHRAG_ALLOW_PARTIAL_INGEST=true`
explicitly enables legacy partial acceptance. The container requires valid source IDs.

## Release limits

See [production readiness](production-readiness.md) for unresolved release gates.
Container packaging does not establish retrieval quality or production readiness.

## Local verification record

On 2026-10-05, the Linux arm64 test stage passed 191 tests, lint checks, and
summary integrity guards. The runtime passed the MCP ingestion and restart test
with a read-only root filesystem and a persistent volume. Offline tokenization
also passed with networking disabled.

Docker reported 406,125,190 bytes for the runtime image, about 387 MiB uncompressed.
The image uses UID and GID 10001. Runtime inspection found no pip, pytest, ruff,
OpenAI, Cohere, Qdrant, or Neo4j package. This is a packaging baseline. It does not
measure startup latency, peak memory, or semantic quality. Local amd64 verification
remains pending. CI defines an amd64 verification gate.

## Prepare the local Ollama test

The host test uses the installed `mxbai-embed-large` model. No API key is required.
It creates a temporary graph and removes it after the test. Existing indexes remain
outside the test. This procedure does not download or install models.

1. Inspect the test configuration without starting the server.

   ```sh
   .venv/bin/python -m scripts.smoke_ollama --dry-run
   ```

2. When the host is available for model inference, run the test.

   ```sh
   .venv/bin/python -m scripts.smoke_ollama
   ```

The test checks active Ollama status, the selected model, ingestion, restart
persistence, and retrieval. It permits 120 seconds for cold model loading and each
embedding request. It reports the detected embedding dimension after success.
An unavailable model fails the test; fallback embeddings cannot satisfy it.

This is a real-provider integration test. A single-document query does not measure
ranking quality. A reviewed multi-document evaluation remains a separate task.
