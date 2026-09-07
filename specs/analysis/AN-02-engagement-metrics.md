# AN-02：參與度指標

**Status**: done
**Actor**: System
**相關 ADR**: ADR-0003

> 實作：`backend/app/analysis/engagement.py`（`raw_metrics` / `normalize` / `weighted_score` / `score_engagement` + `weight_sensitivity`），測試 `backend/tests/unit/analysis/test_engagement.py`（15 tests，`app/analysis` 覆蓋率 100%）。branch `feat/AN-02-engagement-metrics`。

## 目的

使用者想找出真正在推動討論的人，而不只是留言數最多的人。留言 100 則但沒人回應的帳號，跟留言 20 則但每則都引發串接對話的帳號，價值不同。

## Trigger

分析 job 的 `analyzing` 階段，社群偵測完成後。

## Pre-conditions

- 互動網路已建立
- 每個節點已有原始統計（留言數、按讚數、被回覆數、活躍天數）

## Normal Flow

1. 對每個節點計算六項原始指標
2. 各項在整個網路內做 min-max 正規化到 0–1
3. 加權求和後線性映射到 1–10
4. 依總分排序，回傳全部排名與前 5 名的細項拆解

## 六項指標與權重

| 指標 | 權重 | 定義 |
|---|---|---|
| Engagement | 25% | 該使用者留言獲得的回覆數 + 按讚數 |
| Consistency | 20% | 有留言的不重複日數 ÷ 分析期間總日數 |
| Network | 20% | 該節點的加權 degree centrality |
| Quality | 15% | 平均留言長度（對數壓縮）× 平均每則獲得的回覆數 |
| Activity | 10% | 總留言數 |
| Responsiveness | 10% | 該使用者回覆他人的次數 ÷ 其總留言數 |

權重定義於 `analysis/engagement.py` 的 `DEFAULT_WEIGHTS`，總和必須為 1.0。

## Alternative / Exception Flows

| 情況 | 系統行為 |
|---|---|
| 網路中所有節點某項指標值相同 | 該項正規化後全部設為 0.5，不做除以零 |
| 節點少於 5 個 | 正常計算，前 N 名回傳實際數量 |
| 分析期間為 0 天（所有留言同一天） | Consistency 分母設為 1 |
| 使用者從未回覆他人 | Responsiveness = 0，不排除該使用者 |

## Post-conditions

- 每個節點的 `engagement_score` 與六項細項分數寫入 `nodes` 表
- 前 5 名可供前端顯示細項拆解、圓餅圖與散點圖

## Acceptance Criteria

- [x] **AC-1** Given 任意有效輸入，When 計算分數，Then 所有分數落在 1.0–10.0 閉區間內 — `test_ac1_all_scores_within_one_to_ten`
- [x] **AC-2** `sum(DEFAULT_WEIGHTS.values()) == 1.0`（浮點容差 1e-9）— `test_ac2_default_weights_sum_to_one`
- [x] **AC-3** Given 一個手工 fixture（3 個節點，各項指標為已知值），When 計算，Then 每個節點的總分與手算值相符至小數點後 4 位 — `test_ac3_hand_computed_scores_match_to_four_decimals`
- [x] **AC-4** Given 兩個節點除了 Engagement 外所有指標相同，When 計算，Then Engagement 較高者總分較高 — `test_ac4_higher_engagement_wins_when_all_else_equal`
- [x] **AC-5** Given 所有節點的 Activity 完全相同，When 正規化，Then 不拋除以零，該項全部為 0.5 — `test_ac5_uniform_metric_normalises_to_half_without_dividing_by_zero`
- [x] **AC-6** Given 只有 2 個節點的網路，When 取前 5 名，Then 回傳 2 筆而非補空 — `test_ac6_top_n_returns_actual_count_for_small_network`
- [x] **AC-7** Given 一組輸入，When 用自訂權重覆寫 DEFAULT_WEIGHTS，Then 分數依新權重改變且仍在 1–10 內 — `test_ac7_custom_weights_change_scores_but_stay_in_range`（權重內部正規化到總和 1，任何非負權重都保證在範圍內）
- [x] **AC-8** 前 5 名結果中每一筆都包含六項細項分數，供前端拆解顯示 — `test_ac8_top_entries_carry_all_six_subscores`

> 敏感度分析：`weight_sensitivity()` 已實作（每項權重 ±10%，回報前 N 名是否穩定 + 與基準排名的最差 Spearman）。數字表格在 `docs/algorithm-validation.md` §2.1（branch 4 補）。

## Out of scope

- 跨分析、跨專案的參與度累積
- 依權重讓使用者在 UI 上即時調整（權重固定，除非未來另開 spec）
- 機器人 / 垃圾留言偵測

## 實作備註

- 正規化與加權要分成兩個函式，方便分別測試
- 這六項權重是沿用原 FYP 的設計，但原文件沒有說明權重怎麼來的。在 `docs/algorithm-validation.md` 中要誠實說明這是啟發式權重、未經實證校準，並做一次敏感度分析：把每項權重各 ±10% 看排名前 5 是否穩定。這一段會是面試時很好的談資
- Quality 用對數壓縮避免長篇留言者被過度加權：`log1p(avg_length) * avg_replies`
