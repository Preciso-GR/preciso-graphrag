# Built-in English embedding recommendation

Date: 2026-10-16. Recommendation: Granite Small English R2 for the next optional
built-in integration. The production provider and default model are unchanged.

The [recorded comparison](measurements/fastembed-comparison-20261016.json) contains
versions, source revisions, artifact hashes, per-question results, timings,
memory, and limitations. The [setup plan](setup-integration-plan.md) still governs
integration. This screen selects a candidate, not a production-quality guarantee.

## Method

Use FastEmbed 0.9.0 on macOS arm64 with Python 3.13.5 and ONNX Runtime 1.31.0.
Keep one inference thread, one embedding request, batch size one, and no parallel
inference workers. Run the three candidates sequentially. Each candidate runs
twice in a fresh child process with a pinned local model, manifest verification,
Hugging Face offline mode, and a Python Internet-connection guard.

Use the same retrieval configuration for every candidate: mix mode, top two
evidence chunks, and cosine threshold 0.6. Do not tune the threshold after seeing
results. Preserve normal character-based chunk splitting for ordinary fixtures.

Three checks cover different questions:

1. The existing frozen synthetic fixture has five answerable questions and one
   unsupported question.
2. A new frozen fixture contains eight excerpts from existing backup and document
   lifecycle guides, eight author-curated answerable questions, and one unsupported
   question. Each excerpt is below the default character splitting limit. Source
   hashes and exact evidence IDs are recorded in the fixture. This is not held out.
3. A deliberate boundary diagnostic has three passages with a shared repetitive
   prefix and different tail facts. Inputs contain about 607 model tokens before
   provider prefixes. Disable character splitting only for this diagnostic so
   the full text actually reaches the model. It is not a realistic document corpus.

Apply Nomic's published search_document/search_query prefixes and normalize its
full-dimension output after pooling. Use FastEmbed's built-in pooling for the
other two candidates. PRECISO's vector store performs cosine normalization.
Use a separate graph for every fixture and provider. Reopen the ordinary fixture
stores and check repeatability. No existing user collections are read or changed.

## Measured comparison

| Measurement | BGE Small v1.5 | Nomic v1.5 Quantized | Granite Small English R2 |
|---|---:|---:|---:|
| Selected model/configuration files | 64.3 MiB | 131.9 MiB | 188.1 MiB |
| Effective tokenizer limit | 512 | 8,192 | 8,192 |
| Vector dimensions | 384 | 768 | 384 |
| Synthetic complete evidence | 5/5 | 5/5 | 5/5 |
| Repository-document complete evidence | 6/8 | 7/8 | 7/8 |
| Full long-tail complete evidence at threshold 0.6 | 0/3 | 1/3 | 3/3 |
| Peak process RSS across two runs | 287.5–291.0 MiB | 419.7–430.8 MiB | 341.1–348.0 MiB |
| Warm single-query embedding median | 6.86 ms | 13.91–14.31 ms | 8.55–9.14 ms |
| Initialization from cache | 0.42–0.65 s | 0.42–0.54 s | 0.46–0.49 s |
| Unsupported questions returning evidence | 1/2 | 1/2 | 2/2 |

No retrieved chunk IDs were invalid. Query results matched between fresh-process
runs, and reopened ordinary stores returned the original evidence order.
Both larger-window models produced distinct vectors for the contrasting tail
facts; BGE produced identical vectors. A tokenizer-only probe with more than
9,000 tokens confirmed truncation to each model's configured limit. No full-8K
inference or maximum-window memory stress test was performed.

All three share the previously measured optional FastEmbed dependency cost:
about 33.3 MiB of extra wheel downloads and 125.7 MiB of installed package files
over the resolved core dependencies. The table's model files are additional.
These totals exclude the interpreter and unrecorded bytecode. RSS is cumulative
per child and includes imports, integrity checks, ingestion, and retrieval.
Initialization includes library imports and file verification. Two runs and five
warm timing samples per run are a small screen, not a performance benchmark.

## Why Granite is recommended

Granite combines an 8K tokenizer window with 384-dimensional vectors. In these
runs it matched Nomic's ordinary evidence coverage while using less peak process
memory and less time per warm query embedding. It also worked better with the
current threshold on the artificial full-passage diagnostic. The larger download
is the main measured installation trade-off.

However, Nomic ranked the correct passage first in all three raw long-tail rankings.
Its other two results were below the current threshold. The diagnostic does not
prove Granite has universally better ranking quality: cosine score scales differ
between models and need calibration on reviewed, separate evaluation data.
Granite's higher scores also admitted related evidence for both unsupported
questions. Choosing this model does not add an evidence-sufficiency guarantee.

Both Nomic and Granite missed the repository question about where extraction
versions and graph-editing rules are recorded. No question, threshold, or required
evidence was changed to hide that failure. Graph expansion was not evaluated.

Keep Nomic as an alternative if download size matters more. BGE remains the
smallest measured candidate but provides less input headroom. Do not expose a
large model menu in first-run setup; recommend one evaluated option and preserve
explicit Ollama/API choices.

## Packaging issue found during the evaluation

Granite's ONNX graph uses `onnx/model.onnx_data` as a separate external weights
file. The initial generic downloader omitted it. ONNX Runtime also rejected the
symlinked Hub layout under its external-data path validation. The corrected
evaluation profile downloads the graph and required weights into one real local
directory. It preserves the runtime's security checks. Both files and all tokenizer
files are hashed. The final measured model set is 197,189,803 bytes; the registry's
180 MB estimate understated the actual selected artifacts.

The evaluator now explicitly lists required artifacts and rejects missing files
before download. It does not disable external-data path validation or execute
model-provided Python code.

## Remaining work before setup integration

1. Add this as an optional provider behind the existing EmbeddingFunc interface.
   Do not change existing collections or production defaults in an evaluation PR.
2. Enforce actual model-token limits, including prefixes and special tokens, before
   mutations. Entity descriptions, relations, and queries also require checks.
3. Offload synchronous CPU inference from the MCP event loop. Bound threads and
   concurrent requests. Keep normal chunks focused rather than filling 8K windows.
4. Preserve artifact, revision, dimension, and preprocessing identity on disk.
   Cache all required files, including external weights. Check licenses/notices
   before distributing artifacts; prefer downloading them after user consent.
5. Cache the separate context tokenizer or explicitly select its offline fallback.
   During this screen, each fixture attempted a blocked tiktoken file download and
   then used PRECISO's whitespace context tokenizer. All candidates used the same
   fallback. This is separate from each model's own tokenizer.
6. Calibrate thresholds and no-answer handling using representative English
   documents and a held-out question set. The current fixtures are insufficient
   to establish finance/news quality or production recall.
7. Verify the installed package and Codex setup on clean macOS environments before
   publishing a default. No hosted CI or container check was run for this screen.

## Reproduce

Use the existing optional evaluation environment with FastEmbed 0.9.0 installed.
Do not install it into production merely to reproduce this result.

```sh
# Run one candidate at a time. The flag explicitly permits a model download.
HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_XET=1 \
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
python -m scripts.evaluate_fastembed --candidate granite \
  --cache /tmp/preciso-granite-screen --download-model

# Cached runs omit --download-model. Other candidate IDs: bge, nomic.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -m scripts.evaluate_fastembed --candidate granite \
  --cache /tmp/preciso-granite-screen
```

## Sources

- [Granite model guidance](https://huggingface.co/ibm-granite/granite-embedding-small-english-r2)
- [Pinned Granite ONNX conversion](https://huggingface.co/onnx-community/granite-embedding-small-english-r2-ONNX/tree/1dc7835ba0cb9c76a3618d0bf0c427c97671b3c8)
- [Pinned Nomic source](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5/tree/e9b6763023c676ca8431644204f50c2b100d9aab)
- [FastEmbed registry](https://github.com/qdrant/fastembed/tree/main/fastembed/text)
