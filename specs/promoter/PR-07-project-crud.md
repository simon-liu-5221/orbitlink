# PR-07：專案 CRUD（建立 / 重新命名 / 開啟 / 封存 / 刪除）

**Status**: done
**Actor**: Promoter
**相關 ADR**: —
**相關 NFR**: SEC-02（使用者 A 無法讀取使用者 B 的任何專案資源）

## 目的

使用者管理自己的分析專案：建立、改名、封存（收起但可還原）、永久刪除，並在專案清單中搜尋。

## Trigger

使用者在專案清單頁操作某個專案，或建立新專案。

## Pre-conditions

- 使用者已登入
- 操作既有專案時，該專案屬於該使用者

## Normal Flow

1. 使用者建立專案：`POST /api/v1/projects` `{name}` → `201`
2. 使用者檢視清單：`GET /api/v1/projects`，預設只回未封存的，依建立時間新到舊
3. 使用者用關鍵字搜尋：`GET /api/v1/projects?q=xxx`，對名稱做大小寫不敏感的子字串比對
4. 使用者要看封存的：`GET /api/v1/projects?include_archived=true`
5. 使用者開啟專案：`GET /api/v1/projects/{id}`；該專案的分析 job 歷史由 `GET /api/v1/projects/{id}/jobs` 取得（前端專案詳情頁的分析清單）
6. 使用者改名：`PATCH /api/v1/projects/{id}` `{name}` → `200`，回更新後的專案
7. 使用者封存：`POST /api/v1/projects/{id}/archive` → `200`，`archived_at` 設為現在，之後不出現在預設清單
8. 使用者還原：`POST /api/v1/projects/{id}/unarchive` → `200`，`archived_at` 清為 null
9. 使用者永久刪除：`DELETE /api/v1/projects/{id}` → `204`，專案與其所有 job / analysis / node / community / comment 一併刪除

## Alternative / Exception Flows

| 情況 | 系統行為 | HTTP |
|---|---|---|
| 名稱為空或只有空白 | 拒絕（前後空白會先被去除再驗證） | 422 |
| 名稱超過 200 字 | 拒絕 | 422 |
| 操作不存在的專案 | 回應與「非本人專案」完全相同，不透露是否存在 | 403 |
| 操作其他使用者的專案（任何端點） | 拒絕，不透露是否存在 | 403 |
| 刪除仍有進行中 job 的專案 | 拒絕，提示先等待或取消 | 409 `PROJECT_BUSY` |
| 封存已封存的專案 | 幂等，回 200，`archived_at` 不變 | 200 |
| 還原未封存的專案 | 幂等，回 200 | 200 |
| 對已封存專案改名 | 允許 | 200 |
| 未認證 | 回 401 | 401 |

## Post-conditions

- 建立：`projects` 新增一筆，`user_id` 為當前使用者，`archived_at` 為 null
- 改名：`projects.name` 更新，`updated_at` 由 `onupdate` 自動刷新
- 封存 / 還原：只改 `archived_at`，不動其他欄位、不影響既有分析結果
- 刪除：`projects` 該列消失，關聯資料靠 `ondelete=CASCADE` / `cascade="all, delete-orphan"` 一併清除

## Acceptance Criteria

- [x] **AC-1** Given 合法名稱，When POST，Then 回 201、body 含 id 與 `archived_at=null`，且資料庫該列 `user_id` 為當前使用者 — `test_project_crud_api.py::test_create_returns_201_and_belongs_to_the_caller`
- [x] **AC-2** Given 名稱為 `"   "`，When POST 或 PATCH，Then 回 422 — `test_bad_names_are_422`（參數化：空字串 / 純空白 / 純 tab-newline / 201 字）+ `test_create_strips_surrounding_whitespace`
- [x] **AC-3** Given 三個專案其中一個名稱含 "climate"，When `GET /projects?q=CLIMATE`，Then 只回那一個（大小寫不敏感、子字串比對） — `test_search_is_case_insensitive_substring` + `test_search_escapes_like_wildcards`（`%` 當字面處理）
- [x] **AC-4** Given 一個已封存與兩個未封存的專案，When `GET /projects`，Then 只回兩個未封存的；When `GET /projects?include_archived=true`，Then 三個都回 — `test_default_list_hides_archived`
- [x] **AC-5** Given 自己的專案，When `PATCH {name:"新名字"}`，Then 回 200、body.name 為新名字，且重新查詢確認已持久化 — `test_rename_persists`
- [x] **AC-6** Given 自己未封存的專案，When POST archive，Then 回 200、`archived_at` 非 null 且不再出現在預設清單；When 再 POST archive，Then 仍回 200 且 `archived_at` 不變（幂等） — `test_archive_is_idempotent`
- [x] **AC-7** Given 自己已封存的專案，When POST unarchive，Then 回 200、`archived_at` 為 null 且重新出現在預設清單 — `test_unarchive_restores_to_the_default_list` + `test_unarchive_an_active_project_is_idempotent`
- [x] **AC-8** Given 自己的專案且其下有一個 completed 的 analysis，When DELETE，Then 回 204，且該 project / job / analysis / node / community / comment 在資料庫中都不存在 — `test_delete_cascades_to_all_analysis_data`
- [x] **AC-9** Given 自己的專案且其下有一個進行中的 job，When DELETE，Then 回 409 `error_code=PROJECT_BUSY`，專案仍在 — `test_delete_refuses_a_project_with_a_live_job`
- [x] **AC-10** Given 使用者 B，When 對使用者 A 的專案呼叫 `GET {id}` / `PATCH {id}` / `POST {id}/archive` / `POST {id}/unarchive` / `DELETE {id}` / `GET {id}/jobs` / `POST {id}/analyses`，Then 每一個都回 403（SEC-02） — `test_another_users_project_is_403_on_every_endpoint`（參數化，7 個端點）
- [x] **AC-11** Given 一個不存在的 project id，When 對上述任一端點操作，Then 回應（狀態碼與 body）與 AC-10 的「非本人專案」完全相同 — `test_missing_project_is_indistinguishable_from_not_yours`（參數化，狀態碼與 body 逐一比對）
- [x] **AC-12** Given 沒有 access token，When 對任一專案端點操作，Then 回 401 — `test_every_endpoint_needs_a_token`（參數化，7 個端點）
- [x] **AC-13** Given 自己的專案有兩個 job，When `GET /projects/{id}/jobs`，Then 回兩筆、依建立時間新到舊、每筆含 status 與 progress — `test_project_jobs_lists_newest_first`

## Out of scope

- 專案分享 / 協作（多人一個專案）
- 專案範本、複製專案
- 復原已刪除的專案（刪除即永久；要保留就用封存）
- 專案標籤 / 分類 / 排序偏好（搜尋只做名稱關鍵字）
- 專案備註（PR-09）
- 批次操作（一次封存多個）

## 實作備註

- 所有端點共用一個 `_owned_project(db, project_id, user)` helper：查不到或不是本人一律 `raise HTTPException(403, ...)`，訊息不分兩種情況（SEC-02 / AC-11）
- 刪除的 busy 檢查沿用 PR-01 的判斷：`AnalysisJob.status NOT IN TERMINAL`
- 搜尋用 Postgres `ILIKE`，`q` 兩側自動加 `%`；`q` 內的 `%` `_` 需 escape 以免使用者輸入被當萬用字元
- `ProjectOut` 加上 `archived_at` 欄位供前端顯示狀態；名稱驗證抽成 `ProjectName` 型別（`strip_whitespace=True`）給 create 與 rename 共用
- `GET /projects/{id}/jobs` 回 `list[JobStatusOut]`（沿用 analyses router 既有的 schema），給前端專案詳情頁的分析清單用
- 封存 / 還原用 `POST .../archive` 與 `POST .../unarchive` 而非 `PATCH {archived: bool}`，語意較清楚且天然幂等

## 實作結果（M3 PR #3）

- `app/api/routers/projects.py` 擴充：`PATCH`、`archive`、`unarchive`、`DELETE`、`{id}/jobs`，list 加 `q` 與 `include_archived`
- schema `ProjectName`（共用）、`ProjectRename`、`ProjectOut` 加 `archived_at`
- 測試 `tests/integration/test_project_crud_api.py`，AC-1..AC-13 逐條對應，含一支參數化的 SEC-02 測試掃過每個端點
