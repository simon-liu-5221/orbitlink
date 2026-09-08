# AN-05：分析 job 狀態與進度

**Status**: in-progress
**Actor**: System / Promoter（輪詢進度）
**相關 ADR**: ADR-0002

> 實作分佈在 M2 的多個 PR：狀態機（`app/jobs/state_machine.py`）在 `feat/M2-schema`；
> job 執行與心跳在 `feat/M2-analysis-service`；`GET /jobs/{id}` 端點在 `feat/PR-01-api`。

## 目的

使用者送出分析後可以離開頁面，稍後回來看進度；系統需要一個持久、可查詢、可從崩潰恢復的
job 狀態，而不是原 FYP 那個關掉分頁就消失的計時器。

## Trigger

分析 job 被建立（`POST /analyses`，見 PR-01），或 worker 撿起一個 queued job。

## Pre-conditions

- `analysis_jobs` 資料表存在（migration `0002_m2_schema`）

## Normal Flow

1. job 建立時狀態為 `queued`、`progress = 0`
2. worker 撿起後依序推進：`fetching → building_graph → analyzing → persisting → completed`
3. 每次狀態轉移寫入 `status`、`progress`（0–100，單調遞增）、`updated_at`
4. `analyzing` 階段內 worker 可回報子步驟進度（55 → 89）
5. worker 每個檢查點更新 `heartbeat_at`
6. 前端每 2 秒輪詢 `GET /api/v1/jobs/{job_id}`，回傳 `status` + `progress`
7. 進入 `completed` 時 `finished_at` 寫入，`analyses` 表有對應結果

## 狀態機

```
queued ─▶ fetching ─▶ building_graph ─▶ analyzing ─▶ persisting ─▶ completed
   └──────────┴───────────────┴─────────────┴────────────┴─▶ failed
   └──────────┴───────────────┴─────────────┴────────────┴─▶ cancelled
```

- 只能往前推進一步，不能跳步、不能倒退
- 任一非終態可直接轉 `failed`（錯誤）或 `cancelled`（使用者取消）
- 終態（`completed` / `failed` / `cancelled`）沒有任何出口
- `progress_floor`：queued 0 / fetching 10 / building_graph 40 / analyzing 55 / persisting 90 / completed 100
- `failed` / `cancelled` 保留當下的 progress 值

## Alternative / Exception Flows

| 情況 | 系統行為 |
|---|---|
| 非法狀態轉移（跳步 / 倒退 / 從終態出發） | `assert_transition` 拋 `InvalidJobTransitionError`，job 不變動 |
| worker 崩潰 | job 卡在非終態；reaper 檢查 `heartbeat_at`，超過 30 分鐘無心跳 → `failed`、`error_code = WORKER_TIMEOUT` |
| 崩潰後 worker 重啟 | 卡住的 job 被 reaper 標 `failed`，使用者可重試；不自動續跑（M2 範圍） |
| 使用者取消進行中的 job | 標 `cancelled`，worker 在下一個檢查點偵測到並停止 |
| 資料不足（節點 < 3 / 邊 < 2） | 走到 `completed`，但 `analyses.insufficient_data = true`（不是 `failed`） |

## Post-conditions

- `analysis_jobs` 每一筆最終為終態之一
- `completed` 時 `analyses` 及關聯表（`nodes` / `communities` / `comments`）有完整結果
- 進度值全程單調遞增、落在 0–100

## Acceptance Criteria

- [x] **AC-1** Given 任一非終態，When 轉到 pipeline 的下一步，Then `can_transition` 為 true — `test_happy_path_advances_one_step_at_a_time`
- [x] **AC-2** Given 任一非終態，When 嘗試跳步或倒退，Then `can_transition` 為 false — `test_cannot_skip_a_pipeline_step` / `test_cannot_move_backwards`
- [x] **AC-3** Given 任一非終態，When 轉 `failed` 或 `cancelled`，Then 允許 — `test_any_live_status_can_fail_or_cancel`
- [x] **AC-4** Given 任一終態，When 嘗試轉任何狀態，Then 不允許 — `test_terminal_statuses_have_no_exit`
- [x] **AC-5** Given 非法轉移，When `assert_transition`，Then 拋 `InvalidJobTransitionError` — `test_assert_transition_raises_on_illegal_move`
- [x] **AC-6** Given 一連串狀態推進，When 讀 progress，Then 值單調遞增、不超過 100 — `test_clamp_progress_*`
- [x] **AC-7** `analysis_jobs` schema：`status` / `progress` / `heartbeat_at` / `error_code` / timestamps 齊全，時間欄位為 timestamptz — `test_new_job_defaults`
- [ ] **AC-8** Given worker 30 分鐘無心跳，When reaper 執行，Then job 標 `failed` + `error_code = WORKER_TIMEOUT` — （`feat/M2-analysis-service`）
- [ ] **AC-9** Given 進行中的 job，When `GET /jobs/{id}`，Then 回傳合法 status + 0–100 整數 progress — （`feat/PR-01-api`，對應 PR-01 AC-7）

## Out of scope

- 崩潰後自動續跑 job（M2 只做「標 failed，讓使用者重試」）
- 即時推播進度（用輪詢，不用 WebSocket / SSE）
- 多 worker 搶同一個 job 的分散式鎖（單 worker，RQ 自身的 registry 已足夠）

## 實作備註

- 狀態機是純模組（無 DB / RQ import），service 層在寫 DB 前呼叫 `assert_transition`
- `heartbeat_at` 用 `timestamptz`，reaper 比對 `now() - heartbeat_at > interval '30 min'`
- reaper 用 RQ 的 scheduler 週期執行，或 worker 啟動時掃一次
