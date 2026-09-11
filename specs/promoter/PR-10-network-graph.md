# PR-10：檢視網路圖

**Status**: done
**Actor**: Promoter
**相關 ADR**: ADR-0002（分析流程）
**相關 NFR**: PERF-04（2,000 節點 ≥ 30fps）、CAP-03（> 2,000 節點自動降級）

## 目的

使用者在分析完成後，用互動式網路圖直觀看出誰在對話、誰是核心人物、社群怎麼分佈——這是 demo 第一眼看到的東西。

## Trigger

使用者從專案詳情頁的已完成分析點進結果頁。

## Pre-conditions

- 分析已完成（`analyses` 有對應記錄）
- 該分析屬於目前使用者的專案

## Normal Flow

1. 前端 `GET /api/v1/analyses/{id}/graph` 取得完整節點與邊列表（不像 `GET /analyses/{id}` 只回 top 20）
2. Cytoscape.js 以力導向佈局（`cose`）呈現網路圖：節點大小依 PageRank、顏色依所屬社群
3. 使用者點擊節點，側欄顯示該節點的暱稱、社群、參與度、平均情緒、留言數、按讚數
4. 使用者用篩選器縮小範圍：最小 degree、社群（複選）、情緒區間
5. 若節點數 > 2,000，前端只保留 PageRank 最高的 2,000 個節點（及其之間的邊）以維持流暢度，並顯示「顯示前 2,000 / 共 N 位參與者」提示

## Alternative / Exception Flows

| 情況 | 系統行為 | HTTP |
|---|---|---|
| 分析不存在或不是本人的 | 回應與另一情況完全相同，不透露存在與否（沿用既有 `GET /analyses/{id}` 慣例） | 404 |
| 未認證 | 拒絕 | 401 |
| 節點數為 0（`insufficient_data`） | 圖表區顯示「資料不足以建立網路圖」，不嘗試渲染空畫布 | 200，空陣列 |
| 節點數 > 2,000 | 前端降級為只顯示 PageRank 前 2,000 名（CAP-03） | 200，完整資料；前端自行取樣 |
| 篩選後沒有節點符合 | 顯示「沒有符合篩選條件的節點」，不是空白畫布 | — |

## Post-conditions

- 無資料庫寫入（純讀取端點）；圖的邊資料在**分析當下**已經寫入 `analyses.graph_edges`（見實作備註）

## Acceptance Criteria

- [x] **AC-1** Given 一個完成的分析（節點數 > 20），When `GET /analyses/{id}/graph`，Then 回傳的節點數等於該分析的 `node_count`（不是只有 top 20） — `test_analysis_graph_api.py::test_graph_returns_every_node_not_just_top_twenty`
- [x] **AC-2** Given 分析當下建立的互動圖有邊 `A->B weight=3`，When `GET /analyses/{id}/graph`，Then 回傳的 edges 包含該筆且 weight 一致（邊在分析時就序列化好，查詢時零重算） — `test_graph_edges_come_from_the_persisted_snapshot` + `tests/unit/jobs/test_serialize_edges.py`
- [x] **AC-3** Given 不存在的 analysis id 與別人專案下的 analysis id，When GET graph 端點，Then 兩者回應（狀態碼與 body）完全相同 — `test_missing_and_other_users_analysis_answer_identically`
- [x] **AC-4** Given 沒有 access token，When GET graph 端點，Then 回 401 — `test_graph_requires_a_token`
- [x] **AC-5** Given 一個 ≤ 2,000 節點的圖，When 前端渲染，Then 每個節點與邊都畫出來，不做取樣 — `graphData.test.ts::a graph at or under the cap is returned untouched`
- [x] **AC-6** Given 一個 > 2,000 節點的圖，When 前端渲染，Then 只保留 PageRank 前 2,000 名節點與其間的邊，並顯示「顯示前 2,000 / 共 N 位」提示（CAP-03） — `graphData.test.ts::a graph over the cap keeps only the top-N by pagerank...`
- [x] **AC-7** Given 多個社群，When 渲染，Then 同一 `community_index` 的節點顏色一致、不同社群顏色不同（同一組資料多次渲染顏色穩定，不隨機跳動） — `graphData.test.ts::the same community always gets the same color across calls` + `...different colors...`
- [x] **AC-8** Given 不同 PageRank 的節點，When 渲染，Then 節點大小隨 PageRank 遞增（純函式，可離線測試不需真的畫布） — `graphData.test.ts::higher pagerank means a larger radius`
- [x] **AC-9** Given 使用者點擊一個節點，When 點擊，Then 側欄顯示該節點暱稱、社群、參與度、平均情緒、留言數、按讚數 — `NodeDetailPanel.test.tsx` + `NetworkGraph.test.tsx::a tap on a node calls onSelectNode...`
- [x] **AC-10** Given 設定最小 degree 為 N，When 套用，Then 只有 degree ≥ N 的節點留下（純函式） — `graphData.test.ts::min degree excludes low-connection nodes`
- [x] **AC-11** Given 取消勾選某個社群，When 套用，Then 該社群節點被過濾掉（純函式） — `graphData.test.ts::excluded communities are filtered out...`
- [x] **AC-12** Given 設定情緒區間，When 套用，Then 只有 `avg_sentiment` 落在區間內的節點留下；`avg_sentiment=null` 的節點在區間為預設全範圍時仍顯示，區間縮小後排除（純函式） — `graphData.test.ts::a sentiment range excludes out-of-range AND null-sentiment nodes` + `...still show when...untouched`

## Out of scope

- 匯出圖形（PR-11，M5）
- 圖形版面配置的使用者自訂（拖曳後儲存位置）
- 舊資料回填：這個 PR 上線前完成的分析 `graph_edges` 是空陣列，圖上只會看到節點、沒有邊。可接受，因為 M2/M3 期間的分析都是測試資料
- 大於 2,000 節點時的伺服器端取樣（決定：先做前端取樣，見實作備註）
- 分析結果的圖表（情緒分布 / 時間走勢 / 參與度散點圖）——另一個 PR

## 實作備註

- **邊的資料在分析當下就持久化**：`app/services/analysis_service.py::_persist` 已經有建好的 `networkx.DiGraph`（`graph`），直接把 `graph.edges(data=True)` 序列化成 `[{source, target, weight}]` 存進新欄位 `analyses.graph_edges`（JSONB）。不建新表、不在查詢時重新跑 `build_interaction_graph`——這個選擇是因為邊資料本來就是分析當下的副產品，序列化幾乎零成本；相對地一個新的 relational edges table 需要遷移且會跟 `comments` 表的 `parent_author_pseudonym` 邏輯重複
- **新端點獨立於既有的 `GET /analyses/{id}`**：後者是「摘要」（top 20 影響者/參與者 + 社群統計），前者是「完整圖」，兩者用途不同、payload 大小差很多，分開才不會讓平常看摘要也要背負整個圖的重量
- **CAP-03 在前端做**：`nfr.md` 原本就把 CAP-03 的驗證方式寫成「前端單元測試」。後端端點回傳完整資料，前端取樣函式必須是純函式（吃 nodes/edges 陣列，吐取樣後的陣列），這樣不需要畫布就能測
- Cytoscape 佈局用內建 `cose`，不額外裝佈局套件（`cytoscape-cola`/`cytoscape-fcose` 之後效能不夠再考慮）
- 顏色穩定的做法：社群顏色 = 調色盤依 `community_index % palette.length` 索引，不是隨機生成

## 實作結果（M4 PR #1）

- 遷移新增 `analyses.graph_edges` JSONB 欄位；`_persist` 一併寫入
- `GET /api/v1/analyses/{id}/graph` 回傳 `{nodes, edges, node_count, edge_count}`，`nodes` 依 pagerank 遞減排序
- 前端 `src/features/graph/` — `sampleTopByPagerank`、`filterGraph`（純函式，AC-5/6/10/11/12 對應）、`communityColor`、`nodeRadius`（AC-7/8）、`NetworkGraph.tsx`（Cytoscape 包裝 + 側欄）
