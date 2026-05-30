This folder stores generated test-case JSON files used for evaluations.

Guidance:

- Generated test cases (e.g. `test_cases_YYYYMMDDTHHMMSS_XXXX.json`) are intended to be created by the evaluation harness and are gitignored by default.
- If you want to add or edit example test cases for distribution, place them under `evals/` (root) or add a separate sample file — do not add large generated suites to this folder if they are auto-produced.
- Keep the `.gitkeep` file in this directory so the folder is retained in the repo.

Files:

- `.gitkeep` — keep the empty folder in git.
