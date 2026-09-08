"""HMAC pseudonymisation (docs/data-ethics.md)."""

from __future__ import annotations

import pytest

from app.ingest.pseudonym import PSEUDONYM_LENGTH, pseudonymize

KEY = b"deployment-specific-secret"


def test_stable_for_the_same_input_and_key() -> None:
    assert pseudonymize("UCabc123", key=KEY) == pseudonymize("UCabc123", key=KEY)


def test_length_and_charset() -> None:
    token = pseudonymize("UCabc123", key=KEY)
    assert len(token) == PSEUDONYM_LENGTH
    assert all(c in "0123456789abcdef" for c in token)


def test_different_identifiers_differ() -> None:
    assert pseudonymize("UCaaa", key=KEY) != pseudonymize("UCbbb", key=KEY)


def test_different_keys_produce_different_pseudonyms() -> None:
    assert pseudonymize("UCabc", key=b"key-one") != pseudonymize("UCabc", key=b"key-two")


def test_empty_key_rejected() -> None:
    with pytest.raises(ValueError, match="key must not be empty"):
        pseudonymize("UCabc", key=b"")


def test_not_reversible_shape() -> None:
    # a pseudonym must not contain or trivially encode the source id
    token = pseudonymize("UCsecretChannelId", key=KEY)
    assert "secret" not in token
    assert "UC" not in token
