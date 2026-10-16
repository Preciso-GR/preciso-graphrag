"""Compatibility import for callers of the original ingestion module.

The Contribution Ledger module owns ingestion validation and transactions.
Extraction writes remain private to that implementation.
"""
from core.documents import ingest_extracted_json

__all__ = ["ingest_extracted_json"]
