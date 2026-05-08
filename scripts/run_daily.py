"""Daily cron entrypoint. Runs all three pipeline phases.

Usage:
    python scripts/run_daily.py                                  # full scan, today UTC
    python scripts/run_daily.py --date 2026-05-07
    python scripts/run_daily.py --phase fetch
    python scripts/run_daily.py --dry-run

Cheap testing:
    python scripts/run_daily.py --limit-queries 10               # first 10 queries only
    python scripts/run_daily.py --models perplexity/sonar-pro    # one model only
    python scripts/run_daily.py --limit-queries 10 --models perplexity/sonar-pro

Models tracked are configured in `web3seo.providers.openrouter.DEFAULT_MODELS`.
A single OPENROUTER_API_KEY drives them all (D-010).
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv

from web3seo.canonical import CanonicalIndex
from web3seo.pipeline.aggregate import aggregate_phase
from web3seo.pipeline.extract import extract_phase
from web3seo.pipeline.fetch import fetch_phase
from web3seo.providers import DEFAULT_MODELS, LLMProvider, OpenRouterProvider


load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "data" / "store.db"
QUERIES_YAML = REPO_ROOT / "data" / "queries.yaml"
ALIASES_YAML = REPO_ROOT / "data" / "protocol_aliases.yaml"
DEFILLAMA_JSON = REPO_ROOT / "data" / "defillama_protocols.json"
SNAPSHOTS_DIR = REPO_ROOT / "frontend" / "public" / "snapshots"


def load_providers(model_filter: list[str] | None = None) -> list[LLMProvider]:
    """One OpenRouterProvider per configured model.

    `model_filter` (e.g. ["perplexity/sonar-pro"]) restricts to a subset.
    Useful for cheap testing.
    """
    if not os.getenv("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY not set; nothing to do.")

    configs = DEFAULT_MODELS
    if model_filter:
        wanted = set(model_filter)
        configs = [c for c in configs if c.model in wanted]
        unknown = wanted - {c.model for c in DEFAULT_MODELS}
        if unknown:
            raise SystemExit(
                f"Unknown model slugs: {sorted(unknown)}. "
                f"Available: {sorted(c.model for c in DEFAULT_MODELS)}"
            )
        if not configs:
            raise SystemExit("After filter, no models selected.")
    return [OpenRouterProvider(cfg) for cfg in configs]


def check_budget(providers: list[LLMProvider], n_queries: int) -> None:
    budget = float(os.getenv("DAILY_BUDGET_USD", "2.0"))
    estimate = sum(p.cost_estimate(n_queries) for p in providers)
    breakdown = ", ".join(
        f"{p.name}=${p.cost_estimate(n_queries):.2f}" for p in providers
    )
    click.echo(f"[budget] estimate ${estimate:.2f} cap ${budget:.2f} ({breakdown})")
    if estimate > budget:
        raise SystemExit(
            f"Estimated cost ${estimate:.2f} exceeds DAILY_BUDGET_USD ${budget:.2f}; aborting. "
            f"Raise budget or use --limit-queries / --models to reduce scope."
        )


def load_queries(limit: int | None = None) -> list[dict]:
    queries = yaml.safe_load(QUERIES_YAML.read_text())["queries"]
    if limit is not None:
        queries = queries[:limit]
    return queries


@click.command()
@click.option("--date", "run_date", default=None, help="UTC date YYYY-MM-DD (default: today UTC)")
@click.option(
    "--phase",
    type=click.Choice(["fetch", "extract", "aggregate", "all"]),
    default="all",
    help="Run a single phase or all three.",
)
@click.option("--dry-run", is_flag=True, help="Skip API calls; print what would be queried.")
@click.option(
    "--limit-queries",
    type=int,
    default=None,
    help="Run only the first N queries from queries.yaml (cheap testing).",
)
@click.option(
    "--models",
    default=None,
    help="Comma-separated model slugs to use (e.g. 'perplexity/sonar-pro'). Default: all in DEFAULT_MODELS.",
)
def main(
    run_date: str | None,
    phase: str,
    dry_run: bool,
    limit_queries: int | None,
    models: str | None,
) -> None:
    if not run_date:
        run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    model_filter = [m.strip() for m in models.split(",")] if models else None
    providers = load_providers(model_filter)
    click.echo(f"[providers] {[p.name for p in providers]}")

    if not DEFILLAMA_JSON.exists():
        raise SystemExit(
            f"{DEFILLAMA_JSON} not found. Run scripts/refresh_canonical.py first."
        )
    canonical = CanonicalIndex.load(DEFILLAMA_JSON, ALIASES_YAML)
    click.echo(f"[canonical] {len(canonical.protocols)} protocols loaded")

    queries = load_queries(limit_queries)
    click.echo(f"[queries] {len(queries)} (of {len(load_queries())} total)")

    # Write the (possibly filtered) queries to a temp YAML for fetch_phase to pick up.
    if limit_queries is not None:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.safe_dump({"queries": queries}, tmp)
        tmp.close()
        queries_yaml_path = Path(tmp.name)
    else:
        queries_yaml_path = QUERIES_YAML

    if phase in ("fetch", "all"):
        check_budget(providers, n_queries=len(queries))
        click.echo(f"[fetch] {run_date} across {len(providers)} models")
        result = asyncio.run(
            fetch_phase(run_date, queries_yaml_path, providers, DEFAULT_DB, dry_run=dry_run)
        )
        click.echo(f"[fetch] {result}")

    if phase in ("extract", "all"):
        click.echo(f"[extract] {run_date}")
        result = extract_phase(run_date, DEFAULT_DB, canonical)
        click.echo(f"[extract] {result}")

    if phase in ("aggregate", "all"):
        click.echo(f"[aggregate] {run_date}")
        snapshot_path = SNAPSHOTS_DIR / f"{run_date}.json"
        result = aggregate_phase(run_date, DEFAULT_DB, snapshot_path)
        click.echo(f"[aggregate] {result}")
        click.echo(f"[aggregate] wrote {snapshot_path}")


if __name__ == "__main__":
    main()
