"""Tiny shared helper for ``ILIKE``-based search endpoints."""

from __future__ import annotations


def escape_like(term: str) -> str:
    """Neutralise the caller's ``%`` / ``_`` so a search stays a literal search."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
