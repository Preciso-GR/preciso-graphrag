# Retrieval pilot

Run date: 2026-10-07. Scope: direct chunk retrieval in mix mode.

The fixture contains six synthetic chunks and six manually authored questions.
Five questions have required evidence. One question has no supporting evidence.
The fixture has no graph nodes or edges. It does not test graph expansion,
answer generation, contradictory sources, or a held-out corpus.

## Reproduce

1. Check the offline baseline.

   ```sh
   .venv/bin/python -m scripts.evaluate_retrieval_pilot --offline-only
   ```

2. Run the local model comparison.

   ```sh
   OLLAMA_BASE_URL=http://127.0.0.1:11434 \
     .venv/bin/python -m scripts.evaluate_retrieval_pilot
   ```

The script uses `mxbai-embed-large` and application concurrency one. It creates
separate temporary graphs for each provider. No API key or answer model is needed.
The real-model run makes one startup probe, one six-text ingestion request, and
six query requests. The report is stored in `evals/results/core-retrieval-pilot.json`.
Generated reports are ignored by Git.

## Recorded result

Fixture SHA-256:
`4df12b1ed7143d985d807a92c2d785d757a79afe6aacc67ed1fea7f8d3ce9f83`.

Retrieval was capped at two chunks. Query mode and corpus were identical for both
providers. Mean recall averages required-evidence coverage across answerable cases.
Complete coverage requires every expected chunk for a case.

| Measurement | Lexical fallback | Local mxbai-embed-large |
|---|---:|---:|
| Mean evidence recall | 0.70 | 1.00 |
| Complete evidence cases | 3 of 5 | 5 of 5 |
| Invalid retrieved chunk IDs | 0 | 0 |
| Unsupported question returned evidence | Yes | Yes |
| Median query duration | 0.35 ms | 55 ms |
| Embedding dimension | 8 | 1,024 |

These durations come from six sequential queries in one run. They exclude startup
and ingestion. They are not a latency benchmark. No peak memory measurement was made.
The Ollama model revision was not pinned. Save the model digest before using this
fixture as a release gate.

## Interpretation

The semantic model recovered the required access and combined-question evidence
that the fallback missed. This comparison supports using real embeddings for the
next evaluation. It does not establish a general quality improvement or validate
all graph retrieval paths.

Both providers returned evidence for a question about an absent license price.
The returned archive facts did not contain that price. Related evidence is not
proof that the requested fact exists. This test does not generate an answer and
cannot measure hallucination or answer abstention.

Keep the current retrieval settings until a larger reviewed corpus supports a
change. Next, add graph relationships, cross-document evidence, contradictions,
and independently reviewed unsupported questions. Evaluate evidence support and
answer abstention separately. Do not select a similarity threshold from one
unsupported question.
