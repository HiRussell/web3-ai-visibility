# Design decisions

Append-only log. Each entry: ID, date, decision, why, when-to-revisit.

## D-001 (2026-05-07): 4 LLM providers — Perplexity, OpenAI gpt-4o, xAI Grok, Google Gemini

**Why these 4**:
- **Perplexity** (priority): live search + returns citation URLs. Most differentiated data
  — what sources do AIs cite for crypto answers? Nobody publishes this.
- **OpenAI gpt-4o**: simulates ChatGPT consumer experience (largest install base).
- **xAI Grok**: live X (Twitter) data, crypto-Twitter-biased perspective.
- **Gemini 2.0 Flash**: Google Search grounding, captures Google AI Overview behavior.

**Excluded**:
- Anthropic Claude — no consumer search product, parametric only, adds little vs gpt-4o.
- DeepSeek / Qwen / Kimi — low consumer adoption in crypto market.

**Revisit if**: a major new consumer search AI lands (e.g. Apple Intelligence with web), or
one of the four above changes search behavior materially.

## D-002 (2026-05-07): No sentiment classification in v1, but DO save mention context

**Why**:
- LLM-evaluating-LLM is unreliable (cite Corvus D-030 rollback).
- Crypto-specific sentiment is genuinely ambiguous (e.g. "DeFi 风险高" — neutral or negative?).
- BUT: 200-char window around each protocol mention IS persisted from day 1, so:
  - Backfilling sentiment later doesn't require re-querying APIs
  - Protocol teams can read the actual context themselves
  - Tweet hooks have exact quotes available

**Revisit if**: a deterministic sentiment rule emerges from observing the raw context corpus.

## D-003 (2026-05-07): Daily cron, not realtime / not hourly

**Why daily for v1**:
- Cost: 50 queries × 4 providers × 30 days = 6000 calls/month, ~$5–15/month. Manageable.
- Hourly = 24× cost without proportional signal benefit for most queries.
- Schema includes `fetched_at` so frequency change is one config flip.

**Revisit if**:
- Live-search providers (Perplexity / Grok) show meaningful hour-to-hour variation that the
  daily cadence misses
- Event-triggered scans (Twitter trending, DefiLlama TVL spike) become a clearer signal than
  fixed shorter cadence

## D-004 (2026-05-07): Three-stage pipeline (fetch → extract → aggregate)

**Why split**:
- Each phase is idempotent on a different key:
  - fetch: `(run_date, query_id, provider)`
  - extract: `response_id` (cheap, just regex; safe to re-run on schema change)
  - aggregate: `run_date` (overwrite snapshot JSON)
- Failure in extract doesn't waste fetch's API spend.
- Schema upgrades only require re-running affected phases.
- Mirrors Corvus's "约束与恢复" 第六层.

## D-005 (2026-05-07): Protocol name extraction = regex + DefiLlama canonical list. NOT another LLM.

**Why**:
- Corvus D-030: LLM-evaluating-LLM yields self-affirming bias.
- Regex against canonical list is deterministic and debuggable.
- Aliases hand-maintained in `data/protocol_aliases.yaml` (small enough to curate).
- Word-boundary matching to avoid "uni" matching inside "unison".
- LLM may LATER serve as a fallback to *suggest* new aliases for human review, but never
  auto-write to canonical.

## D-006 (2026-05-07): DB ephemeral per cron run; only snapshot JSON committed

**Why**:
- DB committed to git would bloat history and creates merge conflicts on parallel runs.
- Per-day snapshot JSON at `frontend/public/snapshots/{date}.json` is the durable artifact.
- Frontend can read multiple snapshot files for time series.
- DB lives only during the cron job — fetched data → extracted mentions → aggregated JSON,
  then DB is discarded.

**Revisit if**: cross-day analysis becomes hot path (then move to a hosted DB).

## D-007 (2026-05-07): Flat package layout (no `src/` directory)

**Why**: vibe-code project, no need for `src/` layout's import isolation. Flat is one less
PYTHONPATH gotcha during dev. Reverse if shipping as a library.

## D-008 (2026-05-07): Provider list driven by which API keys are present

**Why**: graceful degradation. Bring up Perplexity-only, ship, add others as keys are added.
No code change needed to disable a provider — just unset its env var.

## D-010 (2026-05-07): Use OpenRouter as single LLM gateway, not direct vendor APIs

**Reversal of an earlier implicit decision.** First wrote 4 separate provider classes
(perplexity.py / openai.py / xai.py / gemini.py) hitting vendor APIs directly. User
pushed back: "你为什么会用 perplexity 呢？为什么不直接用 open router？"

Verified via WebFetch (https://openrouter.ai/docs/guides/features/plugins/web-search):
OpenRouter standardizes citations into `message.annotations[].url_citation` with
`{url, title, content, start_index, end_index}`. Native-search models (Perplexity Sonar)
emit them naturally; others get search via `:online` suffix or `openrouter:web_search`
server tool — same shape across providers.

**Honest reasons OpenRouter wins for this project (small but real):**

1. One API key, one bill — no need to register 4 vendors / track 4 ToS / fund 4 wallets.
2. Citation `start_index` / `end_index` are richer than Perplexity's flat URL list —
   you know *where* in the answer text each citation was used.
3. Less code: 1 provider class instead of 4.

**Reasons that are NOT actually load-bearing here (don't believe my first draft):**

- ~~"Vendor lock defense"~~ — this is a hobby data cron with no customers, no
  compliance, no switching cost. Vendor lock is a non-issue. (User caught me citing
  Corvus methodology like an incantation; flagged self-correction.)
- ~~"Corvus's '永远走 OpenAI-compatible 抽象层' applies"~~ — that principle was for
  a customer-data-bearing system. Importing it here is "思维模型中毒" — using
  the model name to skip real thinking. Corvus CLAUDE.md explicitly warns against this.

**Trade-offs accepted:**

- ~5% margin OpenRouter takes vs direct (cents at this scale)
- Single point of failure: if OpenRouter is down, all 4 models down. Mitigation: switch
  back to direct in a few hours if it ever matters.

**What changed:**

- Deleted: `web3seo/providers/{perplexity,openai,xai,gemini}.py`
- Added: `web3seo/providers/openrouter.py` with `OpenRouterProvider` + `DEFAULT_MODELS`
- `.env.example`: 4 keys → 1 `OPENROUTER_API_KEY`
- Tests: single `test_openrouter.py` covers all model behaviours
- GitHub Actions workflow: 4 secrets → 1 secret

**Revisit if:**

- A vendor exposes a feature OpenRouter doesn't passthrough (add a direct-API class
  alongside the OpenRouter ones for that one model)
- OpenRouter starts training on requests or materially raises margin

**Meta-lesson** (also worth flagging in failures.md if it happens again):

When applying a principle from another project, ask "does the situation that made
the principle valuable in project X also exist here?" If not, the principle is
decoration. Don't cite principles to skip thinking about the specific case.

## D-009 (2026-05-07): `cost_estimate()` on every Provider, pre-flight budget gate

**Why**: defends against vendor pricing changes silently bankrupting a hobby project.
`run_daily.py` aborts if total estimate > `DAILY_BUDGET_USD`. Cost numbers are hardcoded in
each provider — must be reviewed when vendor pricing changes (link to vendor pricing page in
each provider file).
