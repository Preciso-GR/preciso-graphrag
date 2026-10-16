"""Bounded, optional FastEmbed screen. Never changes the production provider.

Use a disposable environment containing PRECISO and fastembed==0.9.0. First run
with --download-model to fetch one candidate. Later runs use cached files only.
"""

import argparse
import asyncio
from email.parser import BytesParser
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import statistics
import subprocess
import sys
import time
import traceback
import zipfile

MODEL = "BAAI/bge-small-en-v1.5"
REPOSITORY = "Qdrant/bge-small-en-v1.5-onnx-Q"
FILES = ["model_optimized.onnx", "config.json", "tokenizer.json", "tokenizer_config.json",
         "special_tokens_map.json", "vocab.txt", "README.md", "LICENSE"]
ROOT = Path(__file__).resolve().parents[1]


def dependency_footprint(pip_cache):
    """Compare active installed dependencies, not an estimated model footprint."""
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    def closure(root):
        found = set()
        pending = [(root, "")]
        visited = set()
        while pending:
            name, extra = pending.pop()
            name = canonicalize_name(name)
            if (name, extra) in visited:
                continue
            visited.add((name, extra))
            found.add(name)
            for value in importlib.metadata.requires(name) or []:
                requirement = Requirement(value)
                if requirement.marker and not requirement.marker.evaluate({"extra": extra}):
                    continue
                pending.extend((requirement.name, e) for e in ({""} | requirement.extras))
        return found

    baseline = closure("preciso-graphrag")
    added = closure("fastembed") - baseline
    archive_sizes = {}
    if pip_cache:
        for p in pip_cache.rglob("*.body"):
            with p.open("rb") as f:
                if f.read(4) != b"PK\x03\x04":
                    continue
            with zipfile.ZipFile(p) as z:
                meta = next((n for n in z.namelist() if n.endswith(".dist-info/METADATA")), None)
                if meta:
                    info = BytesParser().parsebytes(z.read(meta))
                    archive_sizes[(canonicalize_name(info["Name"]), info["Version"])] = p.stat().st_size
    rows = []
    for name in sorted(baseline | added):
        dist = importlib.metadata.distribution(name)
        paths = {Path(dist.locate_file(f)) for f in (dist.files or [])}
        rows.append({"name": name, "version": dist.version, "added_by_fastembed": name in added,
                     "installed_bytes": sum(p.stat().st_size for p in paths if p.is_file()),
                     "cached_wheel_bytes": archive_sizes.get((name, dist.version))})
    return {"packages": rows,
            "added_installed_bytes": sum(r["installed_bytes"] for r in rows if r["added_by_fastembed"]),
            "added_cached_wheel_bytes": sum(r["cached_wheel_bytes"] or 0 for r in rows if r["added_by_fastembed"]),
            "missing_added_wheel_sizes": [r["name"] for r in rows if r["added_by_fastembed"] and r["cached_wheel_bytes"] is None],
            "limitations": "Active dependency closure in this resolved macOS environment. Installed bytes include recorded package files and omit interpreter, pip, unrecorded bytecode, model cache, and editable source. Wheel sizes are recovered from this run's pip HTTP cache."}


def file_manifest(directory):
    files = []
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            with p.open("rb") as f:
                digest = hashlib.file_digest(f, "sha256").hexdigest()
            files.append({"name": str(p.relative_to(directory)), "bytes": p.stat().st_size,
                          "sha256": digest})
    return files


def prepare(cache):
    from huggingface_hub import HfApi, snapshot_download

    info = HfApi().model_info(REPOSITORY, files_metadata=True)
    selected = [f for f in info.siblings if f.rfilename in FILES]
    print(json.dumps({"model": MODEL, "repository": REPOSITORY, "revision": info.sha,
                      "selected_artifact_bytes": sum(f.size or 0 for f in selected)}), flush=True)
    started = time.perf_counter()
    path = snapshot_download(REPOSITORY, revision=info.sha, cache_dir=str(cache / "hub"),
                             allow_patterns=FILES, max_workers=1)
    manifest = {"model": MODEL, "repository": REPOSITORY, "revision": info.sha,
                "path": path, "download_seconds": time.perf_counter() - started,
                "files": file_manifest(Path(path))}
    (cache / "model-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


async def worker(provider, cache):
    from scripts.benchmark_runtime import memory
    from scripts.evaluate_retrieval_pilot import evaluate

    attempts = []
    original_connect = socket.socket.connect

    def deny_connect(sock, address):
        # PRECISO's storage manager can use local Unix sockets. These are not
        # network access and must retain their normal behavior in this screen.
        if sock.family not in (socket.AF_INET, socket.AF_INET6):
            return original_connect(sock, address)
        attempts.append({"target": str(address), "callers": [f"{Path(f.filename).name}:{f.name}"
                        for f in traceback.extract_stack(limit=14)[:-1]]})
        raise RuntimeError("Network use is forbidden during cached evaluation")

    socket.socket.connect = deny_connect
    fixture_bytes = (ROOT / "evals/fixtures/core_retrieval_pilot.json").read_bytes()
    fixture = json.loads(fixture_bytes)
    started = time.perf_counter()
    details = {}
    embedding = None
    if provider == "fastembed":
        import numpy as np
        import onnxruntime
        onnxruntime.disable_telemetry_events()
        from fastembed import TextEmbedding
        from core.storage.base import EmbeddingFunc

        manifest = json.loads((cache / "model-manifest.json").read_text())
        path = Path(manifest["path"])
        if file_manifest(path) != manifest["files"]:
            raise RuntimeError("Cached model files do not match the reviewed manifest")
        model = TextEmbedding(MODEL, threads=1, providers=["CPUExecutionProvider"],
                              specific_model_path=str(path), local_files_only=True)
        load_seconds = time.perf_counter() - started

        async def embed(texts, **kwargs):
            method = model.query_embed if kwargs.get("context") == "query" else model.passage_embed
            vectors = np.asarray(list(method(texts, batch_size=8, parallel=None)))
            if vectors.shape != (len(texts), 384) or not np.isfinite(vectors).all():
                raise RuntimeError("Invalid embedding shape or values")
            if not (np.linalg.norm(vectors, axis=1) > 0).all():
                raise RuntimeError("Zero embedding")
            return vectors

        # This synchronous wrapper is for a serial evaluation only. Production
        # integration must offload inference from the async event loop.
        embedding = EmbeddingFunc(384, 512, embed, provider="fastembed-evaluation",
                                  model_name=MODEL, model_revision=manifest["revision"],
                                  supports_asymmetric=True, max_concurrent_requests=1)
        timings = []
        for _ in range(6):
            start = time.perf_counter()
            await embed([fixture["questions"][0]["query"]], context="query")
            timings.append((time.perf_counter() - start) * 1000)
        # A deliberately overlength shared prefix tests whether different tail
        # facts disappear from the generated vectors. Do not use in the corpus.
        prefix = "The archive service keeps records. " * 100
        vectors = await embed([prefix + "The owner is Mira.", prefix + "The owner is Omar."])
        from tokenizers import Tokenizer
        tokenizer = Tokenizer.from_file(str(path / "tokenizer.json"))
        tokenizer.no_truncation()
        details = {"fastembed_version": importlib.metadata.version("fastembed"),
                   "model": MODEL, "source_revision": manifest["revision"],
                   "model_files_bytes": sum(f["bytes"] for f in manifest["files"]),
                   "model_initialization_seconds": load_seconds,
                   "warm_embedding_median_ms": statistics.median(timings[1:]),
                   "overlength_tail_vectors_identical": bool(np.array_equal(vectors[0], vectors[1])),
                   "overlength_text_characters": len(prefix), "threads": 1,
                   "overlength_untruncated_tokens": len(tokenizer.encode(prefix + "The owner is Mira.").ids),
                   "model_manifest": manifest}
    result = await evaluate(fixture, provider, embedding_override=embedding, verify_reopen=True)
    return {"provider": provider, "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
            "elapsed_seconds": time.perf_counter() - started, "memory": memory(),
            "network_attempts": len(attempts), "blocked_connections": attempts,
            "details": details, "retrieval": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--download-model", action="store_true", help="Explicitly allow a candidate download")
    parser.add_argument("--pip-cache", type=Path, help="Optional installer HTTP cache for archive sizes")
    parser.add_argument("--output", type=Path, default=Path("evals/results/fastembed-screen.json"))
    parser.add_argument("--worker", choices=["fallback", "fastembed"], help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.cache = args.cache.resolve()
    args.cache.mkdir(parents=True, exist_ok=True)
    if args.worker:
        print(json.dumps(asyncio.run(worker(args.worker, args.cache))))
        return
    if args.download_model:
        prepare(args.cache)
    if not (args.cache / "model-manifest.json").is_file():
        parser.error("No cached manifest. Use --download-model after approving the download.")
    env = dict(os.environ, HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
               TOKENIZERS_PARALLELISM="false", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
               GRAPHRAG_EMBEDDING_CONCURRENCY="1", GRAPHRAG_EMBEDDING_PROVIDER="fallback")
    results = []
    # The second candidate run starts a fresh interpreter using only cached files.
    for provider in ["fallback", "fastembed", "fastembed"]:
        child = subprocess.run([sys.executable, "-m", "scripts.evaluate_fastembed", "--cache",
                                str(args.cache), "--worker", provider], env=env, capture_output=True,
                               text=True, timeout=180, cwd=ROOT)
        if child.returncode:
            parser.exit(1, child.stderr)
        results.append(json.loads(child.stdout))
    same = results[1]["retrieval"]["queries"]
    repeat = results[2]["retrieval"]["queries"]
    stable = [r["retrieved"] for r in same] == [r["retrieved"] for r in repeat]
    if not stable:
        parser.exit(1, "Fresh-process candidate retrieval changed")
    report = {"platform": platform.platform(), "python": platform.python_version(),
              "dependency_footprint": dependency_footprint(args.pip_cache),
              "fresh_process_retrieval_stable": stable,
              "limitations": "Six synthetic direct-chunk cases; no graph edges, answers, representative corpus, load test, or default-model approval. Offline settings and socket guards block Python network connections; this is not an OS network sandbox. Peak RSS is per child. First load uses an already downloaded cache; repeated load may benefit from OS page cache.",
              "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
