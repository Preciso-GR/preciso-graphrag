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

PROFILES = {
    "bge": {"model": "BAAI/bge-small-en-v1.5", "repository": "Qdrant/bge-small-en-v1.5-onnx-Q",
            "file": "model_optimized.onnx", "dimension": 384, "limit": 512},
    "nomic": {"model": "nomic-ai/nomic-embed-text-v1.5-Q", "repository": "nomic-ai/nomic-embed-text-v1.5",
              "file": "onnx/model_quantized.onnx", "dimension": 768, "limit": 8192},
    "granite": {"model": "ibm-granite/granite-embedding-small-english-r2",
                "repository": "onnx-community/granite-embedding-small-english-r2-ONNX",
                "file": "onnx/model.onnx", "additional_files": ["onnx/model.onnx_data"],
                "dimension": 384, "limit": 8192},
}
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
        if p.is_file() and ".cache" not in p.relative_to(directory).parts:
            with p.open("rb") as f:
                digest = hashlib.file_digest(f, "sha256").hexdigest()
            files.append({"name": str(p.relative_to(directory)), "bytes": p.stat().st_size,
                          "sha256": digest})
    return files


def prepare(cache, profile):
    from huggingface_hub import HfApi, snapshot_download

    files = [profile["file"], "config.json", "tokenizer.json", "tokenizer_config.json",
             "special_tokens_map.json", "vocab.txt", "README.md", "LICENSE"]
    files.extend(profile.get("additional_files", []))
    info = HfApi().model_info(profile["repository"], files_metadata=True)
    required = {profile["file"], *profile.get("additional_files", []),
                "tokenizer.json", "tokenizer_config.json"}
    missing = required - {f.rfilename for f in info.siblings}
    if missing:
        raise RuntimeError(f"Model repository is missing required files: {sorted(missing)}")
    selected = [f for f in info.siblings if f.rfilename in files]
    print(json.dumps({"model": profile["model"], "repository": profile["repository"], "revision": info.sha,
                      "selected_artifact_bytes": sum(f.size or 0 for f in selected)}), flush=True)
    started = time.perf_counter()
    # External ONNX data must reside beside the graph in a real directory.
    # A symlinked Hub snapshot can fail the runtime's external-data path checks.
    location = ({"local_dir": str(cache / "artifacts" / info.sha)} if profile.get("additional_files")
                else {"cache_dir": str(cache / "hub")})
    path = snapshot_download(profile["repository"], revision=info.sha,
                             allow_patterns=files, max_workers=1, **location)
    manifest = {"model": profile["model"], "repository": profile["repository"], "revision": info.sha,
                "path": path, "download_seconds": time.perf_counter() - started,
                "files": file_manifest(Path(path))}
    (cache / "model-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


async def worker(provider, cache, profile):
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
        if manifest["model"] != profile["model"]:
            raise RuntimeError("Cache belongs to a different model profile")
        path = Path(manifest["path"])
        if file_manifest(path) != manifest["files"]:
            raise RuntimeError("Cached model files do not match the reviewed manifest")
        model = TextEmbedding(profile["model"], threads=1, providers=["CPUExecutionProvider"],
                              specific_model_path=str(path), local_files_only=True)
        load_seconds = time.perf_counter() - started

        async def embed(texts, **kwargs):
            is_query = kwargs.get("context") == "query"
            if profile["model"].startswith("nomic-ai/"):
                prefix = "search_query: " if is_query else "search_document: "
                inputs = [prefix + text for text in texts]
                vectors = np.asarray(list(model.embed(inputs, batch_size=1, parallel=None)))
                # Nomic's published full-dimension usage normalizes after pooling.
                vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
            else:
                method = model.query_embed if is_query else model.passage_embed
                vectors = np.asarray(list(method(texts, batch_size=1, parallel=None)))
            if vectors.shape != (len(texts), profile["dimension"]) or not np.isfinite(vectors).all():
                raise RuntimeError("Invalid embedding shape or values")
            if not (np.linalg.norm(vectors, axis=1) > 0).all():
                raise RuntimeError("Zero embedding")
            return vectors

        # This synchronous wrapper is for a serial evaluation only. Production
        # integration must offload inference from the async event loop.
        embedding = EmbeddingFunc(profile["dimension"], profile["limit"], embed, provider="fastembed-evaluation",
                                  model_name=profile["model"], model_revision=manifest["revision"],
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
        # Check the tokenizer boundary without expensive full-window inference.
        boundary_text = prefix * 15 + "The final owner is Mira."
        boundary_input = ("search_document: " if profile["model"].startswith("nomic-ai/") else "") + boundary_text
        model_tokenizer = model.model.tokenizer
        details = {"fastembed_version": importlib.metadata.version("fastembed"),
                   "model": profile["model"], "source_revision": manifest["revision"],
                   "model_files_bytes": sum(f["bytes"] for f in manifest["files"]),
                   "model_initialization_seconds": load_seconds,
                   "warm_embedding_median_ms": statistics.median(timings[1:]),
                   "overlength_tail_vectors_identical": bool(np.array_equal(vectors[0], vectors[1])),
                   "overlength_text_characters": len(prefix), "threads": 1,
                   "overlength_untruncated_tokens": len(tokenizer.encode(prefix + "The owner is Mira.").ids),
                   "effective_tokenizer_truncation": model.model.tokenizer.truncation,
                   "tokenizer_boundary_probe": {
                       "untruncated_tokens": len(tokenizer.encode(boundary_input).ids),
                       "runtime_tokens": len(model_tokenizer.encode(boundary_input).ids),
                       "inference_performed": False},
                   "model_manifest": manifest}
        # Keep inference bounded: this is a 607-token boundary diagnostic, not
        # an 8K-token stress test. The identical prefix isolates the tail fact.
        long_fixture = {"document_id": "long-tail-screen", "chunks": [
            {"chunk_id": "mira", "content": prefix + "The archive owner is Mira."},
            {"chunk_id": "omar", "content": prefix + "The incident owner is Omar."},
            {"chunk_id": "weather", "content": prefix + "The weather sensor is WX-17."}],
            "questions": [
                {"id": "archive-owner", "query": "Who owns the archive?", "required": ["mira"]},
                {"id": "incident-owner", "query": "Who owns the incident service?", "required": ["omar"]},
                {"id": "weather-id", "query": "Which weather sensor is used?", "required": ["weather"]}]}
        # Production currently splits passages by characters. Disable that only
        # inside this diagnostic to test the model on the complete long input.
        previous_limit = os.environ.get("GRAPHRAG_CHUNK_CHAR_LIMIT")
        os.environ["GRAPHRAG_CHUNK_CHAR_LIMIT"] = "0"
        try:
            details["tail_retrieval"] = await evaluate(long_fixture, provider, embedding_override=embedding)
            details["tail_retrieval"]["character_splitting_disabled_for_diagnostic"] = True
        finally:
            if previous_limit is None:
                os.environ.pop("GRAPHRAG_CHUNK_CHAR_LIMIT", None)
            else:
                os.environ["GRAPHRAG_CHUNK_CHAR_LIMIT"] = previous_limit
        passages = await embed([c["content"] for c in long_fixture["chunks"]])
        questions = await embed([q["query"] for q in long_fixture["questions"]], context="query")
        cosine = questions @ passages.T / (np.linalg.norm(questions, axis=1)[:, None] * np.linalg.norm(passages, axis=1)[None, :])
        details["tail_raw_rankings"] = [
            {"question": question["id"], "ranked_chunks": [long_fixture["chunks"][i]["chunk_id"] for i in np.argsort(-scores)],
             "cosine_scores": sorted(scores.tolist(), reverse=True)}
            for question, scores in zip(long_fixture["questions"], cosine)]
        doc_path = ROOT / "evals/fixtures/repo_docs_embedding_screen.json"
        if doc_path.is_file():
            details["repository_document_retrieval"] = await evaluate(
                json.loads(doc_path.read_text()), provider, embedding_override=embedding, verify_reopen=True)
            details["repository_document_fixture_sha256"] = hashlib.sha256(doc_path.read_bytes()).hexdigest()
    result = await evaluate(fixture, provider, embedding_override=embedding, verify_reopen=True)
    return {"provider": provider, "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
            "elapsed_seconds": time.perf_counter() - started, "memory": memory(),
            "network_attempts": len(attempts), "blocked_connections": attempts,
            "details": details, "retrieval": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--candidate", choices=PROFILES, default="bge")
    parser.add_argument("--download-model", action="store_true", help="Explicitly allow a candidate download")
    parser.add_argument("--pip-cache", type=Path, help="Optional installer HTTP cache for archive sizes")
    parser.add_argument("--output", type=Path, default=Path("evals/results/fastembed-screen.json"))
    parser.add_argument("--worker", choices=["fallback", "fastembed"], help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.cache = args.cache.resolve()
    args.cache.mkdir(parents=True, exist_ok=True)
    if args.worker:
        print(json.dumps(asyncio.run(worker(args.worker, args.cache, PROFILES[args.candidate]))))
        return
    if args.download_model:
        prepare(args.cache, PROFILES[args.candidate])
    if not (args.cache / "model-manifest.json").is_file():
        parser.error("No cached manifest. Use --download-model after approving the download.")
    env = dict(os.environ, HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
               TOKENIZERS_PARALLELISM="false", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
               GRAPHRAG_EMBEDDING_CONCURRENCY="1", GRAPHRAG_EMBEDDING_PROVIDER="fallback")
    results = []
    # The second candidate run starts a fresh interpreter using only cached files.
    for provider in ["fallback", "fastembed", "fastembed"]:
        child = subprocess.run([sys.executable, "-m", "scripts.evaluate_fastembed", "--cache",
                                str(args.cache), "--candidate", args.candidate, "--worker", provider], env=env, capture_output=True,
                               text=True, timeout=180, cwd=ROOT)
        if child.returncode:
            parser.exit(1, child.stderr)
        results.append(json.loads(child.stdout))
    same = results[1]["retrieval"]["queries"]
    repeat = results[2]["retrieval"]["queries"]
    stable = [r["retrieved"] for r in same] == [r["retrieved"] for r in repeat]
    for key in ("tail_retrieval", "repository_document_retrieval"):
        first = results[1]["details"].get(key, {}).get("queries", [])
        second = results[2]["details"].get(key, {}).get("queries", [])
        stable = stable and [r["retrieved"] for r in first] == [r["retrieved"] for r in second]
    if not stable:
        parser.exit(1, "Fresh-process candidate retrieval changed")
    report = {"platform": platform.platform(), "python": platform.python_version(),
              "dependency_footprint": dependency_footprint(args.pip_cache),
              "fresh_process_retrieval_stable": stable,
              "limitations": "Six synthetic cases, three repetitive long-tail diagnostics, and nine author-curated repository-document questions. No graph edges, answers, held-out user corpus, load test, full-8K inference, or default-model approval. Offline settings and socket guards block Python network connections; this is not an OS network sandbox. Peak RSS is per child. First load uses an already downloaded cache; repeated load may benefit from OS page cache.",
              "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
