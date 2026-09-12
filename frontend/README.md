# OrbitLink frontend

React 18 + TypeScript + Vite. TanStack Query for server state, Zustand for the
auth session, `react-router-dom` for routing, Tailwind for styling.

```bash
npm install
npm run dev        # http://localhost:5173, proxies /api to the backend
npm run typecheck
npm run test
npm run build
npm run gen:api    # regenerate src/api/schema.d.ts from a running backend
```

## How auth works (M3)

The access token lives **only in memory** (`src/features/auth/store.ts`); the
refresh token is an httpOnly cookie the browser never exposes to JS (backend
decision B1). Because the dev server proxies `/api` and the Render static site
rewrites `/api/*`, every request is same-origin and `credentials: "include"`
just works — no CORS credentials dance.

`src/api/client.ts` is the one place that touches `fetch`:

- attaches `Authorization: Bearer <token>` from the store
- on a `401`, calls `/api/v1/auth/refresh` once (single-flight, so concurrent
  401s share one refresh), adopts the new session, and retries the original
  request
- if the refresh also fails, clears the session and lets the error propagate

On first load, `useSessionBootstrap` tries that same refresh so a page reload
keeps you signed in.

## Layout

```
src/
  api/          client.ts (fetch wrapper), schema.d.ts (generated)
  lib/          password.ts — client mirror of the GU-01 policy
  components/   ui.tsx (Button/TextField/…), AppShell.tsx
  features/
    auth/       store, api, session, RequireAuth, and the 5 auth pages
    projects/   api, ProjectsPage, ProjectDetailPage, JobProgress,
                AnalysisResultPage, jobStatus.ts (ADR-0002 stage labels)
    graph/      NetworkGraph (Cytoscape), NodeDetailPanel, GraphControls,
                graphData.ts — pure sampling/filtering/color/size (PR-10)
    health/     the M0 status widget, now at /status
  test/         utils.tsx — renderWithProviders, jsonResponse
```

## The network graph (PR-10)

`AnalysisResultPage` lazy-loads `NetworkGraphSection` (Cytoscape is heavy —
PERF-05 wants a fast initial LCP, so it's a separate chunk fetched only when
someone opens a result page). Everything with real logic lives in
`graphData.ts` as plain functions with no DOM or Cytoscape dependency, so it's
unit-tested without a canvas:

- `sampleTopByPagerank` — past 2,000 nodes, keep only the top-PageRank ones and
  the edges between them (CAP-03)
- `filterGraph` — the min-degree / community / sentiment-range filters
- `communityColor` / `nodeRadius` — the color and size encodings

`NetworkGraph.tsx` itself is a thin Cytoscape wrapper; its test mocks
`cytoscape` entirely (jsdom has no canvas) and checks the wiring — the right
elements go in, a tap reaches the callback — while the actual rendering only
gets exercised by hand in a real browser.

## Routes

| path | guard | purpose |
|---|---|---|
| `/login` `/register` | redirect home if signed in | GU-01 / PR-02 |
| `/verify` `/forgot-password` `/reset-password` | public | GU-01 / PR-03 |
| `/status` | public | backend health (M0) |
| `/` | require auth | project list + search + create |
| `/projects/:projectId` | require auth | rename, delete, start analysis, job progress |
| `/analyses/:analysisId` | require auth | result summary + interactive network graph (PR-10) |
