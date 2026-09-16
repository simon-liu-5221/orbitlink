# AD-01：使用者管理（檢視 / 搜尋 / 停權）

**Status**: done
**Actor**: Admin
**相關 spec**: GU-01/PR-02（沿用同一套 JWT auth，只加一個角色檢查）

## 目的

管理員需要看到有哪些使用者、搜尋特定帳號、在濫用發生時停止某人使用系統。

## Trigger

管理員登入後進入 `/admin/users`。

## Pre-conditions

- 使用者的 `role='admin'`（沒有任何自助升級路徑——見實作備註）

## Normal Flow

1. 管理員登入（跟一般使用者用同一套登入頁與 JWT，沒有獨立的管理員登入系統）
2. `GET /api/v1/admin/users?q=`，回傳使用者清單（email、使用者名稱、角色、方案、是否已驗證、停權時間、註冊時間）
3. 管理員點某個使用者的「停權」，`POST /api/v1/admin/users/{id}/suspend`
4. 該使用者立即無法登入；若當下已經登入，下一次任何 API 呼叫都會被拒絕（不等現有 access token 過期）
5. 管理員點「解除停權」，`POST /api/v1/admin/users/{id}/unsuspend`，帳號恢復正常

## Alternative / Exception Flows

| 情況 | 系統行為 | HTTP |
|---|---|---|
| 非 admin 呼叫任何 `/admin/*` 端點 | 拒絕 | 403 |
| 管理員嘗試停權自己 | 拒絕，避免自我鎖死 | 409 |
| 管理員嘗試停權另一個 admin | 拒絕 | 409 |
| 停權不存在的使用者 id | 拒絕 | 404 |
| 停權已經被停權的帳號 | 幂等，回 200 | 200 |
| 解除停權未被停權的帳號 | 幂等，回 200 | 200 |
| 已停權帳號嘗試登入 | 拒絕，`error_code=ACCOUNT_SUSPENDED` | 403 |
| 已停權帳號用尚未過期的 access token 呼叫任何端點 | 拒絕，同上 | 403 |
| 未登入呼叫 `/admin/*` | 拒絕 | 401 |

## Post-conditions

- 停權：`users.suspended_at` 設為現在
- 解除停權：`users.suspended_at` 清為 null
- 不影響使用者既有的專案、分析結果、回饋記錄——停權是「不能用」不是「刪除」

## Acceptance Criteria

- [x] **AC-1** Given 管理員，When `GET /admin/users`，Then 回傳所有使用者（不只自己的資料） — `test_admin_api.py::test_admin_sees_every_user_not_just_themselves`
- [x] **AC-2** Given 搜尋關鍵字，When `GET /admin/users?q=xxx`，Then 只回 email 或使用者名稱符合的使用者 — `test_search_matches_email_or_username`
- [x] **AC-3** Given 一個一般使用者呼叫任何 `/admin/*` 端點，When 呼叫，Then 回 403 — `test_a_regular_user_gets_403_on_every_admin_endpoint`
- [x] **AC-4** Given 未登入，When 呼叫任何 `/admin/*` 端點，Then 回 401 — `test_unauthenticated_gets_401`
- [x] **AC-5** Given 管理員停權一個一般使用者，When POST suspend，Then 回 200 且 `suspended_at` 非 null — `test_suspending_a_user_sets_suspended_at`
- [x] **AC-6** Given 已停權的帳號，When 該使用者嘗試登入，Then 回 403 `error_code=ACCOUNT_SUSPENDED` — `test_suspended_account_cannot_log_in`
- [x] **AC-7** Given 使用者在被停權前已登入（持有有效 access token），When 停權後用該 token 呼叫任何端點，Then 回 403（不必等 token 過期） — `test_an_already_issued_token_dies_immediately_on_suspension`
- [x] **AC-8** Given 管理員嘗試停權自己，When POST，Then 回 409 — `test_admin_cannot_suspend_themselves`
- [x] **AC-9** Given 管理員嘗試停權另一個管理員，When POST，Then 回 409 — `test_admin_cannot_suspend_another_admin`
- [x] **AC-10** Given 已停權帳號，When POST unsuspend，Then 回 200 且 `suspended_at` 為 null，該帳號可以重新登入 — `test_unsuspend_restores_the_account`
- [x] **AC-11** Given 停權/解除停權操作重複呼叫，When 第二次呼叫同一動作，Then 仍回 200（幂等） — `test_suspend_and_unsuspend_are_idempotent`

## Out of scope

- 刪除使用者帳號（停權已經足夠應付濫用，刪除是更大的決定，超出這個 spec）
- 自助申請成為管理員、邀請其他管理員的 UI（見實作備註）
- 使用者角色以外的權限細分（沒有「客服」「唯讀管理員」等中間角色）
- 停權原因記錄 / 通知信

## 實作備註

- **沒有獨立的管理員認證系統**：管理員用跟一般使用者完全相同的 `POST /auth/login`、同一組 JWT。差別只在 `users.role` 欄位與一個新的 `require_admin` FastAPI 依賴（包在既有的 `current_user` 之上）。這個決定是為了不要把認證邏輯複製兩份
- **升級成 admin 沒有 API、沒有 UI 按鈕**：只能用 `scripts/promote_admin.py <email>` 手動跑，或直接改資料庫。這是刻意的：一個能自我提權的系統就不是真的權限控制
- 停權檢查放在兩個地方：`auth_service.login`（擋住新的登入）與 `current_user` 依賴（擋住已存在的 token）——只做前者的話，已登入的使用者要等最多 15 分鐘（access token 存活時間）才會真的被踢出，不夠即時

## 實作結果（M5 PR #4）

- 遷移 `0006_admin_role` 新增 `users.role`（預設 `"user"`）與 `users.suspended_at`
- `require_admin` 依賴（`app/api/deps.py`），包在既有的 `current_user` 之上
- `GET /api/v1/admin/users?q=`、`POST /api/v1/admin/users/{id}/suspend`、`.../unsuspend`（`app/api/routers/admin.py`）
- `scripts/promote_admin.py <email>`——手動升級成 admin 的唯一入口
- 前端 `src/features/admin/AdminUsersPage.tsx`，`RequireAdmin` 路由守衛（`src/features/auth/RequireAuth.tsx`）
- 測試：`tests/integration/test_admin_api.py`（AC-1..AC-11）+ 前端 `AdminUsersPage.test.tsx` / `RequireAdmin.test.tsx`
