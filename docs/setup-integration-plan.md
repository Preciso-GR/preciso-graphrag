# Simple setup integration plan

Status: scope approved on 2026-10-16. Evaluation comes before provider integration.
No default model has been selected. Proposed commands do not exist yet.

Stage 1 initial screen is complete. See [measured results](fastembed-evaluation.md).
The candidate's input truncation blocks default adoption. Integration awaits review.

The [expanded comparison](embedding-model-selection.md) now recommends Granite
Small English R2 for the next optional built-in integration. It covers Nomic,
Granite, and BGE using the same fixtures. No production default has changed.

## Outcome

An individual macOS user connects PRECISO to Codex without cloning this repository,
creating a virtual environment, or editing configuration files. Each project has
its own collection and embedding identity. Model files use a shared local cache.

## Agreed flow

1. Run the proposed `uvx preciso-graphrag setup` command. Document installation of
   uv as a prerequisite; uvx does not install Ollama or model weights itself.
2. Select local or API embeddings.
3. For local use, recommend the evaluated built-in English model. Detect Ollama
   and offer supported models as alternatives. Do not require Ollama installation.
4. Show the selected model, publisher, language, download size, and cache location.
   Ask before downloading missing model files. Reuse verified cached files.
5. If a download fails, retain the selection and offer retry, cancellation, or an
   explicit change to API setup. Never change providers silently.
6. For API use, select an existing supported provider and model. Store the key in
   macOS Keychain. Offer an environment variable when secure storage is unavailable.
   Explain that the provider receives document text. Do not save keys in Codex
   configuration, project files, logs, or command-line arguments.
7. Select a project and create its collection outside the source checkout.
8. Test the selected embedding provider before opening populated indexes.
9. Preview the Codex configuration change. Ask before applying it. Preserve other
   MCP entries and existing PRECISO settings. Prefer the supported Codex management
   interface after checking its current official documentation and installed CLI.
10. Test a real MCP connection and report collection location and provider readiness.

The normal server command must run without interactive prompts. Setup prompts use
the terminal; MCP stdout remains reserved for protocol messages. The generated
launch command must retain the optional dependencies selected during setup and
load saved settings before config module import.

## Stage 1: bounded evaluation

Use a separate feature branch, temporary environment, cache, and disposable graph.
Do not change runtime dependencies, defaults, or user data. Use one inference
thread, one embedding request, small batches, and CPU only. Avoid model sweeps.

Evaluate FastEmbed with `BAAI/bge-small-en-v1.5` as a candidate, not an accepted
default. Record the published library version, ONNX source revision, artifact
hashes, actual cache size, and license. FastEmbed and its model are separate works.

Measure baseline and candidate with the same existing six-case retrieval fixture.
Report evidence recall, complete-evidence cases, invalid citations, unsupported
evidence returns, and query timings. This fixture tests direct chunk retrieval;
it does not establish graph reasoning, answer accuracy, or production quality.
Compare the recorded Ollama pilot only with its environment and timing limits
stated. A new live Ollama run is unnecessary for the initial bounded screen.

Measure dependency archive bytes from cached wheels, record the installer report, installed environment
bytes, model cache bytes, initialization, warm queries, and peak process RSS.
Separate model loading from download time. Run again in a fresh process with
offline settings and cached files; test restart retrieval in a disposable graph.

Check tokenization and truncation on overlength input. PRECISO currently allows
larger embedding inputs than this small model supports. Silent evidence loss is
a blocker. A future adapter must reject overlength input clearly or use a reviewed
splitting strategy before the model becomes a default. Do not change source chunks
or average vectors merely to make the pilot pass.

Acceptance for further evaluation: finite nonzero vectors with stable dimensions;
repeatable retrieval; no required Qdrant account, database, or running service;
cached offline execution; visible download consent boundary; reproducible identity;
and a clear input-limit policy. Record resource costs and retrieval trade-offs for
review. No numerical production budget or representative quality threshold has
been agreed yet; do not declare production acceptance from this pilot.

## Stage 2: review and provider integration

Review the measured report with the user before adding a provider. If accepted,
add an optional built-in embedding extra behind the existing EmbeddingFunc
interface. Keep the base server and API-only installation small. Offload synchronous
inference from the async MCP event loop, bound concurrency and internal threads,
and validate shapes, finite values, zero vectors, and model input limits.

Persist model revision, artifact identity, dimension, normalization, and query/document
preprocessing identity. Existing collections retain their provider. A changed model
requires an explicit new index or rebuild. If the provider fails, stop embedding
operations and preserve data. Do not substitute lexical fallback for normal use.
Review third-party license and notice requirements for redistributed artifacts.

## Stage 3: setup command and secure configuration

Add explicit setup and server entry points. Use separate public settings and a
credential reference. Validate configuration before committing it atomically.
Define precedence for explicit environment values, saved project settings, and
defaults. Ensure uvx launches with the chosen provider dependencies on later runs.
Do not install dependencies dynamically inside a running MCP server.

Make setup repeatable. Do not duplicate Codex entries or overwrite a changed
configuration. Verify the user's project path and preserve existing graph data.
Do not store unrelated projects in one default collection. Keep the model cache
independent of collection deletion. Define cache inspection and removal commands.

## Stage 4: verification and distribution

Test clean and repeated setup, each provider path, Keychain failure, masked input,
download refusal, network failure, interrupted download, unavailable providers,
model mismatch, overlength input, config rollback, and MCP startup without a TTY.
Verify stdout remains valid MCP. Run existing tests and container checks.

Publish a versioned Python package to PyPI before claiming uvx installation is
available. Test from outside the checkout on a clean macOS account. Check both
Apple Silicon and Intel compatibility before claiming both. Keep manual setup
documented for Windows and Linux. Use a PR and passing CI before merging to main.

## Sources

- [FastEmbed](https://github.com/qdrant/fastembed)
- [Supported models](https://qdrant.github.io/fastembed/examples/Supported_Models/)
- [Candidate model card](https://huggingface.co/BAAI/bge-small-en-v1.5)
- [Existing retrieval pilot](retrieval-pilot.md)
- [MCP operation](mcp-server.md)
