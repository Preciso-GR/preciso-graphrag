# Development workflow

PRECISO turns reviewed document extractions into a local evidence graph. The MCP
server exposes ingestion, retrieval, status, summaries, and optional export tools.

## Repository layout

| Directory | Responsibility |
|---|---|
| `src/core/` | Retrieval, merging, local storage, and transactions |
| `src/ingest/` | Extraction parsing, validation, and ingestion |
| `src/preciso_mcp/` | MCP startup and tool interfaces |
| `src/config.py` | Runtime settings, providers, and prompt defaults |
| `tests/` | Automated offline regression tests |
| `tests/manual/` | Runnable integrity guards and manual client examples |
| `scripts/` | Launchers, benchmarks, smoke tests, and evaluation commands |
| `docs/` | Architecture, operation, decisions, and release gates |
| `evals/fixtures/` | Committed evaluation inputs and expected evidence |
| `skills/` | Agent extraction instructions |

`GRAPH_IS_HERE/`, `extractions/`, and `to_be_extracted/` are local data directories.
They are not application source. Do not commit operational artifacts or private inputs.
Build requirements and lock files remain at the root for standard build commands.

## Set up development

1. Create a virtual environment.

   ```sh
   python3 -m venv .venv
   ```

2. Install the editable project and development dependencies.

   ```sh
   .venv/bin/python -m pip install -e . -r requirements-dev.txt
   ```

3. Create a branch for the change.

   ```sh
   git switch -c your-change
   ```

The editable install connects imports to `src/`. Repeat installation after a source
layout change. Python module names remain `core`, `ingest`, and `preciso_mcp`.

## Implement and verify

1. Describe the expected behavior and reproduce the failure.
2. Inspect the relevant source path and existing tests.
3. Make the smallest sound change.
4. Run the relevant regression tests.
5. Run the required checks below.
6. Inspect the diff for accidental data, credentials, and unrelated changes.

```sh
.venv/bin/python -m compileall -q src scripts
.venv/bin/python -m ruff check src tests scripts
.venv/bin/python -m pytest -q
.venv/bin/python tests/manual/summary_merge_manual.py
.venv/bin/python tests/manual/marker_leak_manual.py
git diff --check
```

Run the [container gates](docs/container-guide.md) for packaging or runtime changes.
Use the [retrieval pilot](docs/retrieval-pilot.md) for retrieval comparisons. Its small
synthetic results do not replace a reviewed held-out evaluation.

For performance work, record the baseline and measure the result. Separate provider
latency from local storage and ranking work. Do not claim gains from unmeasured changes.

## Review and release

The change description must state the problem, behavior, verification, and limitations.
Explain intentional compatibility changes. Document operational changes with short
instructions and consistent terms. See [engineering decisions](docs/engineering-log.md).

Before release, require passing source and container CI. Verify the installed wheel
outside the checkout. Check data compatibility and model identity. Complete the open
[production gates](docs/production-readiness.md), including restoration and rollback.

The container job uses locked dependencies. The Python-version matrix checks source
compatibility with its declared dependency ranges. Passing one does not replace the other.
Real provider tests run manually and must use disposable graphs.

## Report a defect

Include the command or tool call, expected behavior, actual behavior, runtime version,
and relevant redacted logs. Remove API keys, credentials, and private document content.
Do not attach private graph artifacts to public issues.

Extraction skill changes must include a source example and expected extraction.
Review generated evidence against that source before reporting an evaluation score.
