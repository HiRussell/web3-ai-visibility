"""Abstract LLM provider interface.

Vendor-lock defense: every provider (Perplexity / OpenAI / xAI / Gemini)
implements the same shape, so switching providers is a config change, not a
code rewrite.

Map ≠ Territory: every response carries (a) the model's text answer (the map)
and (b) raw citations (territory pointers). Verification of those citations
happens in `web3seo.verification`, NOT here — this layer is a thin transport.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Citation:
    """A source URL the LLM cited for an answer.

    Empty `citations` list on an LLMResponse means: provider returned no
    citations (parametric response, or live-search provider that didn't return
    any for this query). Distinguish from `[Citation(url=...)]` with one entry.
    """
    url: str
    title: str | None = None
    snippet: str | None = None


@dataclass
class LLMResponse:
    """Single (provider, query) response.

    `raw` keeps the FULL provider response untouched. Corvus's "数据层 > prompt
    工程" lesson: never lose data at fetch time, you can't backfill what you
    didn't save. Storage layer JSON-encodes this for replay later.
    """
    provider: str
    model: str
    query: str
    response_text: str
    citations: list[Citation] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class LLMProvider(ABC):
    """One implementation per LLM vendor.

    Subclasses MUST set:
        name             — canonical short name ("perplexity", "openai", ...)
        has_live_search  — does this model do live web search per query?
        default_model    — used when caller doesn't specify

    Subclasses MUST NOT retry internally. The pipeline.fetch layer handles
    retry + idempotency at the (run_date, query_id, provider) level.
    """
    name: str
    has_live_search: bool
    default_model: str

    @abstractmethod
    async def query(
        self,
        prompt: str,
        *,
        model: str | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    def cost_estimate(
        self,
        n_queries: int,
        avg_input_tokens: int = 200,
        avg_output_tokens: int = 500,
    ) -> float:
        """Pre-flight cost estimate, USD. Used by run_daily for budget gate."""
