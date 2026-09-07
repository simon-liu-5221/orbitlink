# AN-01：社群偵測

**Status**: done
**Actor**: System（在分析 job 的 `analyzing` 階段自動執行）
**相關 ADR**: ADR-0002, ADR-0003

> 實作：`backend/app/analysis/{types,graph_builder,centrality,communities}.py`，測試 `backend/tests/unit/analysis/`（100% 覆蓋率，34 tests）。branch `feat/AN-01-detect-communities`。

## 目的

使用者想知道留言區裡有沒有形成穩定的討論小圈子，各圈子多大、聊什麼調性、誰是圈子的核心、誰橫跨多個圈子。

## Trigger

分析 job 進入 `analyzing` 階段，互動網路已建立完成。

## Pre-conditions

- `graph_builder` 已產出 `DiGraph`
- 圖中至少 3 個節點與 2 條邊

## Normal Flow

1. 將有向圖轉為無向加權圖（邊權重 = 該對使用者之間的互動次數）
2. 對解析度參數 `[0.5, 1.0, 1.5, 2.0]` 各跑一次 Louvain
3. 計算每次結果的 modularity，選最高者
4. 為每個節點指派 community ID
5. 對每個社群計算指標：
   - 規模（節點數）
   - 總留言數、總按讚數
   - 平均情緒分數
   - 前 3 名影響者（社群子圖內的 PageRank）
   - 橋接使用者（全圖 betweenness centrality 前段且屬於此社群者）
   - 內聚度（平均 clustering coefficient）
   - 網路密度
6. 回傳 `CommunityDetectionResult`

## Alternative / Exception Flows

| 情況 | 系統行為 |
|---|---|
| 節點 < 3 或邊 < 2 | 回傳 `insufficient_data=True`、空社群列表，不視為錯誤 |
| 所有解析度的 modularity 皆 < 0.3 | 正常回傳，但設 `weak_structure=True`，前端顯示「此網路沒有明顯社群結構」 |
| 解析度最佳化過程拋出例外 | 記錄警告，回退到 resolution=1.0 的結果 |
| 圖為非連通 | 正常處理，Louvain 本身支援；各連通元件會落在不同社群 |

## Post-conditions

- 結果由 service 層寫入 `communities` 與 `nodes` 表
- 每個節點都有 `community_id`
- `analyses.modularity` 與 `analyses.resolution_used` 已記錄

## Acceptance Criteria

- [x] **AC-1** Given Zachary karate club 圖，When 執行社群偵測，Then modularity ≥ 0.40 且社群數在 2–5 之間 — `test_ac1_zachary_karate_club`（實測 modularity 0.4266、4 社群）
- [x] **AC-2** Given 一個 LFR benchmark 圖（mu=0.1，已知 ground truth），When 執行偵測，Then 與 ground truth 的 NMI ≥ 0.85 — `test_ac2_lfr_benchmark_nmi`（實測 NMI 1.00，n=500）
- [x] **AC-3** Given 一個 2 節點 1 邊的圖，When 執行偵測，Then 回傳 `insufficient_data=True` 且不拋例外 — `test_ac3_two_node_graph_is_insufficient_data`
- [x] **AC-4** Given 一個完全隨機的 Erdős–Rényi 圖，When 執行偵測，Then `weak_structure=True` — `test_ac4_random_graph_flags_weak_structure`
- [x] **AC-5** Given 任一有效圖，When 執行兩次偵測且 random_state 相同，Then 兩次結果的社群指派完全一致 — `test_ac5_same_seed_gives_identical_assignment`
- [x] **AC-6** Given 一個已知社群結構的手工 fixture 圖，When 計算社群指標，Then 每個社群的節點數、密度、平均情緒與手算值相符 — `test_ac6_hand_fixture_metrics_match_by_hand`
- [x] **AC-7** Given 解析度最佳化拋出例外，When 執行偵測，Then 回傳 resolution=1.0 的結果且記錄警告，不拋出 — `test_ac7_resolution_sweep_failure_falls_back_to_res_1`
- [x] **AC-8** `communities.py` 不 import 任何 db / api / http 模組（由 import-linter 驗證）— `test_ac8_module_does_not_import_io_layers` + CI `lint-imports`

## Out of scope

- 重疊社群偵測（一個節點只屬於一個社群）
- 動態 / 時序社群演化
- 社群主題建模（不做 LDA 或關鍵詞抽取）
- 使用者手動調整社群劃分

## 實作備註

- 用 `networkx.community.louvain_communities`，`seed` 固定以確保 AC-5
- 有向圖轉無向時邊權要合併，不是取代
- betweenness centrality 在大圖上是 O(VE)，超過 2,000 節點時用 `k` 抽樣近似（`betweenness_centrality(G, k=500)`），並在結果標記 `approximated=True`
- 情緒分數在此階段可能尚未算完，設計成情緒為選填輸入；若為 None 則社群指標中的平均情緒為 None，不阻塞
