"""Measure a small local-storage baseline. No Ollama or cloud calls.

Each corpus size runs in a fresh process. Synthetic vectors have the same
1,024 dimensions as the installed model. This is not a semantic quality test.
"""

import argparse
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time


def memory():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    if sys.platform.startswith("linux"):
        pages = int(Path('/proc/self/statm').read_text().split()[1])
        current = pages * os.sysconf('SC_PAGE_SIZE')
    else:
        current = int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(os.getpid())], text=True).strip()) * 1024
    return {"rss_mib": round(current / 1024**2, 2), "process_peak_rss_mib": round(peak / 1024**2, 2)}


async def measure(records, repeats):
    start = time.perf_counter()
    import numpy as np
    from config import build_global_config
    from core.backup import backup_graph, restore_graph
    from core.bootstrap import build_storage_instances, initialize_storage_instances
    from core.query import kg_query
    from core.storage.base import EmbeddingFunc, QueryParam
    from core.transactions import ARTIFACTS
    from core.utils import BasicTokenizer
    from ingest.pipeline import ingest_extracted_json

    async def synthetic(texts, **kwargs):
        return np.asarray([np.random.default_rng(int.from_bytes(hashlib.blake2b(text.encode(), digest_size=8).digest(), 'little')).standard_normal(1024) for text in texts], dtype=np.float32)

    with tempfile.TemporaryDirectory(prefix='preciso-runtime-baseline-') as temporary:
        root = Path(temporary)
        graph = root / 'graph'
        embedding = EmbeddingFunc(1024, 8192, synthetic, provider='synthetic', model_name='deterministic-1024', max_concurrent_requests=1)
        config = build_global_config(working_dir=str(graph), tokenizer=BasicTokenizer(), embedding_func=embedding)
        stores = build_storage_instances(config)
        await initialize_storage_instances(stores)
        ready = time.perf_counter() - start
        idle = memory()
        payload = {'document_id': 'runtime-baseline', 'entities': [], 'relationships': [], 'chunks': [
            {'chunk_id': str(i), 'content': f'Record {i}: Mira owns archive service {i}. Daily encrypted snapshots remain available for fourteen days. Check the checksum before opening a restored index.'}
            for i in range(records)
        ]}
        started = time.perf_counter()
        result = await ingest_extracted_json(payload, stores, config)
        if result['status'] != 'success':
            raise RuntimeError(result)
        ingestion = time.perf_counter() - started
        loaded = memory()
        query = payload['chunks'][0]['content']

        async def search(active, cfg):
            return await kg_query(query=query, knowledge_graph_inst=active['graph'], entities_vdb=active['entities_vdb'],
                                  relationships_vdb=active['relationships_vdb'], text_chunks_db=active['text_chunks'],
                                  chunks_vdb=active['chunks_vdb'], query_param=QueryParam(mode='mix', top_k=5, chunk_top_k=5, only_need_context=True), global_config=cfg)

        timings = []
        for _ in range(repeats + 1):
            started = time.perf_counter()
            response = await search(stores, config)
            elapsed = (time.perf_counter() - started) * 1000
            chunks = (response.raw_data or {}).get('data', {}).get('chunks', []) if response else []
            if 'runtime-baseline::0' not in {chunk['chunk_id'] for chunk in chunks}:
                raise RuntimeError('Expected evidence not returned')
            timings.append(elapsed)
        timings = timings[1:]  # Exclude one warm-up query.
        query_memory = memory()
        disk = sum((graph / name).stat().st_size for name in ARTIFACTS if (graph / name).is_file())
        started = time.perf_counter()
        manifest = backup_graph(graph, root / 'backup')
        backup_seconds = time.perf_counter() - started
        started = time.perf_counter()
        restore_graph(root / 'backup', root / 'restored')
        restore_seconds = time.perf_counter() - started
        cfg = build_global_config(working_dir=str(root / 'restored'), tokenizer=config['tokenizer'], embedding_func=embedding)
        reopened = build_storage_instances(cfg)
        await initialize_storage_instances(reopened)
        response = await search(reopened, cfg)
        if 'runtime-baseline::0' not in {chunk['chunk_id'] for chunk in (response.raw_data or {})['data']['chunks']}:
            raise RuntimeError('Restored evidence not returned')
        return {'records': records, 'dimension': 1024, 'embedding_concurrency': 1,
                'initialization_seconds': round(ready, 4), 'empty_storage_memory': idle,
                'ingestion_seconds': round(ingestion, 4), 'loaded_storage_memory': loaded,
                'query_memory': query_memory, 'queries_measured': repeats,
                'query_median_ms': round(statistics.median(timings), 3),
                'query_p95_ms': round(sorted(timings)[math.ceil(0.95 * len(timings)) - 1], 3),
                'artifact_bytes': disk, 'backup_seconds': round(backup_seconds, 4),
                'restore_copy_seconds': round(restore_seconds, 4), 'backup_artifacts': len(manifest['files']),
                'restored_query_passed': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records', type=int, nargs='+', default=[100, 1000])
    parser.add_argument('--repeats', type=int, default=20)
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--output', default='evals/results/runtime-baseline.json')
    args = parser.parse_args()
    if args.repeats <= 0 or any(n <= 0 or n > 5000 for n in args.records):
        parser.error('repeats must be positive; record counts must be 1–5000')
    if args.child:
        print(json.dumps(asyncio.run(measure(args.records[0], args.repeats))))
        return
    results = []
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', GRAPHRAG_EMBEDDING_CONCURRENCY='1')
    for count in args.records:
        child = subprocess.run([sys.executable, '-m', 'scripts.benchmark_runtime', '--child', '--records', str(count), '--repeats', str(args.repeats)], env=env, capture_output=True, text=True, timeout=120)
        if child.returncode != 0:
            parser.exit(1, child.stderr)
        results.append(json.loads(child.stdout))
    report = {'platform': platform.platform(), 'python': platform.python_version(), 'embedding': 'synthetic deterministic 1024 dimensions',
              'limitations': 'Fresh process per corpus; one run per size; 20 warm queries by default. No graph nodes/edges, model inference, MCP transport, concurrency load, or answer generation. Initialization excludes interpreter startup. RSS includes libraries and fixture data. Peak RSS is cumulative within each process.',
              'results': results}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
