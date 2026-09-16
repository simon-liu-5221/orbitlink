# AD-02：檢視回饋與評價

**Status**: done
**Actor**: Admin
**相關 spec**: PR-12（使用者提交回饋）、AD-01（同一組 `require_admin` 檢查）

## 目的

管理員要看到所有使用者提交的產品回饋，了解整體滿意度與具體意見。

## Trigger

管理員進入 `/admin/feedback`。

## Pre-conditions

- 使用者的 `role='admin'`

## Normal Flow

1. 管理員登入
2. `GET /api/v1/admin/feedback`，回傳所有回饋記錄（評分、意見、送出者的 email 與使用者名稱、送出時間），依時間新到舊排序

## Alternative / Exception Flows

| 情況 | 系統行為 | HTTP |
|---|---|---|
| 非 admin 呼叫 | 拒絕 | 403 |
| 未登入 | 拒絕 | 401 |
| 沒有任何回饋記錄 | 回空陣列，前端顯示「還沒有人提交回饋」 | 200 |

## Post-conditions

- 無資料庫寫入（純讀取端點）

## Acceptance Criteria

- [x] **AC-1** Given 資料庫有多筆不同使用者的回饋，When `GET /admin/feedback`，Then 回傳全部，且每筆都附上送出者的 email 與使用者名稱 — `test_admin_api.py::test_feedback_inbox_includes_the_submitters_identity`
- [x] **AC-2** Given 多筆回饋，When 回傳，Then 依 `created_at` 新到舊排序 — `test_feedback_inbox_is_newest_first`
- [x] **AC-3** Given 一般使用者呼叫，When GET，Then 回 403 — `test_feedback_inbox_forbidden_for_non_admin`
- [x] **AC-4** Given 未登入，When GET，Then 回 401 — `test_feedback_inbox_requires_a_token`
- [x] **AC-5** Given 沒有任何回饋，When GET，Then 回空陣列（不是錯誤） — `test_empty_feedback_inbox_is_an_empty_list`

## Out of scope

- 標記回饋為「已讀」/「已處理」
- 回覆使用者的回饋
- 依評分篩選、匯出回饋

## 實作備註

- 回應把 `user.email`／`user.username` 攤平進 `AdminFeedbackOut`，不是巢狀物件——這是唯讀的管理端讀取，攤平比前端多一層解析簡單
- 沿用 AD-01 的 `require_admin` 依賴，沒有另外的權限邏輯

## 實作結果（M5 PR #4）

- `GET /api/v1/admin/feedback`（`app/api/routers/admin.py`），沿用 AD-01 的 `require_admin`
- 前端 `src/features/admin/AdminFeedbackPage.tsx`
- 測試：`tests/integration/test_admin_api.py`（AC-1..AC-5，AD-02 部分）+ 前端 `AdminFeedbackPage.test.tsx`
