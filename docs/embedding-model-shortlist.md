# English local embedding shortlist

Research date: 2026-10-16. Checked current upstream source and the installed
FastEmbed 0.9.0 registry. No additional model weights were downloaded or tested.

Update: the subsequent [measured comparison](embedding-model-selection.md) tested
Nomic and Granite and recommends Granite for the next optional integration. The
table below preserves the earlier registry estimates; use the comparison for
actual selected download sizes and runtime measurements.

## Candidates

| FastEmbed model ID | Registry size estimate | Listed input limit | Dimensions |
|---|---:|---:|---:|
| BAAI/bge-small-en-v1.5 | 67 MB | 512 tokens | 384 |
| nomic-ai/nomic-embed-text-v1.5-Q | 130 MB | 8,192 tokens | 768 |
| jinaai/jina-embeddings-v2-small-en | 120 MB | 8,192 tokens | 512 |
| ibm-granite/granite-embedding-small-english-r2 | 180 MB | 8,192 tokens | 384 |

Sizes are approximate registry values in decimal units, not measured total
downloads. Actual artifact manifests can include tokenizer and configuration files.
Python dependencies, caches, vector indexes, and process memory are additional.
Only BGE has been measured in PRECISO; see [initial screen](fastembed-evaluation.md).

The registry labels the three longer-input candidates Apache 2.0. Inspect the
specific downloaded artifacts and notices before redistribution. Jina v2's license
must not be confused with the different license of Jina v3.

## Recommendation

Evaluate quantized Nomic first as the next bounded candidate. It combines a small
listed artifact size and a longer supported input window. Apply its required
query/document task prefixes, verify normalization and effective tokenizer limits,
and compare evidence retrieval and memory using the same frozen questions.
Quantization reduces weight precision and file size; its retrieval trade-offs
need measurement.

Granite Small R2 is a second candidate. It retains 384-dimensional vectors and
supports longer inputs. Verify FastEmbed preprocessing and normalization against
the model's published instructions before testing it. Do not infer retrieval
quality, CPU speed, or RAM consumption from file size or context length.

Long context is an allowance, not a target chunk length. Continue using focused
evidence chunks. Include tail facts and overlength rejection in tests. An 8,192-token
window can be more expensive to use than a short passage, and all models still
need explicit length protection.

The existing Ollama Nomic files are a different artifact format from the ONNX
variant. Reusing the model family does not let FastEmbed reuse Ollama's weight
files or existing vectors. Preserve provider, artifact, revision, dimension, and
preprocessing identity for every collection. Do not switch populated indexes.

## Sources

- [FastEmbed Nomic registry](https://github.com/qdrant/fastembed/blob/main/fastembed/text/pooled_embedding.py)
- [FastEmbed Jina registry](https://github.com/qdrant/fastembed/blob/main/fastembed/text/pooled_normalized_embedding.py)
- [FastEmbed Granite registry](https://github.com/qdrant/fastembed/blob/main/fastembed/text/builtin_sentence_embedding.py)
- [Nomic instructions](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)
- [IBM Granite model card](https://huggingface.co/ibm-granite/granite-embedding-small-english-r2)
- [Jina Small model card](https://huggingface.co/jinaai/jina-embeddings-v2-small-en)
