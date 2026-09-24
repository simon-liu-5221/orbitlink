// M7 — CAP-02 / PERF-01 page-load latency under 20 concurrent users, while
// seed.py's 5 "active" jobs simulate CAP-02's concurrent-analysis condition.
//
// Run (from loadtest/, after `uv run python seed.py > seed-data.json` and
// with the API reachable):
//
//   docker run --rm -i --add-host=host.docker.internal:host-gateway \
//     -v "$PWD":/scripts -w /scripts grafana/k6 run pageload.js
//
// BASE_URL defaults to the host's API through Docker Desktop's gateway; pass
// -e BASE_URL=http://localhost:8000 if running k6 natively instead.

import http from "k6/http";
import { check, sleep } from "k6";

const seed = JSON.parse(open("./seed-data.json"));
const BASE_URL = __ENV.BASE_URL || "http://host.docker.internal:8000";

const AUTH_HEADERS = {
  headers: { Authorization: `Bearer ${seed.token}` },
};

export const options = {
  stages: [
    { duration: "20s", target: 20 }, // ramp up to CAP-02's 20 concurrent users
    { duration: "40s", target: 20 }, // hold
    { duration: "10s", target: 0 }, // ramp down
  ],
  thresholds: {
    // PERF-01: page APIs p95 < 300ms, checked per endpoint (tagged by name).
    "http_req_duration{name:list_projects}": ["p(95)<300"],
    "http_req_duration{name:get_project}": ["p(95)<300"],
    "http_req_duration{name:list_jobs}": ["p(95)<300"],
    "http_req_duration{name:history}": ["p(95)<300"],
    "http_req_duration{name:forecast}": ["p(95)<300"],
    "http_req_duration{name:get_analysis}": ["p(95)<300"],
    http_req_failed: ["rate<0.01"],
  },
};

function get(name, path) {
  const res = http.get(`${BASE_URL}${path}`, {
    ...AUTH_HEADERS,
    tags: { name },
  });
  check(res, { [`${name}: status 200`]: (r) => r.status === 200 });
  return res;
}

export default function () {
  get("list_projects", "/api/v1/projects");
  get("get_project", `/api/v1/projects/${seed.primary_project_id}`);
  get("list_jobs", `/api/v1/projects/${seed.primary_project_id}/jobs`);
  get("history", `/api/v1/projects/${seed.primary_project_id}/analyses`);
  get(
    "forecast",
    `/api/v1/projects/${seed.primary_project_id}/analyses/forecast`,
  );
  get("get_analysis", `/api/v1/analyses/${seed.analysis_id}`);
  sleep(1);
}
