"""End-to-end pipeline test with mocked OpenRouter.

Proves: fetch persists raw responses → extract identifies protocol mentions
against canonical → aggregate writes a snapshot JSON the frontend can read.
Also verifies fetch idempotency.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import yaml

from web3seo.canonical import CanonicalIndex, Protocol
from web3seo.pipeline.aggregate import aggregate_phase
from web3seo.pipeline.extract import extract_phase
from web3seo.pipeline.fetch import fetch_phase
from web3seo.providers.openrouter import OpenRouterModelConfig, OpenRouterProvider


PERPLEXITY_CFG = OpenRouterModelConfig(
    model="perplexity/sonar-pro",
    display_name="Perplexity Sonar Pro",
    has_native_search=True,
    input_usd_per_m=3.0,
    output_usd_per_m=15.0,
)


def _fake_response(prompt: str) -> dict:
    """Stub response that mentions a few canonical protocols."""
    if "DEX" in prompt or "Ethereum" in prompt:
        text = (
            "Uniswap V3 remains the dominant DEX. "
            "Curve is preferred for stablecoin swaps. "
            "Aave handles most of the lending volume."
        )
    elif "staking" in prompt.lower() or "lst" in prompt.lower():
        text = (
            "Lido Finance is the leading liquid staking option, "
            "with Rocket Pool a distant second."
        )
    else:
        text = "No specific protocol comes to mind."
    return {
        "id": "fake",
        "model": "perplexity/sonar-pro",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": text,
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url_citation": {
                                "url": "https://defillama.com",
                                "title": "DefiLlama",
                                "content": "TVL aggregator",
                                "start_index": 0,
                                "end_index": 5,
                            },
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
    }


def _make_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        prompt = body["messages"][0]["content"]
        return httpx.Response(200, json=_fake_response(prompt))
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_full_pipeline_runs_end_to_end(tmp_path: Path):
    queries_yaml = tmp_path / "queries.yaml"
    queries_yaml.write_text(
        yaml.safe_dump(
            {
                "queries": [
                    {"id": "q1", "category": "rec", "text": "Best DEX on Ethereum?"},
                    {"id": "q2", "category": "rec", "text": "Best liquid staking option?"},
                    {"id": "q3", "category": "other", "text": "Anything else?"},
                ]
            }
        )
    )

    db_path = tmp_path / "test.db"
    snapshot_path = tmp_path / "snapshot.json"

    provider = OpenRouterProvider(
        PERPLEXITY_CFG, api_key="testkey", transport=_make_transport()
    )

    # ── Phase 1: fetch ──
    result = await fetch_phase(
        run_date="2026-05-07",
        queries_yaml=queries_yaml,
        providers=[provider],
        db_path=db_path,
    )
    assert result["saved"] == 3
    assert result["errors"] == 0
    assert result["skipped"] == 0

    # ── Idempotency: re-run skips ──
    result2 = await fetch_phase(
        run_date="2026-05-07",
        queries_yaml=queries_yaml,
        providers=[provider],
        db_path=db_path,
    )
    assert result2["skipped"] == 3
    assert result2["saved"] == 0

    # ── Phase 2: extract ──
    canonical = CanonicalIndex(
        [
            Protocol(id="uniswap-v3", name="Uniswap V3", aliases=[]),
            Protocol(id="curve-dex", name="Curve", aliases=[]),
            Protocol(id="aave", name="Aave", aliases=[]),
            Protocol(id="lido", name="Lido Finance", aliases=["lido"]),
            Protocol(id="rocket-pool", name="Rocket Pool", aliases=["rocketpool"]),
        ]
    )
    extract_result = extract_phase("2026-05-07", db_path, canonical)
    assert extract_result["responses_processed"] == 3
    # q1: uniswap-v3 + curve-dex + aave = 3; q2: lido + rocket-pool = 2; q3: 0; total = 5
    assert extract_result["mentions_extracted"] >= 5

    # Re-running extract is idempotent (delete-then-reinsert)
    extract_result2 = extract_phase("2026-05-07", db_path, canonical)
    assert extract_result2["mentions_extracted"] == extract_result["mentions_extracted"]

    # ── Phase 3: aggregate ──
    agg_result = aggregate_phase("2026-05-07", db_path, snapshot_path)
    assert snapshot_path.exists()
    assert agg_result["protocols_in_leaderboard"] >= 4

    snapshot = json.loads(snapshot_path.read_text())
    assert snapshot["run_date"] == "2026-05-07"

    protocol_ids = {item["protocol_id"] for item in snapshot["leaderboard"]}
    assert "uniswap-v3" in protocol_ids
    assert "curve-dex" in protocol_ids
    assert "aave" in protocol_ids
    assert "lido" in protocol_ids

    top_entry = snapshot["leaderboard"][0]
    assert "by_provider" in top_entry
    assert "sample_contexts" in top_entry
    assert len(top_entry["sample_contexts"]) >= 1

    # OpenRouter `annotations` schema flowed through into citation host tracking
    hosts = [h["host"] for h in snapshot["top_citation_hosts"]]
    assert "defillama.com" in hosts


@pytest.mark.asyncio
async def test_fetch_persists_errors_without_crashing(tmp_path: Path):
    queries_yaml = tmp_path / "queries.yaml"
    queries_yaml.write_text(
        yaml.safe_dump(
            {"queries": [{"id": "q1", "category": "rec", "text": "anything"}]}
        )
    )
    db_path = tmp_path / "test.db"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    provider = OpenRouterProvider(
        PERPLEXITY_CFG,
        api_key="testkey",
        transport=httpx.MockTransport(handler),
    )

    result = await fetch_phase(
        run_date="2026-05-07",
        queries_yaml=queries_yaml,
        providers=[provider],
        db_path=db_path,
    )
    assert result["errors"] == 1
    assert result["saved"] == 0

    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM errors").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["phase"] == "fetch"
    assert rows[0]["provider"] == "perplexity/sonar-pro"
