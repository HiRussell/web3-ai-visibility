"""Phase 2: extract protocol mentions from raw responses.

Idempotent on response_id — re-running deletes existing mentions for that
response and re-extracts. Cheap (no API calls), so it's safe to re-run any
time the canonical index or alias dictionary changes.
"""
from __future__ import annotations

from pathlib import Path

from ..canonical import CanonicalIndex
from ..storage import connect


CONTEXT_WINDOW = 200  # chars on each side of the matched alias


def extract_phase(
    run_date: str,
    db_path: Path,
    canonical: CanonicalIndex,
) -> dict[str, int]:
    counters = {"responses_processed": 0, "mentions_extracted": 0}

    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, response_text FROM responses WHERE run_date = ?",
            (run_date,),
        ).fetchall()

        for row in rows:
            response_id = row["id"]
            text = row["response_text"]

            conn.execute("DELETE FROM mentions WHERE response_id = ?", (response_id,))

            hits = canonical.find(text)
            for ordinal, (protocol, offset, matched_text) in enumerate(hits):
                start = max(0, offset - CONTEXT_WINDOW)
                end = min(len(text), offset + len(matched_text) + CONTEXT_WINDOW)
                context = text[start:end]
                conn.execute(
                    """
                    INSERT INTO mentions
                        (response_id, protocol_id, matched_alias, context, char_offset, ordinal)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (response_id, protocol.id, matched_text, context, offset, ordinal),
                )
                counters["mentions_extracted"] += 1
            counters["responses_processed"] += 1

    return counters
