# Production readiness

Review date: 2026-10-10. Scope: the core-only branch and private stdio MCP use.

PRECISO has stronger data safety and a minimal container build. It is not yet
verified for a production release. Backup restoration, representative resource
budgets, provider integration, and release rollback remain open gates.

## Implemented controls

| Control | Behavior | Evidence |
|---|---|---|
| Strict loading | Reject malformed existing stores without replacing them | JSON loading regression tests |
| Input validation | Validate types, finite weights, record counts, and payload bytes before mutation | Validation and unchanged-store tests |
| File boundaries | Restrict resolved input paths and file sizes; generate safe reconciliation names | Traversal, symlink, extension, and size tests |
| Atomic artifacts | Publish complete files with same-directory replacement and filesystem sync | Serialization, replacement, and sync failure tests |
| Transaction recovery | Restore disk and memory after failure; recover interruption before opening stores | Failure, cancellation, retry, and subprocess termination tests |
| Read isolation | Supported reads wait for complete mutations | Reader isolation regression test |
| Process ownership | Reject a second MCP runtime for the same graph directory | Ownership acquisition and release tests |
| Embedding identity | Reject incompatible populated indexes, including models with equal dimensions | Model and revision mismatch tests |
| Provider deadlines | Bound embedding queue and provider time; probe Ollama asynchronously | Timeout, cancellation, and permit recovery tests |
| Worker scheduling | Keep at most four default embedding workers, rather than one task per batch | Ordering tests and paused-provider task benchmark |
| Offline backup | Copy a stopped artifact set, verify checksums, and restore into a fresh directory | Byte equality, reopen/query, corruption, locking, and failure tests |
| Container packaging | Build a wheel; copy core dependencies and tokenizer cache into a non-root runtime | Locked container test stage and MCP smoke procedure |

The defaults limit ingestion to 50,000 records and 26,214,400 bytes. Embedding
requests have a 60-second deadline. Startup probing has a 15-second deadline.
Partial ingestion is disabled. The runtime image requires valid source IDs.
See `.env.example` for configuration names.

Tests establish behavior at selected failure boundaries. They do not establish
power-loss durability for every filesystem or production storage device. Local
macOS and container Linux tests use POSIX filesystem semantics.

## Deployment boundary

Use one active MCP runtime per graph directory. Keep local graph and vector
storage. Connect to a configured host or external embedding provider. Additional
Qdrant, Neo4j, and Ollama containers are excluded from this scope.

A private stdio client needs no listening port. Shared or public use requires a
separate transport and access design. That design must include authentication,
authorization, workspace isolation, quotas, and audit logging.

## Open release gates

1. **Backup operations.** The offline backup and restore fixture is verified.
   Repeat the drill with representative deployment data. Preserve reviewed inputs.
   Define retention, separate storage, recovery time, and acceptable data loss.
   A transaction journal does not protect against volume loss.
2. **Resource budgets.** Measure startup, peak memory, ingestion persistence, and
   query latency with representative corpora. Set CPU, memory, PID, and disk budgets.
   Bound request admission and lock waiting. Define cache retention.
3. **Provider integration.** Test the selected real embedding model and revision.
   Verify unavailable-provider behavior and readiness reporting. Fallback tests do
   not establish semantic retrieval quality.
4. **Retrieval quality.** Freeze reviewed questions and required evidence spans.
   Measure recall, bridge coverage, citations, no-answer behavior, latency, and tokens.
   Compare proposed changes with this baseline before changing retrieval defaults.
5. **Observability.** Define structured stderr logs, duration measurements, operation
   identifiers, and error categories. Verify credential and document redaction.
6. **Shutdown.** Verify client disconnect and SIGTERM behavior with mounted data.
   Forced-termination recovery tests already exercise selected commit boundaries.
7. **Release compatibility.** Define artifact and package version compatibility.
   Test image rollback against supported data. Review locked dependency updates
   and scan shipped packages before release.
8. **Platform coverage.** Run the container gates on Linux amd64 and arm64. A base
   image that supports both platforms does not prove application compatibility.

## Verification paths

- [Backup and restoration](backup-recovery.md) gives the offline operating procedure.
- [Engineering decisions](engineering-log.md) records reasons and limitations.
- [Container operation](container-guide.md) gives build and smoke procedures.
- [Performance](performance.md) separates local measurements from system claims.
- `tests/test_transactions.py` exercises recovery and read isolation.
- `tests/test_json_storage_loading.py` exercises strict startup loading.
- `.github/workflows/ci.yml` runs offline tests and container verification.

CI configuration is a gate definition. Check its actual result before releasing.
