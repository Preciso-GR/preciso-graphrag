from __future__ import annotations

import json
import re
from json import JSONDecodeError


def parse_markdown_extraction(content: str) -> dict:
    """
    Parses agent extraction output if saved as .md or .txt
    instead of .json.

    Agent may write output like:

    ```json
    {
      "document_id": "...",
      "entities": [...],
      ...
    }
    ```

    Extract the JSON block from markdown fences and parse it.
    Also handle raw JSON with no markdown fences.

    Returns: dict matching ingest_graph payload schema
    Raises: ValueError if no valid JSON found
    """

    if not isinstance(content, str):
        raise ValueError("content must be a string")

    stripped = content.strip()
    if not stripped:
        raise ValueError("no valid JSON found")

    candidates = _extract_json_candidates(stripped)
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("no valid JSON found")


def _extract_json_candidates(content: str) -> list[str]:
    candidates = [content]
    fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", content, flags=re.DOTALL | re.IGNORECASE)
    candidates.extend(block.strip() for block in fenced_blocks if block.strip())
    return candidates
