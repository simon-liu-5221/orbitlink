# AN-03：情緒分析

**Status**: done（AC-9 除外，延到 M8）
**Actor**: System
**相關 ADR**: ADR-0003, ADR-0004

> 實作：`backend/app/analysis/sentiment.py`（`SentimentAnalyzer(predict_fn=...)`，模型注入式，無 transformers/torch 依賴），測試 `backend/tests/unit/analysis/test_sentiment.py`（19 tests，`app/analysis` 覆蓋率 100%）。branch `feat/AN-03-sentiment`。真實模型封裝在 worker（M2，ADR-0004）。

## 目的

使用者想知道留言區整體的情緒走向、哪些影片或哪些時段情緒轉負、哪些社群的調性跟其他人不同。

## Trigger

分析 job 的 `analyzing` 階段，網路建立完成後。

## Pre-conditions

- 已擷取留言文字
- 情緒模型已載入（worker 啟動時預載，見 ADR-0004）

## Normal Flow

1. 依 `batch_size=32` 切分留言
2. 逐批送入模型，取得 negative / neutral / positive 三類的機率
3. 標籤取 argmax；連續分數定義為 `p_positive - p_negative`，落在 -1 到 1
4. 同批送入毒性模型，取得 0–1 毒性分數
5. 聚合：
   - 整體三類百分比分布
   - 依時間分桶的情緒走勢（桶大小依分析期間自適應：< 7 天用小時，否則用天）
   - 依社群分組的平均情緒
   - 毒性超過 0.7 的留言比例
6. 回傳 `SentimentResult`

## Alternative / Exception Flows

| 情況 | 系統行為 |
|---|---|
| 留言為空字串或只有表情符號 | 跳過推論，標記 `skipped=True`，不計入分布 |
| 單批推論拋出例外 | 重試 2 次；仍失敗則該批標記 `failed`，其餘批次照常，結果中揭露失敗比例 |
| 失敗比例 > 20% | 整個 job 標記 `failed` |
| 留言超過模型最大長度 | 截斷至 512 token，記錄被截斷的比例 |
| 模型未載入 | 拋出明確例外，不靜默降級為隨機值 |

## Post-conditions

- 每則留言的情緒標籤、連續分數、毒性分數寫入資料庫
- 依 `docs/data-ethics.md`，留言原文在此步驟後刪除（除非使用者選擇保留）
- 聚合結果寫入 `analyses.sentiment_summary`

## Acceptance Criteria

- [x] **AC-1** Given 注入一個回傳固定機率的假模型，When 執行分析，Then 批次切分正確且每則留言都有結果 — `test_ac1_batches_split_correctly_and_every_comment_has_a_result`
- [x] **AC-2** Given 100 則留言與 batch_size=32，When 執行，Then 假模型被呼叫 4 次 — `test_ac2_hundred_comments_batch_32_calls_model_four_times`
- [x] **AC-3** Given 一則空字串留言，When 執行，Then 該筆標記 skipped 且不影響整體分布的分母 — `test_ac3_empty_comment_is_skipped_and_excluded_from_distribution`
- [x] **AC-4** Given 假模型在第 2 批連續拋出 3 次例外，When 執行，Then 該批標記 failed 而其餘批次完成，結果 `failed_ratio` 正確 — `test_ac4_failing_batch_is_isolated_and_failed_ratio_is_reported`（500 則 / batch 50，第 2 批失敗 → failed_ratio 0.1）
- [x] **AC-5** Given 失敗比例達 25%，When 執行，Then 拋出 `SentimentAnalysisFailed` — `test_ac5_failure_above_threshold_raises`
- [x] **AC-6** Given 一組已知標籤的留言，When 聚合，Then 三類百分比加總為 100（容差 0.1）— `test_ac6_distribution_percentages_sum_to_100`
- [x] **AC-7** Given 分析期間為 3 天，When 分桶，Then 桶單位為小時；期間為 30 天時為天 — `test_ac7_trend_bucket_is_hourly_under_a_week_daily_over`
- [x] **AC-8** Given 模型未注入，When 執行，Then 拋出明確例外而非回傳預設值 — `test_ac8_missing_model_raises_not_defaults`（`SentimentModelNotLoaded`）
- [ ] **AC-9** 在 500 筆人工標註樣本上，macro F1 ≥ 0.65 且結果記入 `docs/algorithm-validation.md` — **延到 M8**（需要真實人工標註資料，不是假模型）

## Out of scope

- 面向級情緒分析（不判斷「對某個主題」的情緒）
- 反諷偵測
- 情緒的因果解釋
- 即時串流情緒

## 實作備註

- 模型物件由呼叫端注入（`SentimentAnalyzer(predict_fn=...)`），這是讓這個模組可以離線測試的關鍵
- 前端呈現時必須一併顯示 AC-9 的實測 F1，讓使用者知道這不是絕對真值
- 已知弱點要寫進驗證文件：粵語口語、閩南語、大量表情符號、中英夾雜的縮寫
- 毒性分數不用來給使用者貼標籤，只做聚合統計（見 `docs/data-ethics.md`）
