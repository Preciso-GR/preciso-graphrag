"""Compatibility imports for the original MCP summary helpers.

Summary policy and persistence coordination belong to core.summary_maintenance.
MCP tool registration remains in preciso_mcp.server.
"""
from core.summary_maintenance import list_pending_summaries, submit_summary

__all__ = ["list_pending_summaries", "submit_summary"]
