# Offline backup and restoration

Scope: one stopped local graph directory. No provider calls are required.
This procedure uses the same installed package as the MCP server.

## What the backup contains

The backup copies the supported graph, vector, and JSON artifacts. It preserves
embedding fingerprints inside the vector files. It excludes lock files, transaction
journals, source documents, extraction files, and reconciled output directories.
Preserve reviewed source inputs separately.

The manifest records each artifact's byte count and SHA-256 hash. Verification
detects changed bytes. It does not establish authenticity, source correctness,
or compatibility with another release. Keep backup directories private and immutable.

## Create a backup

Use a destination that does not exist. Use storage outside the graph directory.
For volume-loss protection, copy the verified backup to separate storage.

1. Stop the MCP runtime and other graph writers.
2. Select the correct graph directory.
3. Run the backup command.

   ```sh
   .venv/bin/python -m preciso_mcp.backup_cli backup \
     GRAPH_IS_HERE /absolute/backup/location/snapshot-001
   ```

4. Verify the completed backup.

   ```sh
   .venv/bin/python -m preciso_mcp.backup_cli verify \
     /absolute/backup/location/snapshot-001
   ```

The command rejects an active runtime or mutation. It rejects unfinished
transactions. Recover an interrupted graph through normal startup before taking
its backup. Stop the runtime after recovery completes.

The command copies into a private staging directory. It publishes that directory
after successful copy and verification. Copy failures do not publish a partial
backup. Do not modify source, destination, or backup paths during this operation.

## Restore into a fresh directory

Do not restore over an existing graph. Keep the previous directory until verification
of the restored graph succeeds.

1. Verify the selected backup.
2. Select a destination that does not exist.
3. Restore the artifacts.

   ```sh
   .venv/bin/python -m preciso_mcp.backup_cli restore \
     /absolute/backup/location/snapshot-001 /absolute/graph-restored
   ```

4. Set `GRAPHRAG_MCP_WORKDIR` to the restored directory.
5. Configure the same embedding provider, model, revision, and dimension.
6. Start one MCP runtime.
7. Check server status, graph counts, and known evidence queries.

Restoration checks copied bytes before publishing the new directory. It rejects
changed backup content and existing destinations. It does not generate embeddings
or rebuild indexes. The original fingerprint remains in each vector artifact.

If the command fails after a directory sync error, inspect the destination before
retrying. Publication may already have completed. Never remove an existing directory
merely to bypass the fresh-destination requirement.

## Use the command in Docker

The runtime image includes `preciso_mcp.backup_cli`. Override its normal server
entrypoint to run the backup command. Keep the server stopped during the operation.

Example: mount the stopped graph volume and a dedicated backup directory.
The backup directory must permit UID 10001 to write.

```sh
docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount type=volume,source=preciso-data,target=/data \
  --mount type=bind,source=/absolute/backups,target=/backups \
  --entrypoint python preciso-graphrag:local \
  -m preciso_mcp.backup_cli backup /data/graph /backups/snapshot-001
```

Use the same mounts with `verify /backups/snapshot-001` to verify the backup.
For restoration, mount the selected destination volume writable and use a new path,
such as `/data/restored`. Set the server work directory to that path afterward.
New volumes can already contain `/data/graph`; restoration does not overwrite it.

The Docker commands do not require network access or Ollama. The checksum check
is not a malware scan. Use a trusted backup and restrict its access.

## Verification record and limits

On 2026-10-10, the offline test restored a populated graph into a fresh directory.
Artifact bytes matched the source. The reopened graph contained the expected node,
and the vector query returned its expected evidence chunk.

The full suite passed 210 tests locally and in the locked Linux arm64 image.
The installed runtime CLI also passed with networking disabled and a read-only root.

Regression tests also cover corruption, copy failure, changed bytes during restore,
active ownership, mutation locks, journals, unsafe artifact names, links, and
existing destinations. These checks use small local fixtures.

An operator must still select retention, separate storage, recovery time, and
acceptable data loss. Repeat the drill with representative data and the deployment
filesystem. Image rollback and data migration remain separate release gates.
