# PR-13：分析結果圖表（情緒分布 / 時間走勢 / 參與度散點圖）

**Status**: done
**Actor**: Promoter
**相關 spec**: AN-03（情緒分析，`sentiment_summary` 的資料來源）、PR-10（`GET /analyses/{id}/graph`，散點圖的資料來源）

## 目的

分析結果頁除了網路圖，還要用圖表回答三個問題：整體情緒怎麼分佈、情緒隨時間怎麼變化、留言量與參與度的關係。

## Trigger

使用者在分析結果頁往下捲動到圖表區。

## Pre-conditions

- 分析已完成
- 該分析屬於目前使用者的專案（沿用結果頁既有的擁有權檢查，這個 PR 不新增任何端點）

## Normal Flow

1. 結果頁載入時已經有 `GET /analyses/{id}` 回傳的 `sentiment_summary`（AN-03 產生，情緒分布與時間走勢都在裡面）——**不需要新的後端呼叫**
2. 情緒分布圖：長條圖顯示 positive / neutral / negative 三類的百分比
3. 情緒時間走勢圖：折線圖顯示 `sentiment_summary.trend` 每個時間桶的平均情緒分數，X 軸依 `trend_bucket`（`hour` 或 `day`）決定顯示格式
4. 參與度散點圖：重用 PR-10 已經在抓的 `GET /analyses/{id}/graph` 節點資料，X 軸為留言數、Y 軸為參與度分數，點的顏色依社群（與網路圖同一套調色盤）
5. 三張圖都沒有資料時（例如 `insufficient_data`），各自顯示「沒有足夠資料」而不是空白圖表

## Alternative / Exception Flows

| 情況 | 系統行為 |
|---|---|
| `sentiment_summary.trend` 為空陣列 | 時間走勢圖顯示「沒有足夠的時間分布資料」 |
| 所有情緒分布都是 0（`insufficient_data` 或情緒分析被跳過） | 分布圖顯示「沒有情緒資料」 |
| 節點數為 0 | 散點圖顯示「沒有參與者資料」（與 PR-10 網路圖的空狀態一致） |
| `sentiment_summary` 缺欄位或型別不符（後端目前是 `dict[str, Any]`，沒有嚴格 schema） | 前端解析函式對缺欄位給預設值，不噴例外 |

## Post-conditions

- 無資料庫寫入、無新端點（純前端消費既有資料）

## Acceptance Criteria

- [x] **AC-1** Given `sentiment_summary.distribution = {positive: 60, neutral: 30, negative: 10}`，When 渲染分布圖，Then 三個類別的數值與順序（positive/neutral/negative）正確、顏色各自不同且穩定 — `sentimentSummary.test.ts::distributionChartData is always positive/neutral/negative in that order` + `SentimentDistributionChart.test.tsx::renders all three category labels`
- [x] **AC-2** Given `distribution` 缺少某個 key，When 解析，Then 該類別當作 0 處理，不拋錯 — `sentimentSummary.test.ts::a missing distribution key defaults to zero...`
- [x] **AC-3** Given `trend_bucket="hour"` 的 trend 資料，When 渲染時間走勢圖，Then X 軸標籤格式含小時；Given `trend_bucket="day"`，Then 標籤格式只到日期 — `sentimentSummary.test.ts::an hour bucket includes the hour in the label` + `...a day bucket produces a different label...`
- [x] **AC-4** Given `trend=[]`，When 渲染，Then 顯示「沒有足夠的時間分布資料」而不是空白圖表 — `sentimentSummary.test.ts::an empty trend parses to an empty array...` + `SentimentTrendChart.test.tsx::shows an empty state...`
- [x] **AC-5** Given PR-10 的節點列表，When 建立散點圖資料，Then 每個點的 x/y 對應留言數/參與度分數，顏色與該節點在網路圖上的社群顏色一致（同一個 `communityColor` 函式） — `engagementScatter.test.ts::maps comment count and engagement score onto x/y` + `...uses the same community palette...`
- [x] **AC-6** Given 節點數為 0，When 渲染散點圖，Then 顯示「沒有參與者資料」 — `engagementScatter.test.ts::an empty node list produces an empty scatter` + `EngagementScatterChart.test.tsx::shows an empty state...`
- [x] **AC-7** Given 分析的 `insufficient_data=true`，When 進入圖表區，Then 三張圖都顯示各自的空狀態，不嘗試渲染 — `AnalysisChartsSection.test.tsx::insufficient_data shows one empty state and renders none of the three charts`

## Out of scope

- 跨分析的歷史趨勢比較（AN-06，M6）
- 圖表匯出成圖片（PR-11，M5）
- 圖表的互動篩選（例如點散點圖高亮對應網路圖節點）——好主意，但不是這個 PR
- 依社群拆分的情緒圖（`sentiment_summary.by_community` 已經有資料，未來可以加，這次先不做）

## 實作備註

- 三張圖都不需要新的後端端點：分布圖與時間走勢圖吃 `AnalysisOut.sentiment_summary`（已經是結果頁在抓的資料），散點圖吃 PR-10 的 `GET /analyses/{id}/graph`（結果頁的網路圖區塊已經抓過一次，這裡直接共用同一個 TanStack Query cache key，不會重複打 API）
- `sentiment_summary` 後端是 `dict[str, Any]`，沒有嚴格型別，前端要寫一個防禦性的解析函式（`parseSentimentSummary`），缺欄位給合理預設值，不能讓一張圖表壞掉拖累整頁
- Recharts 的 `ResponsiveContainer` 在 jsdom 裡需要 `ResizeObserver`，jsdom 沒有內建，測試環境要 polyfill（`src/test/setup.ts`）
- 純資料轉換函式（`distributionChartData`、`trendChartData`、`buildEngagementScatterData`）都不碰 Recharts，方便單元測試；圖表元件本身用真的 Recharts 渲染（不像 Cytoscape 需要 mock），斷言渲染出的文字內容

## 實作結果（M4 PR #2）

- `src/features/charts/sentimentSummary.ts`（解析 + 分布/走勢的純資料轉換）
- `src/features/charts/SentimentDistributionChart.tsx`、`SentimentTrendChart.tsx`、`EngagementScatterChart.tsx`
- 三者都掛在 `AnalysisResultPage`，與網路圖共用 `useQuery(["analyses", id, "graph"])` 快取
- 測試：`sentimentSummary.test.ts` / `engagementScatter.test.ts`（純函式）+ 三個圖表元件與 `AnalysisChartsSection` 的渲染測試（真的 Recharts，斷言文字內容），共 21 個測試
- 測試環境補了 `ResizeObserver` polyfill 與 `getBoundingClientRect` 固定尺寸 stub（`src/test/setup.ts`），否則 Recharts 在 jsdom 量到 0×0 直接不渲染任何內容
