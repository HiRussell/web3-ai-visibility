# Frontend

Static single-page leaderboard. Reads from `public/snapshots/{run_date}.json`.

## Why vanilla HTML, not Next.js?

For v1, a single `index.html` + Tailwind CDN + vanilla JS is enough — no build step, no
deps, opens with `file://`, deploys anywhere as a static asset. Upgrade to Next.js when:
- We need history navigation across multiple snapshot dates
- We add interactivity (search, filter, drill-down to raw responses)
- We need server-side rendering for SEO

Until then, "如无必要勿增实体" applies.

## View locally

```bash
cd frontend/public
python3 -m http.server 8080
open http://localhost:8080
```

(Direct `file://` open also works in most browsers, but `fetch()` of the JSON file may
be blocked by file:// CORS — easier to just run a local server.)

## Deploy

Two no-build options:

1. **GitHub Pages** — repo Settings → Pages → Source = `main` branch / `frontend/public` folder.
   Requires the repo to be public OR a GitHub Pro subscription.
2. **Vercel** — point project root to `frontend/public`, set framework to "Other (static)".
   Works with private repos.

## Update the latest snapshot

`index.html` has `const LATEST = '2026-05-08'` near the bottom. Bump after each scan, or
generate a `runs.json` index file later for auto-detection.

## Tweet drafts

See `frontend/tweets.md` for ready-to-post copy from the latest snapshot.
