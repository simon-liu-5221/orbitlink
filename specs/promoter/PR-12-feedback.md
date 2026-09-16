# PR-12：提交回饋與評分

**Status**: done
**Actor**: Promoter
**相關 spec**: AD-02（管理端檢視回饋，之後的 PR）

## 目的

使用者對 OrbitLink 這個產品本身（不是某一次分析結果）給星等評分與意見，讓開發者知道哪裡該改進。

## Trigger

使用者在應用程式的任何頁面點擊「Feedback」。

## Pre-conditions

- 使用者已登入

## Normal Flow

1. 使用者從導覽列點「Feedback」，開啟回饋表單（彈窗）
2. 選 1–5 星評分，選填一段文字意見
3. 送出，`POST /api/v1/feedback`
4. 後端寫入一筆記錄（`user_id`、`rating`、`comment`、`created_at`），回 `201`
5. 前端顯示感謝訊息並關閉表單

## Alternative / Exception Flows

| 情況 | 系統行為 | HTTP |
|---|---|---|
| 未選星等就送出 | 前端擋下，不送出請求（送出鍵停用） | — |
| 評分不在 1–5 範圍 | 拒絕 | 422 |
| 意見文字超過長度上限（2000 字） | 拒絕 | 422 |
| 未登入 | 拒絕 | 401 |
| 一小時內同一 IP 第 11 次送出 | 限流 | 429 |
| 同一使用者送出多次 | 都接受，各自一筆記錄（不是「更新」而是累積歷史） | 201 |

## Post-conditions

- `feedback` 表新增一筆記錄，`user_id` 為送出者、`comment` 可為 null

## Acceptance Criteria

- [x] **AC-1** Given 合法評分（1–5）與可選意見，When POST，Then 回 201 且資料庫新增一筆記錄，`user_id` 為呼叫者 — `test_feedback_api.py::test_valid_feedback_is_stored_against_the_caller`
- [x] **AC-2** Given 只給評分不給意見，When POST，Then 回 201，`comment` 為 null — `test_comment_is_optional`
- [x] **AC-3** Given 評分為 0 或 6，When POST，Then 回 422 — `test_rating_out_of_range_is_422`（0/6/-1 參數化）
- [x] **AC-4** Given 完全沒給評分欄位，When POST，Then 回 422（評分必填，意見選填） — `test_missing_rating_is_422`
- [x] **AC-5** Given 意見文字超過 2000 字，When POST，Then 回 422 — `test_comment_over_length_limit_is_422`
- [x] **AC-6** Given 沒有 access token，When POST，Then 回 401 — `test_requires_a_token`
- [x] **AC-7** Given 同一使用者連續送出兩次回饋，When 都合法，Then 兩筆都成功寫入（不是覆蓋，是各自的歷史記錄） — `test_the_same_user_can_submit_more_than_once`
- [x] **AC-8** Given 一小時內同一 IP 第 11 次送出，When POST，Then 回 429 — `test_rate_limit_refuses_the_eleventh`
- [x] **AC-9** Given 前端表單尚未選星等，When 檢視送出鍵，Then 停用 — `FeedbackModal.test.tsx::submit is disabled until a star is picked`
- [x] **AC-10** Given 送出成功，When 前端收到回應，Then 顯示感謝訊息且表單重置 — `FeedbackModal.test.tsx::shows a thank-you message and lets the user send another`

## Out of scope

- 使用者檢視自己過去提交的回饋（沒有這個需求，管理端才需要看全部——AD-02）
- 回饋分類 / 標籤（bug report vs 建議）
- 對單一分析結果的評分（不同語意，這裡是產品整體回饋）
- 管理端檢視回饋（AD-02，下一個 PR）
- 匿名（未登入）回饋

## 實作備註

- 一個新表 `feedback`：`id`、`user_id`（FK CASCADE）、`rating`（1–5）、`comment`（nullable, ≤2000 字）、`created_at`。不做「使用者一次只能有一筆」的唯一限制，累積歷史對後續做趨勢分析更有用
- 限流沿用 `app/api/deps.py` 既有的 `rate_limiter` 工廠，10/hr/IP 是為了擋濫用，不是為了限制正常使用（一般人不會一小時交十次意見）
- 前端表單是個彈窗，從 `AppShell`（每頁都有的導覽列）觸發，符合「任何頁面都能提交」

## 實作結果（M5 PR #2）

- 遷移 `0005_feedback` 新增 `feedback` 表
- `POST /api/v1/feedback`（`app/api/routers/feedback.py`），schema `FeedbackCreate`/`FeedbackOut`
- 前端 `src/features/feedback/`：`FeedbackModal.tsx`、`api.ts`，掛在 `AppShell` 的導覽列
- 測試：`tests/integration/test_feedback_api.py`（AC-1..AC-8）+ 前端表單測試（AC-9/AC-10）
