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
