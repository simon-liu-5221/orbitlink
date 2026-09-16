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
    charts/     SentimentDistributionChart, SentimentTrendChart,
                EngagementScatterChart (Recharts), sentimentSummary.ts /
                engagementScatter.ts — pure parsing/chart-data prep (PR-13)
    export/     csv.ts (pure), downloadFile.ts, pdfReport.ts — PNG/CSV/PDF
                export, all client-side (PR-11)
    feedback/   StarRating, FeedbackModal, api.ts — product feedback,
                reachable from AppShell on every page (PR-12)
    admin/      AdminUsersPage, AdminFeedbackPage, AdminNav, api.ts —
                gated by RequireAdmin (AD-01/AD-02)
    history/    HistorySection, HistoryTrendChart, HistoryComparisonTable,
                ForecastSection, historyData.ts / forecastData.ts — pure
                trend/comparison/forecast-view builders (AN-06)
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

## The result-page charts (PR-13)

`AnalysisChartsSection` also lazy-loads (Recharts is the other heavy dependency).
Unlike the graph, Recharts *can* render in jsdom — `src/test/setup.ts` polyfills
`ResizeObserver` and stubs `getBoundingClientRect` to a fixed non-zero size, since
`ResponsiveContainer` refuses to draw anything at a measured 0x0. That lets the
chart tests assert on real rendered text instead of mocking the library.

Sentiment distribution and the sentiment-over-time trend need no new backend
call at all — both already live in `AnalysisOut.sentiment_summary` (AN-03). The
engagement scatter reuses PR-10's `GET /analyses/{id}/graph` query (same
TanStack Query cache key as the network graph, so opening both costs one fetch).

## History trends (AN-06)

`HistorySection` lives on `ProjectDetailPage` (comparisons are always within one
project — see the spec's out-of-scope list) and lazy-loads for the same
PERF-05 reason as the other Recharts sections. It fetches
`GET /projects/{id}/analyses` (oldest first) and hands the result to three
pure builders in `historyData.ts`:

- `buildSentimentTrend` / `buildParticipantsTrend` both keep `insufficient_data`
  rows — participant counts and the derived sentiment index stay meaningful
  even when the graph itself was too sparse to build.
- `buildCommunityTrend` drops `insufficient_data` rows — a community count from
  too few nodes isn't a real number.
- `hasEnoughHistory` gates the whole section on ≥ 2 analyses; with 0 or 1, the
  UI shows a message instead of a single meaningless point.

### Forecast (AN-06 phase 2)

`ForecastSection` (nested inside `HistorySection`) fetches
`GET /projects/{id}/analyses/forecast` and renders one card per headline
metric via the pure `buildForecastViews` (`forecastData.ts`). The math itself
(linear regression + leave-one-out MAE) lives entirely on the backend in
`app/analysis/forecast.py`, gated independently per metric — a metric with
fewer than 5 usable points shows "need N more analyses" instead of a number,
and the card always carries a fixed disclaimer that this is an extrapolated
trend line, not a machine-learning model (AC-12) — see
`specs/analysis/AN-06-history-trends.md`.

## Export (PR-11)

Everything is client-side — no export endpoint exists on the backend.

- **PNG**: `NetworkGraph` hands its live Cytoscape instance up via `onCyReady`;
  `NetworkGraphSection` calls `cy.png({ output: "blob-promise" })` on it.
- **CSV**: `csv.ts`'s `nodesToCsv` formats whatever node list the caller passes —
  `NetworkGraphSection` passes the currently filtered/sampled list, so the
  export matches what's on screen, not the unfiltered full set.
- **PDF**: `pdfReport.ts`'s `buildPdfReport` walks a list of DOM refs
  (`AnalysisResultPage` holds one per section), screenshots each with
  `html2canvas`, and lays them out one per page with `jsPDF`. Both libraries
  are dynamically imported inside the function — they land in their own build
  chunks and never touch the initial bundle (PERF-05).
- jsPDF is pinned to 4.x, not 2.x — 2.x's `dompurify` dependency carries a
  critical CVE (unrelated to the `.html()` feature this app never calls, but
  `npm audit`/SEC-03 flags it regardless).

## Admin (AD-01 / AD-02)

`RequireAdmin` (in `RequireAuth.tsx`) nests inside `RequireAuth` and checks
`user.role === "admin"` — a non-admin is redirected home and never learns the
route exists. The "Admin" link in `AppShell` is hidden the same way. There's
no self-service path to become an admin anywhere in the UI — see the backend
README's `scripts/promote_admin.py`.

## Routes

| path | guard | purpose |
|---|---|---|
| `/login` `/register` | redirect home if signed in | GU-01 / PR-02 |
| `/verify` `/forgot-password` `/reset-password` | public | GU-01 / PR-03 |
| `/status` | public | backend health (M0) |
| `/` | require auth | project list + search + create |
| `/projects/:projectId` | require auth | rename, delete, start analysis, job progress |
| `/analyses/:analysisId` | require auth | result summary + interactive network graph (PR-10) |
| `/admin/users` | require admin | search, suspend / restore accounts (AD-01) |
| `/admin/feedback` | require admin | every feedback submission (AD-02) |
