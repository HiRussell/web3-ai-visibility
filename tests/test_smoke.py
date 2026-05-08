"""Smoke tests: imports, storage round-trip, canonical resolution."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from web3seo.canonical import CanonicalIndex, Protocol
from web3seo.providers.base import Citation, LLMResponse
from web3seo.storage import connect, has_response, save_response


def test_module_imports():
    """All modules import cleanly with no missing dependencies."""
    from web3seo.pipeline import aggregate, extract, fetch  # noqa: F401
    from web3seo.providers import openrouter  # noqa: F401


def test_storage_roundtrip(tmp_path: Path):
    db_path = tmp_path / "test.db"
    resp = LLMResponse(
        provider="testprov",
        model="test-model",
        query="hello",
        response_text="world",
        citations=[Citation(url="https://example.com")],
        fetched_at=datetime.now(timezone.utc),
    )
    with connect(db_path) as conn:
        assert not has_response(conn, "2026-05-07", "q1", "testprov")
        save_response(conn, "2026-05-07", "q1", resp)
        assert has_response(conn, "2026-05-07", "q1", "testprov")


def test_canonical_basic_lookup():
    protocols = [
        Protocol(id="uniswap-v3", name="Uniswap V3", aliases=["uni v3"]),
        Protocol(id="aave", name="Aave", aliases=["aave protocol"]),
    ]
    idx = CanonicalIndex(protocols)

    text = "I'd recommend Uniswap V3 for swaps and Aave Protocol for lending."
    hits = idx.find(text)
    ids = [p.id for p, _, _ in hits]
    assert "uniswap-v3" in ids
    assert "aave" in ids


def test_canonical_word_boundary():
    """'uni' should not match inside 'unison'."""
    protocols = [Protocol(id="uniswap", name="Uniswap", aliases=["uniswap labs"])]
    idx = CanonicalIndex(protocols)
    hits = idx.find("There is unison among traders. But Uniswap is bigger.")
    assert len(hits) == 1
    assert hits[0][0].id == "uniswap"


def test_canonical_min_alias_len_filter():
    """Aliases shorter than MIN_ALIAS_LEN should not be registered (false positives)."""
    protocols = [Protocol(id="uniswap", name="Uniswap", aliases=["a", "b"])]  # garbage short aliases
    idx = CanonicalIndex(protocols)
    # "Uniswap" still matches via name; short aliases are ignored.
    hits = idx.find("a b Uniswap")
    assert len(hits) == 1


def test_canonical_longest_match_wins():
    """When 'Uniswap V3' could match either 'uniswap' or 'uniswap v3', the longer wins."""
    protocols = [
        Protocol(id="uniswap", name="Uniswap", aliases=[]),
        Protocol(id="uniswap-v3", name="Uniswap V3", aliases=[]),
    ]
    idx = CanonicalIndex(protocols)
    hits = idx.find("Try Uniswap V3 for swaps.")
    ids = [p.id for p, _, _ in hits]
    assert ids == ["uniswap-v3"]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Aave is great", ["aave"]),
        ("aave protocol works well", ["aave"]),
        ("AAVE PROTOCOL works", ["aave"]),  # case-insensitive
    ],
)
def test_canonical_case_insensitive(text, expected):
    protocols = [Protocol(id="aave", name="Aave", aliases=["aave protocol"])]
    idx = CanonicalIndex(protocols)
    hits = idx.find(text)
    assert [p.id for p, _, _ in hits] == expected
