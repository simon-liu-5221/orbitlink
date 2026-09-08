"""HMAC pseudonymisation of author / comment identifiers (docs/data-ethics.md).

Raw YouTube channel ids never reach the database. Each deployment has its own
``PSEUDONYM_KEY`` so pseudonyms are not comparable across environments.
"""

from __future__ import annotations

import hashlib
import hmac

#: Hex characters kept from the digest — 16 = 64 bits, ample for one analysis.
PSEUDONYM_LENGTH = 16


def pseudonymize(identifier: str, *, key: bytes) -> str:
    """Stable, non-reversible 16-hex-char token for ``identifier`` under ``key``."""
    if not key:
        raise ValueError("pseudonym key must not be empty")
    digest = hmac.new(key, identifier.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:PSEUDONYM_LENGTH]
