"""Unified OpenRouter provider — covers Perplexity / OpenAI / xAI / Gemini / Anthropic
through a single API key + standardized response schema.

Why OpenRouter (not 4 direct vendor APIs):
- One key, one bill, one schema. Direct application of Corvus's vendor-lock
  defense ("永远走 OpenAI-compatible 抽象层").
- OpenRouter standardizes citations into `message.annotations[].url_citation`
  with `{url, title, content, start_index, end_index}` — richer than Perplexity's
  native flat URL list.
- Models with native search (Perplexity Sonar) return citations naturally.
- Models without native search (gpt-4o, Grok, Gemini, Claude) get search via the
  `:online` suffix or the `openrouter:web_search` server tool — same response shape.

Pricing reference (verify on update): https://openrouter.ai/models
OpenRouter takes ~5% margin on most models. Web search plugin: ~$5 per 1000
results (configurable). Acceptable for ~50 queries/day.

Decisions log: D-010 in `.web3seo-dev/decisions.md`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from .base import Citation, LLMProvider, LLMResponse


@dataclass(frozen=True)
class OpenRouterModelConfig:
    """One row per model we want to track on the leaderboard."""
    model: str                # OpenRouter slug, e.g. "perplexity/sonar-pro"
    display_name: str         # for leaderboard UI, e.g. "Perplexity Sonar Pro"
    has_native_search: bool   # True = no need to add :online; native search returns citations
    input_usd_per_m: float    # USD per million input tokens (verify on price changes)
    output_usd_per_m: float   # USD per million output tokens


# OpenRouter web_search plugin pricing (verify: https://openrouter.ai/docs/guides/features/plugins/web-search)
# Charged when using :online suffix on models without native search.
SEARCH_FEE_PER_RESULT_USD = 0.005          # $5 per 1000 results
DEFAULT_SEARCH_RESULTS_PER_QUERY = 5       # OpenRouter default max_results
SEARCH_FEE_PER_QUERY_USD = SEARCH_FEE_PER_RESULT_USD * DEFAULT_SEARCH_RESULTS_PER_QUERY

# When :online injects search results into the prompt, those count as input tokens.
# Rough average: 5 results × ~500 tokens/result = 2500 extra input tokens per query.
# Verify by sampling real responses; update if measured differently.
ONLINE_EXTRA_INPUT_TOKENS = 2500


class OpenRouterProvider(LLMProvider):
    """Concrete LLMProvider parameterized by an OpenRouterModelConfig.

    `name` is set to the model slug so the storage layer naturally separates
    per-model results — the leaderboard shows e.g. `openai/gpt-4o` vs
    `perplexity/sonar-pro` directly.
    """
    BASE_URL = "https://openrouter.ai/api/v1"
    has_live_search = True

    def __init__(
        self,
        config: OpenRouterModelConfig,
        *,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        self.config = config
        self.name = config.model
        self.default_model = (
            config.model if config.has_native_search else f"{config.model}:online"
        )
        self._transport = transport
        self._timeout = timeout

    async def query(self, prompt: str, *, model: str | None = None) -> LLMResponse:
        use_model = model or self.default_model
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # OpenRouter analytics — non-essential, but recommended.
            "HTTP-Referer": "https://github.com/web3-ai-visibility",
            "X-Title": "Web3 AI Visibility Tracker",
        }
        body = {
            "model": use_model,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            r = await client.post(
                f"{self.BASE_URL}/chat/completions",
                json=body,
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()

        return self._parse_response(prompt, use_model, data)

    def _parse_response(self, prompt: str, model: str, data: dict) -> LLMResponse:
        message = data["choices"][0]["message"]
        text = message.get("content") or ""
        usage = data.get("usage") or {}
        in_tokens = int(usage.get("prompt_tokens", 0))
        out_tokens = int(usage.get("completion_tokens", 0))

        cost = (
            (in_tokens / 1_000_000) * self.config.input_usd_per_m
            + (out_tokens / 1_000_000) * self.config.output_usd_per_m
        )

        citations: list[Citation] = []

        # Standard OpenRouter shape: message.annotations[].url_citation.*
        for ann in message.get("annotations") or []:
            if ann.get("type") != "url_citation":
                continue
            cit = ann.get("url_citation") or {}
            url = cit.get("url")
            if not url:
                continue
            citations.append(
                Citation(
                    url=url,
                    title=cit.get("title"),
                    snippet=cit.get("content"),
                )
            )

        # Fallback for older Perplexity passthrough: top-level `citations: [url, ...]`
        if not citations:
            for url in data.get("citations") or []:
                if isinstance(url, str) and url:
                    citations.append(Citation(url=url))

        return LLMResponse(
            provider=self.name,
            model=model,
            query=prompt,
            response_text=text,
            citations=citations,
            raw=data,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=cost,
        )

    def cost_estimate(
        self,
        n_queries: int,
        avg_input_tokens: int = 200,
        avg_output_tokens: int = 500,
    ) -> float:
        """Estimate cost in USD for n_queries.

        For models without native search (using `:online`), this includes:
        - The OpenRouter web_search service fee (~$0.025/query at default settings)
        - The extra input tokens from injected search snippets (~+2500 tokens/query)

        Token pricing varies by vendor; search fees are flat OpenRouter pricing.
        Verify against actual OpenRouter dashboard after first real run.
        """
        effective_input_tokens = avg_input_tokens
        search_fee = 0.0
        if not self.config.has_native_search:
            effective_input_tokens += ONLINE_EXTRA_INPUT_TOKENS
            search_fee = n_queries * SEARCH_FEE_PER_QUERY_USD

        in_cost = (n_queries * effective_input_tokens / 1_000_000) * self.config.input_usd_per_m
        out_cost = (n_queries * avg_output_tokens / 1_000_000) * self.config.output_usd_per_m
        return in_cost + out_cost + search_fee


# Catalog of models we track. Edit this list to add/remove targets.
#
# Goal: track what consumer defaults each AI search product actually serves
# (not the absolute SOTA). When a vendor flips their consumer default, update.
#
# Pricing verified 2026-05-08 against OpenRouter model pages. If a model
# 404s or pricing breaks, see failures.md and update slug + cost together.
DEFAULT_MODELS: list[OpenRouterModelConfig] = [
    # Perplexity Pro tier default. (Free tier uses bare `perplexity/sonar`;
    # could add as a 5th model later to track the free-user experience.)
    OpenRouterModelConfig(
        model="perplexity/sonar-pro",
        display_name="Perplexity Sonar Pro",
        has_native_search=True,
        input_usd_per_m=3.0,
        output_usd_per_m=15.0,
    ),
    # ChatGPT consumer default since 2026-05-05 (was gpt-4o before).
    # API name is gpt-5.5; "instant" is the consumer-product branding only.
    OpenRouterModelConfig(
        model="openai/gpt-5.5",
        display_name="ChatGPT (GPT-5.5)",
        has_native_search=False,
        input_usd_per_m=5.0,
        output_usd_per_m=30.0,
    ),
    # xAI flagship (released 2026-03-31). grok-2 was deprecated on OpenRouter.
    OpenRouterModelConfig(
        model="x-ai/grok-4.20",
        display_name="Grok 4.20",
        has_native_search=False,
        input_usd_per_m=1.25,
        output_usd_per_m=2.50,
    ),
    # Gemini consumer-app default. The OpenRouter slug carries `-preview`
    # suffix even though it's what the consumer Gemini app serves. Replace
    # with non-preview slug when Google promotes it out of preview.
    OpenRouterModelConfig(
        model="google/gemini-3-flash-preview",
        display_name="Gemini 3 Flash",
        has_native_search=False,
        input_usd_per_m=0.50,
        output_usd_per_m=3.0,
    ),
]
