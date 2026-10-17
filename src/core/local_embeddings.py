"""Optional pinned Granite embeddings. No downloads during server startup."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path

MODEL = "ibm-granite/granite-embedding-small-english-r2"
REPOSITORY = "onnx-community/granite-embedding-small-english-r2-ONNX"
REVISION = "1dc7835ba0cb9c76a3618d0bf0c427c97671b3c8"
DIMENSION = 384
TOKEN_LIMIT = 8192
MODEL_BYTES = 197189803
FILES = {
    "README.md": "99162b472dbdbbda16424dadb484be941bcb7df1b0077808e961386e53485c55",
    "config.json": "1a1710c20911da8c96179716bf44058e54cca6fa7952cce77be83ef05edae3ee",
    "onnx/model.onnx": "cddb145cd1147ec24a3908b2ca2602b98b20a3d198365cff270b7cb26c98179e",
    "onnx/model.onnx_data": "86a3a705d4598615894d89540ea71a3d9bbdb17a315e79edcd5dfc737222834b",
    "special_tokens_map.json": "ea97ecdbcc73713039d8d64dbb05e3689495c96657fbd9a18f5bed381be81049",
    "tokenizer.json": "feeb83348dcb033bc6b9d2e1f7906ca9eb2d122845000c9416d894d7c2927149",
    "tokenizer_config.json": "ce06781b38bb393db68c9e0709bddd31ef5d88f2c6fbb3fd9f369778fb85e451",
}


def default_model_directory() -> Path:
    cache = Path(os.environ.get("PRECISO_CACHE_DIR", "~/Library/Caches/PRECISO")).expanduser()
    return cache / "models" / f"granite-{REVISION}"


def verify_model(directory: Path) -> None:
    for name, expected in FILES.items():
        path = directory / name
        if not path.is_file():
            raise ValueError("Local model is incomplete. Run PRECISO setup to download or repair it.")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError("Local model integrity check failed. Run PRECISO setup to repair it.")


def download_model(directory: Path) -> None:
    """Caller must obtain download consent. Hub downloads resume partial files."""
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    from huggingface_hub import hf_hub_download

    for name, expected in FILES.items():
        path = directory / name
        if path.is_file():
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() == expected:
                    continue
        hf_hub_download(REPOSITORY, filename=name, revision=REVISION, local_dir=str(directory),
                        force_download=path.exists())
    verify_model(directory)


async def thread_call(function, *args):
    """Drain uncancellable CPU work before releasing the caller's lock."""
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if task.done() and not task.cancelled():
            task.exception()
        raise


class GraniteEmbedding:
    """One CPU session; complete-input validation before any model inference."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.model = None
        self.tokenizer = None
        self.lock = asyncio.Lock()

    def _load(self):
        verify_model(self.directory)
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        try:
            if importlib.metadata.version("fastembed") != "0.9.0":
                raise RuntimeError("This model configuration requires fastembed==0.9.0")
            import onnxruntime
            from fastembed import TextEmbedding
            from tokenizers import Tokenizer
        except (ImportError, importlib.metadata.PackageNotFoundError):
            raise RuntimeError("Built-in embeddings require the 'local' extra. Run PRECISO setup.") from None
        onnxruntime.disable_telemetry_events()
        model = TextEmbedding(MODEL, threads=1, providers=["CPUExecutionProvider"],
                              specific_model_path=str(self.directory), local_files_only=True)
        tokenizer = Tokenizer.from_str(model.model.tokenizer.to_str())
        tokenizer.no_truncation()
        tokenizer.no_padding()
        if model.model.tokenizer.truncation["max_length"] != TOKEN_LIMIT:
            raise ValueError("Unexpected model tokenizer limit")
        self.tokenizer, self.model = tokenizer, model

    async def initialize(self):
        async with self.lock:
            if self.model is None:
                await thread_call(self._load)

    def _validate(self, texts):
        for index, text in enumerate(texts):
            count = len(self.tokenizer.encode(text).ids)
            if count > TOKEN_LIMIT:
                raise ValueError(f"Embedding input {index} has {count} model tokens; maximum is {TOKEN_LIMIT}. "
                                 "Split the passage or shorten the description/query. No text was truncated.")

    async def validate_inputs(self, texts):
        async with self.lock:
            if self.model is None:
                await thread_call(self._load)
            await thread_call(self._validate, texts)

    def _embed(self, texts):
        self._validate(texts)
        return list(self.model.embed(texts, batch_size=1, parallel=None))

    async def __call__(self, texts, **kwargs):
        if not isinstance(texts, list) or not all(isinstance(text, str) for text in texts):
            raise ValueError("Embedding input must be a list of strings")
        async with self.lock:
            if self.model is None:
                await thread_call(self._load)
            return await thread_call(self._embed, texts)


def build_embedding(directory: Path | None = None):
    from core.storage.base import EmbeddingFunc

    provider = GraniteEmbedding(directory or default_model_directory())
    identity = {"revision": REVISION, "files": FILES, "preprocessing": "granite-fastembed-0.9.0-v1"}
    revision = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return EmbeddingFunc(DIMENSION, TOKEN_LIMIT, provider, provider="fastembed", model_name=MODEL,
                         model_revision=revision, max_concurrent_requests=1)
