# Tweet drafts — 2026-05-08

5 drafts based on first real-data day (50 queries × 4 models). Pick what to post first;
revise wording to your voice.

Numbers come from `frontend/public/snapshots/2026-05-08.json`.

---

## Tweet 1 — Thread headliner (the hook)

> i ran 50 crypto questions through 4 AI search models every day —
> perplexity / chatgpt / grok / gemini — and tracked which protocols they recommend.
>
> day 1 results:
>
> @LidoFinance is the only protocol all 4 AIs agree on. everything else, they wildly disagree.
>
> 🧵

(280 chars OK. Hook + thread promise.)

---

## Tweet 2 — Data drop (top protocols)

> top protocols by AI mentions, cross-model (50 queries × 4 models):
>
> 1. lido        172
> 2. monad       124
> 3. rocket-pool 101
> 4. dextools     89
> 5. gate.io      66
> 6. symbiotic    61
> 7. berachain    47
> 8. bitget       37
> 9. phemex       36
> 10. bydfi       32
>
> full data: <link to repo>

(Surprisingly few "real DeFi" names in top 10 — lots of CEX, lots of weird picks. Provocative.)

---

## Tweet 3 — Provocation (journalism missing)

> crypto journalism barely exists in AI's worldview.
>
> top citation hosts when AI answers crypto questions:
>
> 1. defillama.com   56
> 2. coingecko.com   36
> 3. youtube.com     27
> 4. eco.com         21
> 5. gate.io blog    18
> ...
> 12. coindesk.com   13
>
> @TheBlock__, @decryptmedia, @Cointelegraph — not even in top 30.

(Deliberately spicy. Tags @-handles for visibility. Will get crypto journalism people angry-replying.)

---

## Tweet 4 — Curiosity / model personalities

> each AI has a totally different "personality" answering crypto questions:
>
> · perplexity → conservative, TVL-anchored (Lido / KuCoin / Nexo)
> · gpt-4o → median, balanced across categories
> · grok → crypto-twitter pilled (Monad 31, 1inch heavy)
> · gemini → scattered, pushes obscure tools (DexTools 72× when no other AI mentions it once)
>
> what they pick says more about the model than the protocol.

(Reframes the data into a usable narrative for non-data Twitter. People love personality charts.)

---

## Tweet 5 — CTA + transparency

> this is a hobby project tracking how AI search recommends crypto.
>
> · open source: github.com/HiRussell/web3-ai-visibility
> · runs daily at 04:00 UTC
> · 50 queries × 4 AI models via @OpenRouterAI
> · raw data committed to the repo every day
>
> if your protocol is mis-categorized or missing, reply 👇

(Closes thread. Transparency = trust. Invites engagement that grows the dataset.)

---

## Order suggestion

If posting as a single thread: 1 → 2 → 4 → 3 → 5 (lead with hook, then data, then narrative, then provocation, then CTA).

If posting as standalone tweets over a few days: start with **Tweet 3** alone as a one-shot. It's the most retweet-bait and pulls people to the repo for the rest.

---

## Pre-post checklist

- [ ] Verify GitHub repo is public (currently private — `gh repo edit --visibility public`)
- [ ] Add a screenshot of `frontend/public/index.html` rendered (open locally, screenshot the leaderboard table)
- [ ] If posting tweet 3, decide whether to actually @-mention the journalism handles or leave them off
- [ ] Once posted, monitor for: (a) protocol founders complaining their protocol got "wrong" data — useful signal; (b) journalists pushing back — also useful signal
