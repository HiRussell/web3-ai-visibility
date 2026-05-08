# Failures log

Append-only. Format per entry:

- **Date** (UTC)
- **Symptom** (what did the user / cron / test see?)
- **Root cause** (the actual reason, ideally with commit / log line)
- **Fix** (what was changed)
- **Prevention** (test / guard / process that would catch this earlier)

Focus this log on failure modes that **couldn't have been predicted from reading the code**.
Run-of-the-mill bugs go in commit messages, not here.

---

## 2026-05-08 — Protocol leaderboard polluted by chain names + English-word slugs

**Symptom**: First real cron run (10 queries × Perplexity Sonar Pro). Pipeline ran clean (10 saved, 0 errors, 53 citation hosts), but top of protocol leaderboard was nonsense:

```
 1. ethereum    21    ← chain, not protocol
 2. market      12    ← English word
 3. arbitrum     8    ← chain
 4. use          7    ← English word
 5. lido         7    ← legit
 6. across       5    ← Across Protocol legit, but mostly the English word
 7. solana       5    ← chain
 8. depth        4    ← English word
 9. current      3    ← English word
10. cap          3    ← English word
```

Of 129 mentions extracted from 10 responses, an estimated 60–70% were noise.

**Root cause**: DefiLlama's protocol list (7,451 entries) contains:
1. **Chain-level TVL aggregations as "protocols"** (slug `ethereum`, `solana`, `arbitrum`, etc.) — they're real entries, but not what users mean when they say "what protocol should I use".
2. **Long-tail micro/abandoned projects whose slugs are common English words** (`use`, `depth`, `current`, `gravity`, `cap`, `scale`, `market`, `back`, `next`, `core`, ...). These are often abandoned, have $0 TVL, but their slugs match in any English text.

Word-boundary regex on the bare slug list matched all of them indiscriminately. `MIN_ALIAS_LEN = 3` doesn't help because all the offenders are 3+ chars.

This was a **classic Map-vs-Territory failure**: the canonical list (the "map" of what we're tracking) didn't actually correspond to the user-facing concept of "protocol" (the "territory"). I trusted the canonical source without sanity-checking what it contained.

**Fix** (`web3seo/canonical.py`):
1. `CanonicalIndex.DEFAULT_STOPLIST` — frozenset of ~50 slugs to hard-block. Includes:
   - All major chain slugs (ethereum, solana, arbitrum, base, optimism, ...)
   - High-frequency English-word slugs (use, market, depth, cap, scale, ...)
   - General DeFi-vocab words that aren't specific protocols (yield, stake, lending, ...)
2. `CanonicalIndex.DEFAULT_MIN_TVL_USD = 1_000_000.0` — drop protocols with TVL < $1M. Eliminates the long-tail noise that survived the stoplist.

After fix, same 10 responses produced 44 mentions across 24 protocols. Top 10 are all legitimate (Lido / Kalshi / Beefy / SushiSwap / Frax / Yearn / Harvest / Nexo / Robinhood / KuCoin).

**Prevention**:
1. New tests in `tests/test_smoke.py` lock in stoplist + TVL filter behaviour — regression is caught immediately if either is bypassed.
2. Process: when adding a new false-positive observation, append to `DEFAULT_STOPLIST` and re-run `extract` phase (idempotent, no new API calls). Don't add aliases — add stoplist entries.
3. Meta-lesson: when ingesting an external "canonical" list, sample what's actually in it before trusting it. DefiLlama's protocol list is much broader than what users mentally call "a DeFi protocol".

**Notes for future**:
- Across Protocol IS a real bridge — current stoplist drops it. Acceptable v1 trade-off (it's mentioned rarely; English "across" matches dominate). Revisit if Across becomes a frequently-discussed protocol in queries.
- TVL threshold of $1M is conservative; can tune higher ($10M) if noise persists, lower if we want long-tail coverage.

---

## 2026-05-08 — Grok model slug `x-ai/grok-2` 404'd by OpenRouter

**Symptom**: First 4-model real run (50 q × 4). Three of four models all 50/50 saved, but `x-ai/grok-2` returned **50/50 errors**, all `HTTPStatusError 404 Not Found`.

**Root cause**: OpenRouter has deprecated/removed `x-ai/grok-2` from their model catalog. xAI's current flagship is `x-ai/grok-4.20` (released 2026-03-31). I'd hardcoded the older slug from memory rather than verifying against the current catalog.

This is the **gemini-flash-lite lesson again** (Corvus D-039) — vendor model slugs change. Hardcoded slugs without periodic verification are a vendor-lock failure mode that even OpenRouter's abstraction can't prevent.

**Fix** (`web3seo/providers/openrouter.py`):
- `DEFAULT_MODELS`: replaced `x-ai/grok-2` → `x-ai/grok-4.20`
- Updated pricing accordingly ($2/M → $1.25/M input, $10/M → $2.50/M output — newer model is cheaper, nice).
- Inline comment with link to verify on price changes.

**Prevention**:
1. **Process**: when a model errors with 404 / "model_not_found", first check OpenRouter's model catalog at https://openrouter.ai/models before debugging code.
2. **Idea (deferred)**: a quarterly `scripts/refresh_model_catalog.py` that pulls live OpenRouter model list and warns on slugs in `DEFAULT_MODELS` that no longer exist. Defer until we have ≥ 3 such incidents.

**Notes**:
- Other 3 models all worked end-to-end through the full pipeline. Idempotency + fail-soft worked: the 50 Grok errors didn't crash the run; the other 150 successful responses still flowed through extract + aggregate normally.
- Errors table now has 50 stale `x-ai/grok-2` entries. Could prune them but they're useful as a record. Leave for now.

---

## 2026-05-08 — gpt-5.5 全部 402, gemini-3-flash-preview 67% 403

**Symptom**: After updating DEFAULT_MODELS to consumer-default slugs (gpt-5.5 + gemini-3-flash-preview) and re-running, 50/50 gpt-5.5 returned 402 Payment Required, and 33/50 gemini-3-flash-preview returned 403 Forbidden (17 succeeded first, then the rest started failing).

**Root cause**:
- **gpt-5.5 402**: User's OpenRouter wallet didn't have enough credit for gpt-5.5's pricing ($5/M input, $30/M output) — significantly more expensive than gpt-4o. Credit ran out before any single call succeeded. This is a per-call cost gate on OpenRouter's side: if a request's max possible cost exceeds remaining wallet balance, request is rejected pre-flight.
- **gemini-3-flash-preview 403**: Likely a per-model rate limit or preview-tier access cap kicking in after 17 calls. Could also be a content-policy gate triggered by certain queries (e.g. risk-related queries in our seed). Worth investigating; for now treat as flaky.

**Fix (this incident)**:
1. Deleted the 17 partial gemini-3-flash-preview responses + 116 mentions from DB, since incomplete-by-model data pollutes the cross-model leaderboard ("17 vs 50" looks like real divergence but isn't).
2. Re-aggregated to clean 4-model snapshot (perplexity / gpt-4o / grok-4.20 / gemini-2.0). Site still meaningful; tweet copy uses this dataset.
3. Did NOT roll back DEFAULT_MODELS — keeping gpt-5.5 / gemini-3-flash-preview slugs so the next budgeted scan (when user tops up wallet) auto-switches. Frontend `activeProviders()` already handles whichever providers have data.

**Prevention**:
1. Pre-flight budget gate (`scripts/run_daily.py:check_budget`) only checks against `DAILY_BUDGET_USD`, not OpenRouter wallet balance. Could query OpenRouter's `/credits` endpoint before scanning to abort early if wallet < estimate. **Deferred** until this fails twice (avoid premature optimization).
2. For preview models like `gemini-3-flash-preview`, add a "first-run sanity check" that runs 5 queries and aborts if error rate > 50% — saves spending on a known-broken target. **Deferred**.
3. Process: when adding a new expensive model, run 1-query test first to verify wallet has headroom AND model is accessible, before committing 50× spend.
