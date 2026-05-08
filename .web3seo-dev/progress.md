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

## Next: real cron run with live OpenRouter key

Acceptance:
- Set `OPENROUTER_API_KEY` in `.env` (one key, all 4 models)
- `uv run python scripts/run_daily.py --date 2026-05-07` produces non-empty snapshot at `frontend/public/snapshots/2026-05-07.json`
- Snapshot has at least 5 protocols mentioned across 50 queries × 4 models = 200 calls
- `errors` table empty for happy path (or near-empty — some flakiness expected from any single model)
- Cost stays under $2 (dry-run estimated ~$0.96 across 4 models)
- `responses.citations_json` populated for Perplexity at minimum; gpt-4o:online / grok:online / gemini:online may also populate via OpenRouter's web_search plugin
- Manually inspect 2-3 raw responses per model, confirm protocol names look right + citations make sense

## Later

- C. **Frontend** (Next.js leaderboard + sparkline charts + sample-context drill-down)
- D. Public deploy (Vercel) + first tweet
- E. Add Claude Sonnet 4.6 to DEFAULT_MODELS once we want broader coverage
- F. Event-triggered scans (defer until cost/signal data justifies)
- G. Citation-host leaderboard ("which crypto media does AI cite most?") as a separate weekly tweet hook
