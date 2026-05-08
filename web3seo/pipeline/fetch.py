"""Phase 1: query LLMs and persist raw responses.

Idempotent on (run_date, query_id, provider). Errors don't crash the pipeline
— they're persisted to errors table and the aggregate phase runs on partial
data. This is the "fail-soft" property from Corvus's 第六层"约束与恢复".
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from ..providers.base import LLMProvider
from ..storage import connect, has_response, save_error, save_response


async def fetch_phase(
    run_date: str,
    queries_yaml: Path,
    providers: list[LLMProvider],
    db_path: Path,
    *,
    concurrency: int = 4,
    dry_run: bool = False,
) -> dict[str, int]:
    """Run all (query, provider) pairs not already done. Return counters."""
    queries = yaml.safe_load(queries_yaml.read_text())["queries"]

    counters = {"skipped": 0, "saved": 0, "errors": 0}
    sem = asyncio.Semaphore(concurrency)

    async def run_one(q: dict, p: LLMProvider) -> None:
        with connect(db_path) as conn:
            if has_response(conn, run_date, q["id"], p.name):
                counters["skipped"] += 1
                return

        if dry_run:
            print(f"[dry-run] would query: {p.name} {q['id']}")
            return

        async with sem:
            try:
                resp = await p.query(q["text"])
            except Exception as e:
                with connect(db_path) as conn:
                    save_error(conn, run_date, "fetch", e, query_id=q["id"], provider=p.name)
                counters["errors"] += 1
                return

        with connect(db_path) as conn:
            save_response(conn, run_date, q["id"], resp)
        counters["saved"] += 1

    tasks = [run_one(q, p) for q in queries for p in providers]
    await asyncio.gather(*tasks)
    return counters
