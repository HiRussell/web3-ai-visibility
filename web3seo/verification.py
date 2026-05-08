"""Map ≠ Territory: independent-channel verification.

Use these helpers on any LLM-claimed fact before trusting it for the
leaderboard. The whole point of this project is to characterize what AIs
say about crypto — but trusting their citations / data without checking
would replicate their errors instead of measuring them.
"""
from __future__ import annotations

import asyncio

import httpx


async def verify_citation(url: str, *, timeout: float = 5.0) -> bool:
    """HTTP HEAD (with GET fallback). True iff URL responds 2xx/3xx.

    Caches nothing. Caller batches as needed (see verify_citations_batch).
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            try:
                r = await client.head(url)
                if r.status_code in (405, 501):
                    r = await client.get(url)
            except httpx.HTTPError:
                r = await client.get(url)
            return r.status_code < 400
    except Exception:
        return False


async def verify_citations_batch(
    urls: list[str],
    *,
    concurrency: int = 10,
    timeout: float = 5.0,
) -> dict[str, bool]:
    """Verify many URLs in parallel. Returns {url: ok}."""
    sem = asyncio.Semaphore(concurrency)

    async def one(url: str) -> tuple[str, bool]:
        async with sem:
            return url, await verify_citation(url, timeout=timeout)

    results = await asyncio.gather(*(one(u) for u in urls))
    return dict(results)
