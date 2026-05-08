# Progress

## Current phase

**Awaiting first real Perplexity API run** — 2026-05-07

## A — Initial scaffolding ✅ DONE 2026-05-07

- [x] Repo skeleton (flat layout, web3seo + scripts + tests + data + .github)
- [x] LLMProvider base class
- [x] SQLite storage with `(run_date, query_id, provider)` idempotency
- [x] Three-stage pipeline (fetch / extract / aggregate)
- [x] Canonical protocol index + alias resolution + word-boundary matching
- [x] HTTP citation verification (Map ≠ Territory)
- [x] CLI entry `scripts/run_daily.py` (verified `--help` and `--dry-run`)
- [x] DefiLlama refresh `scripts/refresh_canonical.py` (verified: pulled 7,451 protocols)
- [x] GitHub Actions daily cron
- [x] 50 seed queries in `data/queries.yaml`

## B — End-to-end with mocked OpenRouter ✅ DONE 2026-05-07

- [x] Built `PerplexityProvider` direct-API. **Then refactored to `OpenRouterProvider` after
      D-010 review** — 4 vendor providers collapsed into one catalog-driven class.
- [x] `OpenRouterProvider.query()` against `/api/v1/chat/completions`
- [x] Parses `message.annotations[].url_citation` (OpenRouter standard schema)
- [x] Falls back to legacy top-level `citations: [url, ...]` shape
- [x] `:online` suffix auto-added for models without native search
- [x] Cost calc per-model from `OpenRouterModelConfig`
- [x] `DEFAULT_MODELS` catalog: perplexity/sonar-pro, openai/gpt-4o, x-ai/grok-2, google/gemini-2.0-flash-001
- [x] `httpx.MockTransport`-based unit tests (8 cases for OpenRouter + e2e)
- [x] End-to-end pipeline test (mocked OpenRouter → fetch → extract → aggregate → snapshot JSON)
- [x] Idempotency verified: re-run skips already-fetched (query, provider) pairs
- [x] Error path verified: 500 status persists to `errors` table without crashing pipeline
- [x] **Total: 19 tests passing** (10 openrouter + e2e, 9 smoke)
- [x] CLI dry-run verified: 4 models × 50 queries listed, $0.96 cost estimate

## C — First real run + false-positive fix ✅ DONE 2026-05-08

- [x] Live `OPENROUTER_API_KEY` configured
- [x] First real run: `--limit-queries 10 --models perplexity/sonar-pro`
- [x] 10/10 saved, 0 errors, 53 citation hosts captured
- [x] OpenRouter → Perplexity citation passthrough verified ✓
- [x] **Failure mode caught**: protocol leaderboard polluted by chain slugs + English-word slugs (see failures.md 2026-05-08)
- [x] Fix: `CanonicalIndex.DEFAULT_STOPLIST` + `DEFAULT_MIN_TVL_USD = $1M`
- [x] After fix: top 10 all legitimate (Lido / Kalshi / Beefy / SushiSwap / Frax / ...)
- [x] 23/23 tests passing (added 4 cases for stoplist/TVL filter regression guard)
- [x] First commit pushed to `HiRussell/web3-ai-visibility` (private)
- [x] Project-level `CLAUDE.md` added with permission overrides for this hobby project

## Next: scale data run

Plan:
1. Run all 50 queries × Perplexity Sonar Pro (~$0.50). Density check + see what real protocol leaderboard looks like with 5x more data.
2. Inspect: top 20 protocols, top 30 citation hosts, model bias, query coverage. Iterate stoplist if more false positives surface.
3. Decide: stay Perplexity-only weekly cadence ($18/month) or scale to 4 models ($170/month) for cross-model comparison.

## Later

- C. **Frontend** (Next.js leaderboard + sparkline charts + sample-context drill-down)
- D. Public deploy (Vercel) + first tweet ✅ done 2026-05-08, live at https://web3-ai-visibility.vercel.app
- E. Add Claude Sonnet 4.6 to DEFAULT_MODELS once we want broader coverage
- F. Event-triggered scans (defer until cost/signal data justifies)
- G. Citation-host leaderboard ("which crypto media does AI cite most?") as a separate weekly tweet hook
- H. **Query rotation pool**: expand `data/queries.yaml` to ~80–100 queries, randomly sample 50 per week. Increases data diversity + surfaces protocols that wouldn't appear in a fixed seed set. Trade-off: harder to compare week-over-week (different queries → different mention counts). Maybe split: 30 fixed (for trend tracking) + 20 rotating (for diversity).
- I. Cost optimization (deferred): max_results 5→2 in OpenRouter plugin config saves ~$1.25/scan. User opted to keep $24/month weekly cadence for now since cost is hobby-acceptable and citation richness matters more than $20/month savings.
