"""Pull the latest DefiLlama protocols list to data/defillama_protocols.json.

Run weekly (cron or manual). Independent from daily fetch — protocol universe
changes slowly and we don't want a transient DefiLlama outage to take down
the daily scan.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "data" / "defillama_protocols.json"
DEFILLAMA_URL = "https://api.llama.fi/protocols"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"GET {DEFILLAMA_URL} ...")
    r = httpx.get(DEFILLAMA_URL, timeout=30.0)
    r.raise_for_status()
    protocols = r.json()
    minimal = [
        {
            "slug": p["slug"],
            "name": p["name"],
            "category": p.get("category"),
            "tvl": p.get("tvl", 0),
        }
        for p in protocols
        if p.get("slug") and p.get("name")
    ]
    OUT.write_text(json.dumps(minimal, indent=2, ensure_ascii=False))
    print(f"Wrote {len(minimal)} protocols to {OUT}")


if __name__ == "__main__":
    main()
