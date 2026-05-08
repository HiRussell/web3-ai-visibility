"""DefiLlama canonical protocol list + alias resolution.

Map ≠ Territory: when an LLM mentions "Uni" or "uniswap-v3", we map back to
the canonical DefiLlama slug. The alias dictionary is HAND-MAINTAINED in
`data/protocol_aliases.yaml`; LLMs are NOT used to expand aliases (Corvus D-030
lesson: don't let LLMs evaluate / generate canonical references they'll later
be measured against).

The DefiLlama slug list refreshes weekly via scripts/refresh_canonical.py.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Protocol:
    id: str             # DefiLlama slug, e.g. "uniswap-v3"
    name: str           # display name, e.g. "Uniswap V3"
    aliases: list[str]  # additional case-insensitive match strings
    category: str | None = None
    tvl: float | None = None


class CanonicalIndex:
    """Pre-built lookup from any alias → canonical Protocol.

    Word-boundary regex matching avoids partial-word false positives
    (e.g. "uni" inside "unison" should not match Uniswap).
    """

    MIN_ALIAS_LEN = 3  # below this, false-positive rate is too high

    def __init__(self, protocols: list[Protocol]):
        self.protocols: dict[str, Protocol] = {p.id: p for p in protocols}
        self._lookup: dict[str, str] = {}
        for p in protocols:
            candidates = [p.name, p.id, *p.aliases]
            for alias in candidates:
                key = (alias or "").lower().strip()
                if len(key) >= self.MIN_ALIAS_LEN:
                    self._lookup[key] = p.id

    def find(self, text: str) -> list[tuple[Protocol, int, str]]:
        """Find all canonical protocol mentions in text.

        Returns list of (protocol, char_offset, matched_text), in document
        order. Longer aliases tried first so "uniswap v3" wins over "uniswap"
        when both could match the same span.
        """
        hits: list[tuple[Protocol, int, str]] = []
        seen_offsets: set[int] = set()

        sorted_aliases = sorted(self._lookup.items(), key=lambda x: -len(x[0]))
        for alias, pid in sorted_aliases:
            pattern = r"\b" + re.escape(alias) + r"\b"
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                if m.start() in seen_offsets:
                    continue
                # Also skip if this match overlaps with a longer one already found
                if any(s <= m.start() < s + length for s, length in self._taken_spans(seen_offsets, hits)):
                    continue
                seen_offsets.add(m.start())
                hits.append((self.protocols[pid], m.start(), m.group()))

        return sorted(hits, key=lambda x: x[1])

    @staticmethod
    def _taken_spans(seen_offsets: set[int], hits: list[tuple[Protocol, int, str]]):
        return [(offset, len(matched)) for _, offset, matched in hits]

    @classmethod
    def load(cls, defillama_json: Path, aliases_yaml: Path) -> "CanonicalIndex":
        protocols_raw = json.loads(defillama_json.read_text())
        aliases_data = yaml.safe_load(aliases_yaml.read_text()) or {}

        protocols: list[Protocol] = []
        for entry in protocols_raw:
            pid = entry["slug"]
            name = entry["name"]
            extra_aliases = aliases_data.get(pid, []) or []
            protocols.append(
                Protocol(
                    id=pid,
                    name=name,
                    aliases=extra_aliases,
                    category=entry.get("category"),
                    tvl=entry.get("tvl"),
                )
            )
        return cls(protocols)
