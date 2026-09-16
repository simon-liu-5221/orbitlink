# AN-06：歷史趨勢比較

**Status**: Phase 1 done；Phase 2（外插預測）延到下一個 PR
**Actor**: Promoter
**相關 spec**: PR-13（圖表元件與測試模式沿用）、AN-03（`sentiment_summary` 是情緒指標的來源）

## 目的

原 FYP 的「Predictive Analysis」是最空的一塊——沒有真的模型、沒有驗證數字。這裡重做成誠實版本：同一個專案多次分析之間的比較與趨勢，以及一個**明確標示為外插、附驗證誤差**的簡單預測，而不是假裝有 ML。

這個 spec 分兩個階段：

- **Phase 1（PR #18）**：比較視圖 + 趨勢圖。不需要新的資料庫欄位——`analyses` 表每一列本來就是專案在某個時間點的完整快照，「歷史」只是把同一個 `project_id` 的多筆 `analyses` 依時間排序
- **Phase 2（下一個 PR）**：外插預測 + 留出法 MAE，只在有 ≥5 次歷史分析時啟用

## Trigger

使用者在專案詳情頁點進「歷史趨勢」分頁。

## Pre-conditions

- 該專案至少有一筆已完成的分析

## Normal Flow（Phase 1）

1. `GET /api/v1/projects/{id}/analyses`，回傳該專案所有分析的摘要，依時間**由舊到新**排序（時間序列圖表要的順序，跟 `GET /projects/{id}/jobs`「新到舊」的慣例刻意不同——原因見實作備註）
2. 前端畫三條趨勢線：情緒指標、參與人數（`node_count`）、社群數（`community_count`）
3. 若分析數 < 2，顯示「需要更多歷史分析才能看出趨勢」而不是畫一條沒有意義的單點線
4. 使用者可以在比較表格裡看到每次分析的關鍵數字並排（時間、參與人數、社群數、情緒指標、是否為資料不足的分析）

## Normal Flow（Phase 2，另一個 PR）

5. 當歷史分析數 ≥ 5，額外顯示「預測」區塊：對情緒指標、參與人數、社群數各自用簡單線性迴歸外插下一個時間點
6. 用留出法（leave-one-out 或 leave-last-N-out）算出每個指標的 MAE，顯示在預測旁邊
7. UI 明確標示「這是根據過去數據外插的簡單趨勢線，不是機器學習模型」

## Alternative / Exception Flows

| 情況 | 系統行為 | HTTP |
|---|---|---|
| 專案不存在或不是本人的 | 回應與另一情況完全相同 | 403 |
| 未登入 | 拒絕 | 401 |
| 專案沒有任何完成的分析 | 回空陣列，前端顯示「還沒有分析結果」 | 200 |
| 只有 1 筆分析 | 回該筆，前端顯示「需要更多歷史分析才能看出趨勢」 | 200 |
| 某筆分析 `insufficient_data=true` | 該筆仍列在比較表格裡，但社群數趨勢線跳過它（社群數在資料不足時沒有意義）；參與人數與情緒趨勢仍然使用 | 200 |
| 歷史分析數 < 5（Phase 2） | 不顯示預測區塊，顯示「還需要 N 次分析才能開始預測」 | — |

## Post-conditions

- 無資料庫寫入（純讀取端點）

## Acceptance Criteria

### Phase 1（這個 PR）

- [x] **AC-1** Given 一個專案有 3 筆已完成的分析，When `GET /projects/{id}/analyses`，Then 回傳 3 筆，依 `created_at` 由舊到新排序 — `backend/tests/integration/test_project_history_api.py::test_returned_oldest_first`
- [x] **AC-2** Given 分析的 `sentiment_summary.distribution`，When 計算情緒指標，Then 用 `(positive% - negative%) / 100`（範圍 -1 到 1），不需要重新查詢 comments 或 nodes — `backend/tests/integration/test_project_history_api.py::test_sentiment_index_from_distribution`
- [x] **AC-3** Given 不存在的 project id 與別人的 project id，When 呼叫，Then 兩者回應完全相同（403，沿用既有 `_owned_project`） — `backend/tests/integration/test_project_history_api.py::test_missing_and_other_users_project_answer_identically`
- [x] **AC-4** Given 未登入，When 呼叫，Then 回 401 — `backend/tests/integration/test_project_history_api.py::test_requires_a_token`
- [x] **AC-5** Given 專案沒有任何分析，When 呼叫，Then 回空陣列 — `backend/tests/integration/test_project_history_api.py::test_a_project_with_no_analyses_yet_is_an_empty_list`
- [x] **AC-6** Given 前端收到少於 2 筆分析，When 渲染趨勢圖，Then 顯示「需要更多歷史分析」而不是畫圖（純函式，可離線測試） — `frontend/src/features/history/historyData.test.ts` (`hasEnoughHistory`), `frontend/src/features/history/HistorySection.test.tsx`
- [x] **AC-7** Given 某筆分析 `insufficient_data=true`，When 建立社群數趨勢資料，Then 該筆被排除；When 建立參與人數與情緒趨勢資料，Then 該筆仍包含在內（純函式） — `frontend/src/features/history/historyData.test.ts` (`buildCommunityTrend`, `buildParticipantsTrend`, `buildSentimentTrend`)
- [x] **AC-8** Given 多筆分析，When 建立比較表格資料，Then 每一列包含時間、參與人數、社群數、情緒指標、是否資料不足（純函式） — `frontend/src/features/history/historyData.test.ts` (`buildComparisonRows`), `frontend/src/features/history/HistoryComparisonTable.test.tsx`

### Phase 2（下一個 PR，先列出不做）

- [ ] **AC-9** Given ≥5 筆歷史分析，When 計算外插預測，Then 對每個指標用線性迴歸並回傳下一個時間點的預測值
- [ ] **AC-10** Given 同樣的歷史資料，When 計算 MAE，Then 用留出法（每次留一筆當測試集，其餘訓練，取誤差平均）算出，不是憑空給一個數字
- [ ] **AC-11** Given <5 筆歷史分析，When 檢視預測區塊，Then 顯示「還需要 N 次分析」而不是顯示假預測
- [ ] **AC-12** Given 顯示預測結果，When 使用者看到 UI，Then 有文字明確說明這是外插趨勢線，不是機器學習模型

## Out of scope

- 跨「不同專案」的比較（只比較同一個專案自己的歷史）
- 除了線性迴歸以外更複雜的時間序列模型（ARIMA、Prophet 等）——不符合這個專案「誠實勝過花俏」的定位
- 對已封存專案的特殊處理（封存不影響歷史資料，一樣看得到）
- 匯出歷史趨勢圖（沿用 PR-11 的匯出機制即可，這個 spec 不重做）

## 實作備註

- **為什麼歷史端點是「舊到新」，`jobs` 端點是「新到舊」**：`GET /projects/{id}/jobs` 是給使用者看「最近在幹嘛」，最新的擺最前面才合理；這個端點的唯一用途是畫時間序列圖表，圖表函式庫（Recharts）期待資料本來就照 X 軸順序排好，讓後端排序而不是每次前端都要 `.reverse()`
- **情緒指標是近似值，不是真的算術平均**：`sentiment_summary.distribution` 存的是各類別的百分比（AN-03），`(positive% - negative%) / 100` 跟 AN-03 定義的單則留言分數（`p_positive - p_negative`）用同一套邏輯，但這是「用分布反推」的近似整體分數，不是重新對每則留言的原始分數取平均。這個近似的取捨是為了不必新增查詢——`sentiment_summary` 已經在 `analyses` 表上，不用碰 `comments` 或 `nodes` 表
- 這個端點掛在既有的 `app/api/routers/projects.py`（跟 `list_project_jobs` 放一起），不開新的 router 檔案
