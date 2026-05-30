Evaluation workflow
-------------------

This folder contains evaluation assets and samples to help users validate the system quickly.

What to push

- `evals/WALMART_SAMPLE_QUESTIONS.json` — a small, curated set of 23 sample questions derived from the Walmart 2022/2023 extraction artifacts. This file is safe to commit and provides an immediate smoke-test for new users.
- `evals/SKILL.md` — the evaluation skill note (already in the repo).

What NOT to push

- `evals/results/*.jsonl` — runtime run outputs (evaluation results). These are ignored by default.
- `evals/test_cases/*.json` — generated test-case suites. These are ignored by default.

Quick start (run sample questions):

1. Ensure the MCP server is running (see repo `scripts/mcp_launcher.sh`).
2. Run the evaluation harness that accepts a questions file (or adapt `test/query_manual.py` to iterate the questions array).
