# Hirewise frontend

React + TypeScript + Vite dashboard for the automated hiring pipeline. Serves
both recruiters (pipeline, review, decisions) and applicants (track their
applications, browse roles,
apply).

See [DESIGN.md](./DESIGN.md) for the information architecture, design tokens,
component inventory, and the AI-recommendation and accessibility patterns.

## Running

Start the API first, from the repository root:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Then:

```bash
cd Frontend
npm install
npm run dev
```

Open <http://localhost:5173/dashboard/> — the `/dashboard/` base is kept in
dev so paths match production exactly. You will land on a sign-in screen:
use the superadmin set by `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` in the
API's `.env`, or create a candidate account from the second tab. The dev server proxies `/auth`, `/jobs`,
`/applications`, `/interviews`, `/hiring` and `/health` to the API, so everything is same-origin
and no CORS config is needed.

If your API runs on another port:

```bash
VITE_API_TARGET=http://127.0.0.1:8090 npm run dev
```

## Building

```bash
npm run build     # type-checks, then outputs to ../app/static/dashboard
```

FastAPI mounts that directory, so the built app is served at
<http://127.0.0.1:8000/dashboard/> with no separate frontend process.

## Checks

```bash
npm run lint      # eslint, including React 19 hook rules
npx tsc -b        # types only
```

Both are clean as committed.

## Layout

```
src/
├── types.ts          API response types
├── api/client.ts     typed fetch wrapper
├── hooks/useApi.ts   useApi (queries) · useAction (mutations)
├── lib/              format · flags · nav  (non-component helpers)
├── components/       Icon · primitives · AppShell · AiRecommendation
├── pages/            Dashboard · Jobs · Candidates · Review · Interviews · Portal · MyApplications
└── styles.css        the design system — components add no new CSS
```

## Notes

- Navigation is state-driven, not routed, so views are not deep-linkable.
  `DESIGN.md` §1 explains the trade-off and what changing it would involve.
- The candidate interview recorder is **not** in this app; it stays as
  `app/static/interview.html`, served at `/interview?token=…`.
