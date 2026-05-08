"""Phase 3: aggregate mentions into the public snapshot JSON.

Output: `frontend/public/snapshots/{run_date}.json`. The frontend reads multiple
snapshot files for time-series leaderboards. Each snapshot is independent — no
cross-day stitching at this layer (KISS; D-006).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ..storage import connect


def aggregate_phase(
    run_date: str,
    db_path: Path,
    output_path: Path,
) -> dict[str, int]:
    with connect(db_path) as conn:
        # Per-protocol totals + per-provider breakdown
        rows = conn.execute(
            """
            SELECT m.protocol_id, r.provider
            FROM mentions m
            JOIN responses r ON r.id = m.response_id
            WHERE r.run_date = ?
            """,
            (run_date,),
        ).fetchall()

        # Sample contexts (first 3 per protocol) for hover/click-through on the leaderboard
        ctx_rows = conn.execute(
            """
            SELECT m.protocol_id, m.context, m.matched_alias, r.provider, r.query_text, r.query_id
            FROM mentions m
            JOIN responses r ON r.id = m.response_id
            WHERE r.run_date = ?
            ORDER BY m.id
            """,
            (run_date,),
        ).fetchall()

        # Citation breakdown
        cit_rows = conn.execute(
            """
            SELECT provider, citations_json
            FROM responses
            WHERE run_date = ?
            """,
            (run_date,),
        ).fetchall()

    total: Counter = Counter()
    per_provider: dict[str, Counter] = {}
    for row in rows:
        pid, prov = row["protocol_id"], row["provider"]
        total[pid] += 1
        per_provider.setdefault(prov, Counter())[pid] += 1

    contexts: dict[str, list[dict]] = {}
    for r in ctx_rows:
        pid = r["protocol_id"]
        bucket = contexts.setdefault(pid, [])
        if len(bucket) < 3:
            bucket.append({
                "provider": r["provider"],
                "query_id": r["query_id"],
                "query": r["query_text"],
                "matched_alias": r["matched_alias"],
                "context": r["context"],
            })

    # Citation host frequency
    citation_hosts: Counter = Counter()
    for r in cit_rows:
        try:
            cits = json.loads(r["citations_json"])
        except json.JSONDecodeError:
            continue
        for c in cits:
            url = c.get("url", "")
            if "://" in url:
                host = url.split("://", 1)[1].split("/", 1)[0]
                citation_hosts[host] += 1

    leaderboard = []
    for pid, count in total.most_common(100):
        leaderboard.append({
            "protocol_id": pid,
            "total_mentions": count,
            "by_provider": {prov: c.get(pid, 0) for prov, c in per_provider.items()},
            "sample_contexts": contexts.get(pid, []),
        })

    output = {
        "run_date": run_date,
        "leaderboard": leaderboard,
        "top_citation_hosts": [
            {"host": h, "count": c} for h, c in citation_hosts.most_common(50)
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    return {
        "protocols_in_leaderboard": len(leaderboard),
        "citation_hosts_tracked": len(citation_hosts),
    }
