# Built-in English embeddings: initial screen

Date: 2026-10-16. Decision: retain as a candidate. Do not change the default yet.

The [setup integration plan](setup-integration-plan.md) defines the approved scope.
The [recorded measurements](measurements/fastembed-screen-20261016.json) include
dependency versions, model artifact hashes, per-question results, and limitations.

## Question and method

Can PRECISO run useful English embeddings without installing an Ollama service,
while keeping the optional dependency and resource costs reasonable?

Test FastEmbed 0.9.0 with BAAI/bge-small-en-v1.5. Use its quantized ONNX conversion
from `Qdrant/bge-small-en-v1.5-onnx-Q`, revision
`aa8f8b060edb00e03bfdd08813a2949946c8ba55`. The model repository declares MIT;
FastEmbed declares Apache 2.0. These are separate licenses. This test downloads
artifacts; it does not redistribute weights in the PRECISO package.

Use the existing frozen six-passage retrieval fixture. Five questions have required
evidence; one has no answer in the corpus. Compare lexical fallback and the candidate
in the same resolved environment with identical retrieval settings. Use one CPU
inference thread, one embedding request, batch size eight, and no parallel workers.
Each run creates and removes its own graph directory. Reopen the stores and repeat
a query. Run the candidate in a second fresh process to check cached startup and
retrieval repeatability. No user graph or source document is used.

The host is Apple Silicon, macOS 26.5.1, Python 3.13.5, ONNX Runtime 1.31.0.
This is a temporary evaluation installation, not a dependency-lock update. Package
resolution used the project's declared ranges; installed versions are recorded.

## Observed results

| Measurement | Observed result |
|---|---|
| Candidate model files | 67,411,571 bytes, about 64.3 MiB |
| Extra dependency wheel downloads over resolved core dependencies | 34,912,021 bytes, about 33.3 MiB |
| Extra installed package files over resolved core dependencies | 131,761,614 bytes, about 125.7 MiB |
| Candidate vector dimensions | 384 |
| Lexical fallback complete evidence | 3 of 5 answerable cases; mean recall 0.70 |
| Candidate complete evidence | 5 of 5 answerable cases in both fresh processes; mean recall 1.00 |
| Invalid retrieved chunk IDs | None |
| Candidate initialization from cache | 0.65–0.77 seconds, including imports and integrity verification |
| Warm single-query embedding median | 6.93 and 7.09 ms; five samples per process after one warm-up |
| Candidate peak process RSS | 275.47 and 290.86 MiB |
| Fallback peak process RSS | 61.03 MiB |
| Reopened-store query | Matched original evidence order |
| Fresh-process candidate query results | Matched across all six questions |
| Unsupported question | Both providers still returned related evidence |

Peak memory is cumulative within each measured child. It includes library imports,
model loading, integrity checks, and a small ingestion/query run. It is not idle
memory or a production memory limit. Current RSS fluctuated between processes.
File sizes omit interpreter, pip, unrecorded bytecode, and the source checkout.
Repeated initialization can benefit from the operating system's file cache.

The historical mxbai Ollama pilot also retrieved complete evidence for five of five
answerable questions. It was not rerun: this screen does not establish equal quality
or a speed improvement over Ollama. The lexical fallback is a diagnostic baseline,
not an adequate semantic-model quality benchmark.

## Offline behavior

Model downloads happen only with `--download-model`. The downloader pins a source
revision and writes an artifact manifest. Cached runs verify those hashes and use
the specific local model path with Hugging Face offline mode. A Python socket guard
blocks IPv4/IPv6 connections while permitting local Unix sockets.

All evaluated retrieval runs completed under that guard. Each run attempted one
blocked connection from tiktoken's `read_file_cached` path, then used PRECISO's
whitespace context-tokenizer fallback. This is separate from the embedding model's
own tokenizer. Both comparison providers used the same context-tokenizer fallback.
Setup must cache the context tokenizer or explicitly choose its offline fallback;
do not describe this observation as zero attempted network activity.

FastEmbed inference required no Qdrant account, running database, or service.
The Python guard is not an operating-system network sandbox and does not prove
all native-library network behavior. Hugging Face telemetry was disabled, and the
worker disables ONNX Runtime telemetry through its exposed API.

## Input-length blocker

The candidate supports 512 model tokens. The screen embedded two passages with
the same long prefix and different final owner names. Each full input contains
607 model tokens. FastEmbed returned exactly identical vectors without rejecting
the inputs. The distinct tail facts were beyond the truncation boundary.

PRECISO's current general embedding limit is larger. Setting an EmbeddingFunc
metadata limit alone does not enforce this model's tokenizer boundary. A default
integration must count tokens using the selected model's tokenizer and reject
overlength inputs before mutation, or implement and verify an explicit splitting
policy. Query prefixes and special tokens also consume the token budget. Entity
and relationship descriptions need the same protection as document chunks.

The evaluation deliberately exposes this behavior. It does not truncate source
evidence or average sub-vectors to make the test pass. A future extraction workflow
must communicate the selected provider's actual input limits to the agent.

## Recommendation

Keep FastEmbed as an optional local-provider candidate. The screen shows useful
short-passage retrieval without an Ollama service, with a measured package and
memory cost. It does not yet justify selecting the model as the default.

Before integration, review the input-length policy and test longer English
documents. Before claiming default quality, freeze representative questions and
evidence with explicit acceptance thresholds. This synthetic screen has no graph
edges, generated answers, finance/news coverage, concurrent load, or held-out set.
Related evidence for an unsupported question remains a retrieval limitation.

## Reproduce

Use a disposable environment with the project installed and `fastembed==0.9.0`.
The model is not a production dependency. macOS process-RSS collection requires
permission to execute `ps`.

```sh
# Explicit download step: inspect the proposed model and approve it first.
HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_XET=1 \
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
python -m scripts.evaluate_fastembed \
  --cache /tmp/preciso-model-screen --download-model

# Cached evaluation: no model download flag.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -m scripts.evaluate_fastembed --cache /tmp/preciso-model-screen
```

The script prints selected artifact bytes before downloading. It is an explicit
developer evaluation command, not the proposed interactive setup assistant. The
`--pip-cache` option reads cached wheel sizes when the installation used a known
pip cache directory. Default report output under `evals/results/` is ignored.

## Sources

- [FastEmbed source and license](https://github.com/qdrant/fastembed)
- [Candidate ONNX artifacts](https://huggingface.co/Qdrant/bge-small-en-v1.5-onnx-Q/tree/aa8f8b060edb00e03bfdd08813a2949946c8ba55)
- [Original BAAI model card](https://huggingface.co/BAAI/bge-small-en-v1.5)
