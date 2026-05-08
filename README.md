# Web3 AI Visibility

Track which crypto protocols get mentioned by LLM search (Perplexity / ChatGPT / Grok / Gemini) when users ask common Web3 questions.

## What this is

A daily cron job that:
1. Runs ~50 hand-crafted crypto queries across 4 LLM providers
2. Extracts which protocols get mentioned, against the DefiLlama canonical list
3. Publishes a public leaderboard

## What this is NOT (v1)

- A user system (no login, no accounts)
- A real-time tool (daily scan)
- A sentiment classifier (only mention frequency + raw context)
- A B2B SaaS (this is a vibe-code side project)

## Stack

- Python 3.11 + httpx
- SQLite (idempotency-keyed storage)
- **OpenRouter** as the single LLM gateway (one key drives Perplexity / GPT-4o / Grok / Gemini; D-010)
- GitHub Actions cron (daily, 04:00 UTC)
- Next.js + Tailwind on Vercel (static-generated leaderboard, separate frontend/)

## Principles (inherited from `corvus/CLAUDE.md`)

- **Map ≠ Territory**: protocol names cross-checked against DefiLlama canonical list; citation URLs HTTP-verified before being trusted
- **Vendor lock defense**: `LLMProvider` abstract interface; switching providers is a config change
- **Idempotency**: `(run_date, query_id, provider)` is the unique key; cron interruptions resume cleanly
- **三阶段独立**: fetch / extract / aggregate, each idempotent on its own keys
- **如无必要勿增实体**: no UX bloat, no premature abstractions beyond what's cheap-now-expensive-later

## Quick start

```bash
# 1. install deps
uv sync --dev

# 2. configure: one OpenRouter key drives all 4 models
cp .env.example .env
# edit .env: set OPENROUTER_API_KEY (get one at https://openrouter.ai/keys, prepay $5–10)

# 3. pull DefiLlama protocol list
uv run python scripts/refresh_canonical.py

# 4. run a daily scan
uv run python scripts/run_daily.py --date 2026-05-07

# 5. tests
uv run pytest
```

## Repo layout

```
web3seo/                # main package (flat layout)
  providers/            # one file per LLM vendor, all implement LLMProvider
  pipeline/             # 3 phases: fetch -> extract -> aggregate
  storage.py            # SQLite + idempotency
  canonical.py          # DefiLlama + alias resolution
  verification.py       # Map-not-Territory checks (HTTP, canonical lookup)
data/
  queries.yaml          # 50 hand-crafted seed queries
  protocol_aliases.yaml # canonical_id -> aliases (hand-maintained)
  defillama_protocols.json  # generated weekly
scripts/
  run_daily.py          # cron entry, runs all 3 phases
  refresh_canonical.py  # weekly DefiLlama refresh
.web3seo-dev/           # dev knowledge base, anti-amnesia
  progress.md
  decisions.md
  failures.md
frontend/               # Next.js leaderboard (added later)
.github/workflows/      # daily cron + deploy
tests/
```

## Why this might matter

Ahrefs / SEMrush optimize for Google SEO. AI search (ChatGPT / Perplexity / Grok / Gemini) is eating that traffic, and nobody publishes data on which protocols those AIs actually recommend. That's the gap.

For protocol teams: knowing "ChatGPT recommends our competitor over us" is the new SEO signal. Knowing "Perplexity cites this blog when answering crypto questions" is the new backlink signal.
