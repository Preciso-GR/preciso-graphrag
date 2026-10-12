"""Measure the actual MCP server with a small offline corpus. No model calls."""

import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from scripts.smoke_mcp import result_dict


def rss(pid):
    if sys.platform.startswith('linux'):
        pages = int(Path(f'/proc/{pid}/statm').read_text().split()[1])
        return round(pages * os.sysconf('SC_PAGE_SIZE') / 1024**2, 2)
    import subprocess
    kb = int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(pid)], text=True).strip())
    return round(kb / 1024, 2)


async def benchmark():
    with tempfile.TemporaryDirectory(prefix='preciso-mcp-memory-') as temporary:
        root = Path(temporary)
        pidfile = root / 'server.pid'
        env = dict(os.environ, GRAPHRAG_EMBEDDING_PROVIDER='fallback', GRAPHRAG_EMBEDDING_CONCURRENCY='1',
                   GRAPHRAG_MCP_WORKDIR=str(root / 'graph'), OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
        # exec preserves the PID while replacing the wrapper with the server.
        wrapper = 'import os,sys; from pathlib import Path; Path(sys.argv[1]).write_text(str(os.getpid())); os.execv(sys.executable,[sys.executable,"-m","preciso_mcp.server"])'
        params = StdioServerParameters(command=sys.executable, args=['-c', wrapper, str(pidfile)], env=env)
        started = time.perf_counter()
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=60)) as session:
                await session.initialize()
                startup = time.perf_counter() - started
                pid = int(pidfile.read_text())
                idle = rss(pid)
                text = 'Alice maintains the document index. Verified snapshots permit recovery of the complete corpus.'
                payload = {'document_id': 'memory-check', 'entities': [], 'relationships': [], 'chunks': [
                    {'chunk_id': str(i), 'content': f'Record {i}: {text}'} for i in range(1000)]}
                started = time.perf_counter()
                result = result_dict(await session.call_tool('ingest_graph_tool', {'payload': payload}))
                if result['status'] != 'success':
                    raise RuntimeError(result)
                ingestion = time.perf_counter() - started
                loaded = rss(pid)
                timings = []
                for _ in range(21):
                    started = time.perf_counter()
                    result = result_dict(await session.call_tool('query_graph_tool', {'query': text, 'mode': 'mix'}))
                    timings.append((time.perf_counter() - started) * 1000)
                    if not result.get('raw_data', {}).get('data', {}).get('chunks'):
                        raise RuntimeError('No evidence returned')
                report = {'records': 1000, 'dimension': 8, 'provider': 'fallback', 'embedding_concurrency': 1,
                          'startup_to_handshake_seconds': round(startup, 4), 'idle_server_rss_mib': idle,
                          'loaded_server_rss_mib': loaded, 'post_query_server_rss_mib': rss(pid),
                          'ingestion_seconds': round(ingestion, 4), 'warm_query_median_ms': round(statistics.median(timings[1:]), 3),
                          'warm_query_p95_ms': round(sorted(timings[1:])[18], 3),
                          'limitations': 'One run, 20 warm queries, 1000 short chunks, no graph edges or real embeddings. RSS samples are not a peak memory measurement. MCP transport is included; client memory is excluded.'}
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    asyncio.run(benchmark())
