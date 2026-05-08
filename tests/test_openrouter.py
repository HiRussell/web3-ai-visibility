"""Tests for OpenRouterProvider — uses httpx.MockTransport, no network."""
from __future__ import annotations

import json

import httpx
import pytest

from web3seo.providers.openrouter import (
    DEFAULT_MODELS,
    OpenRouterModelConfig,
    OpenRouterProvider,
)


SAMPLE_PERPLEXITY_RESPONSE = {
    "id": "abc",
    "model": "perplexity/sonar-pro",
    "choices": [
        {
            "index": 0,
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": "Uniswap remains the leading DEX on Ethereum.",
                "annotations": [
                    {
                        "type": "url_citation",
                        "url_citation": {
                            "url": "https://defillama.com/protocol/uniswap",
                            "title": "Uniswap on DefiLlama",
                            "content": "Uniswap is a decentralized exchange...",
                            "start_index": 0,
                            "end_index": 30,
                        },
                    },
                    {
                        "type": "url_citation",
                        "url_citation": {
                            "url": "https://uniswap.org",
                            "title": "Uniswap home",
                            "content": "Swap any token...",
                            "start_index": 30,
                            "end_index": 50,
                        },
                    },
                ],
            },
        }
    ],
    "usage": {"prompt_tokens": 12, "completion_tokens": 88, "total_tokens": 100},
}


SAMPLE_GPT4O_ONLINE_RESPONSE = {
    "id": "xyz",
    "model": "openai/gpt-4o:online",
    "choices": [
        {
            "index": 0,
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": "Aave is a leading lending protocol with $X TVL.",
                "annotations": [
                    {
                        "type": "url_citation",
                        "url_citation": {
                            "url": "https://aave.com",
                            "title": "Aave",
                            "content": "Aave is...",
                            "start_index": 0,
                            "end_index": 4,
                        },
                    },
                ],
            },
        }
    ],
    "usage": {"prompt_tokens": 30, "completion_tokens": 60, "total_tokens": 90},
}


PERPLEXITY_CFG = OpenRouterModelConfig(
    model="perplexity/sonar-pro",
    display_name="Perplexity Sonar Pro",
    has_native_search=True,
    input_usd_per_m=3.0,
    output_usd_per_m=15.0,
)

GPT4O_CFG = OpenRouterModelConfig(
    model="openai/gpt-4o",
    display_name="ChatGPT (GPT-4o)",
    has_native_search=False,
    input_usd_per_m=2.5,
    output_usd_per_m=10.0,
)


def _mock_transport(payload: dict, status_code: int = 200, expected_model: str | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer testkey"
        body = json.loads(request.content)
        assert body["messages"][0]["role"] == "user"
        if expected_model is not None:
            assert body["model"] == expected_model, f"got {body['model']!r} not {expected_model!r}"
        return httpx.Response(status_code, json=payload)
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_perplexity_via_openrouter_no_online_suffix():
    """Models with native search use the bare slug, no `:online` suffix."""
    transport = _mock_transport(
        SAMPLE_PERPLEXITY_RESPONSE, expected_model="perplexity/sonar-pro"
    )
    p = OpenRouterProvider(PERPLEXITY_CFG, api_key="testkey", transport=transport)
    resp = await p.query("What's the best DEX on Ethereum?")

    assert resp.provider == "perplexity/sonar-pro"
    assert resp.model == "perplexity/sonar-pro"
    assert "Uniswap" in resp.response_text
    assert resp.input_tokens == 12
    assert resp.output_tokens == 88
    expected_cost = (12 / 1e6) * 3.0 + (88 / 1e6) * 15.0
    assert resp.cost_usd == pytest.approx(expected_cost)
    # Annotations parsed
    assert len(resp.citations) == 2
    assert resp.citations[0].url == "https://defillama.com/protocol/uniswap"
    assert resp.citations[0].title == "Uniswap on DefiLlama"
    assert resp.citations[0].snippet == "Uniswap is a decentralized exchange..."


@pytest.mark.asyncio
async def test_gpt4o_via_openrouter_appends_online_suffix():
    """Models without native search auto-append `:online` to enable web search."""
    transport = _mock_transport(
        SAMPLE_GPT4O_ONLINE_RESPONSE, expected_model="openai/gpt-4o:online"
    )
    p = OpenRouterProvider(GPT4O_CFG, api_key="testkey", transport=transport)
    resp = await p.query("Best lending on Ethereum?")

    assert resp.provider == "openai/gpt-4o"  # name = bare slug, used for storage key
    assert resp.model == "openai/gpt-4o:online"  # actually-sent model
    assert "Aave" in resp.response_text
    assert len(resp.citations) == 1
    assert resp.citations[0].url == "https://aave.com"


@pytest.mark.asyncio
async def test_legacy_top_level_citations_fallback():
    """If a route returns the older flat `citations: [url, ...]` shape, parse that."""
    payload = {
        "id": "x",
        "model": "perplexity/sonar-pro",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "ok",
                    # no annotations field
                },
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        "citations": ["https://example.com/a", "https://example.com/b"],
    }
    transport = _mock_transport(payload)
    p = OpenRouterProvider(PERPLEXITY_CFG, api_key="testkey", transport=transport)
    resp = await p.query("test")

    assert [c.url for c in resp.citations] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert resp.citations[0].title is None  # legacy shape has no title


@pytest.mark.asyncio
async def test_http_error_propagates():
    transport = _mock_transport({"error": "rate limited"}, status_code=429)
    p = OpenRouterProvider(PERPLEXITY_CFG, api_key="testkey", transport=transport)
    with pytest.raises(httpx.HTTPStatusError):
        await p.query("test")


@pytest.mark.asyncio
async def test_empty_annotations_does_not_crash():
    payload = {
        **SAMPLE_PERPLEXITY_RESPONSE,
        "choices": [
            {
                **SAMPLE_PERPLEXITY_RESPONSE["choices"][0],
                "message": {
                    "role": "assistant",
                    "content": "ok",
                    "annotations": [],
                },
            }
        ],
    }
    transport = _mock_transport(payload)
    p = OpenRouterProvider(PERPLEXITY_CFG, api_key="testkey", transport=transport)
    resp = await p.query("test")
    assert resp.citations == []


def test_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        OpenRouterProvider(PERPLEXITY_CFG)


def test_cost_estimate_matches_pricing():
    p = OpenRouterProvider(PERPLEXITY_CFG, api_key="x")
    cost = p.cost_estimate(n_queries=50, avg_input_tokens=200, avg_output_tokens=500)
    expected = (50 * 200 / 1e6) * 3.0 + (50 * 500 / 1e6) * 15.0
    assert cost == pytest.approx(expected)


def test_default_models_catalog_sane():
    """Sanity check: DEFAULT_MODELS covers each of the 4 vendors with sane pricing.

    Slug-version-agnostic — vendors flip consumer defaults often (gpt-4o → gpt-5.5,
    gemini-2.0-flash → gemini-3-flash, etc). Test the vendor coverage, not exact slugs.
    """
    slugs = {m.model for m in DEFAULT_MODELS}
    assert any(s.startswith("perplexity/") for s in slugs)
    assert any(s.startswith("openai/") for s in slugs)
    assert any(s.startswith("x-ai/grok") for s in slugs)
    assert any(s.startswith("google/gemini") for s in slugs)
    for m in DEFAULT_MODELS:
        assert m.input_usd_per_m > 0
        assert m.output_usd_per_m > 0
        assert m.display_name
