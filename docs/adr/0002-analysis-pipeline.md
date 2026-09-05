# ADR-0002：分析流程設計為 job 狀態機

**狀態**：已採納

## 背景

原始 FYP 對「分析需要跑很久」這件事的處理，只有一個 use case：前端顯示一個進度計時器。沒有任務佇列、沒有狀態持久化、沒有失敗重試。另外社群偵測的 post-condition 寫「結果存在 session storage」，但資料庫設計裡有 `analyses` 子集合，兩者矛盾，實際上代表結果關掉分頁就消失。

## 決策

分析是一個持久化的 job，狀態存在 Postgres 的 `analysis_jobs` 表。

### 狀態機

```
queued ──▶ fetching ──▶ building_graph ──▶ analyzing ──▶ persisting ──▶ completed
   │           │              │                │              │
   └───────────┴──────────────┴────────────────┴──────────────┴──▶ failed
                                                                     │
                                                                     ▼
                                                                 cancelled
```

每次狀態轉移寫入 `analysis_jobs.status` 與 `progress`（0–100）並更新 `updated_at`。

### 階段

| 階段 | 工作 | 產出 |
|---|---|---|
| `fetching` | 呼叫 YouTube Data API 分頁抓留言與回覆 | 原始留言列（暫存） |
| `building_graph` | 從 comment→parent_comment 關係建有向圖，作者 ID 做 HMAC 雜湊 | `networkx.DiGraph` |
| `analyzing` | Louvain、PageRank、betweenness、engagement scoring、情緒推論 | dataclass 結果物件 |
| `persisting` | 寫入 `analyses`、`nodes`、`communities`、`sentiment_results` | DB rows |

### API 契約

```
POST /api/v1/projects/{id}/analyses   → 202 { "job_id": "..." }
GET  /api/v1/jobs/{job_id}            → 200 { "status": "analyzing", "progress": 62, ... }
GET  /api/v1/analyses/{analysis_id}   → 200 完整結果
```

前端在 job 未完成時以 2 秒間隔輪詢 `/jobs/{job_id}`。

### 失敗處理

- YouTube API 配額耗盡 → `failed`，`error_code = QUOTA_EXCEEDED`，前端顯示明確訊息與重試時間
- 留言數不足（節點 < 3 或邊 < 2）→ `completed`，但結果標記 `insufficient_data = true`，前端顯示說明而不是空白圖
- 模型推論逾時 → 重試 2 次後 `failed`
- worker 崩潰 → job 超過 30 分鐘無心跳自動標記 `failed`

## 後果

- 使用者可以關掉分頁，回來仍看得到結果
- 歷史分析可查詢，Predictive Analysis 才有真實的輸入資料
- 需要額外維護一個 worker process 與心跳機制
