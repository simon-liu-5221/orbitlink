# AN-04：影響者辨識

**Status**: done
**Actor**: System
**相關 ADR**: ADR-0003

> 實作：`backend/app/analysis/influence.py`（`rank_influencers`），測試
> `backend/tests/unit/analysis/test_influence.py`。branch `feat/M2-analysis-service`。
> 決定 F1：併進 M2，不獨立開 branch。

## 目的

使用者想知道留言區裡誰是真正的中心節點——不是留言最多的人，而是把討論串在一起、
資訊經過他們流動的人。

## Trigger

分析 job 的 `analyzing` 階段，互動網路建立完成後（社群偵測之後、參與度評分並行）。

## Pre-conditions

- `graph_builder` 已產出 `DiGraph`

## Normal Flow

1. 對每個節點算三項中心性：
   - **PageRank**（`centrality.pagerank`）——穩定影響力
   - **Betweenness**（`centrality.betweenness`，>2000 節點用 k=500 抽樣）——中介／橋接
   - **加權 degree centrality**（`centrality.weighted_degree_centrality`）——單純觸及範圍
2. 三項各在全網路內 min-max 正規化到 0–1（某項全同 → 0.5）
3. 加權求和：PageRank 50% / Betweenness 30% / degree 20%（`DEFAULT_WEIGHTS`，內部重新正規化到總和 1）
4. 依 influence_score 排序，指派 `influence_rank`
5. 回傳 `InfluenceResult`（`ranking` + `approximated` 旗標）

## Alternative / Exception Flows

| 情況 | 系統行為 |
|---|---|
| 空圖 | 回傳空 `ranking`、`approximated=False` |
| 網路 > 2000 節點 | betweenness 用抽樣，`approximated=True` |
| 自訂權重缺項 / 負值 / 全為 0 | 拋 `ValueError` |

## Post-conditions

- 每個 `nodes` row 的 `pagerank`、`betweenness`、`influence_rank` 欄位由 service 層寫入
- 社群指標的「前 3 名影響者」（AN-01）用的是社群子圖內的 PageRank，與此處的全圖排名不同，兩者並存

## Acceptance Criteria

- [x] **AC-1** `sum(DEFAULT_WEIGHTS.values()) == 1.0` — `test_default_weights_sum_to_one`
- [x] **AC-2** Given 一個星狀圖的中心點，When 排名，Then 它排第一 — `test_hub_of_a_star_ranks_first`
- [x] **AC-3** Given 相同輸入，When 排兩次，Then 結果一致 — `test_ranking_is_deterministic`
- [x] **AC-4** Given `top_n=3`，When 排名，Then 回 3 筆、rank 為 1/2/3 — `test_top_n_truncates`
- [x] **AC-5** Given > threshold 的圖，When 排名，Then `approximated=True` — `test_large_graph_flags_approximation`
- [x] **AC-6** Given 空圖，When 排名，Then 回空 ranking 不拋例外 — `test_empty_graph_returns_empty_ranking`
- [x] **AC-7** Given 不合法的權重，When 排名，Then 拋 `ValueError` — `test_weights_must_be_complete_and_non_negative`

## Out of scope

- 時序影響力演化
- 「這個人是不是機器人／買來的帳號」判斷
- 跨影片、跨頻道的影響力累積
- 讓使用者在 UI 上調整三項權重（權重固定，除非另開 spec）

## 實作備註

- 三項中心性都來自 `centrality.py`，本模組只做正規化 + 加權 + 排序
- betweenness 用無權重計算（邊權是互動次數，不是路徑長度）
- 排序 tie-break 用 `str(node_id)` 確保決定性
