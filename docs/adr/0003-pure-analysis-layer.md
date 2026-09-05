# ADR-0003：演算法層為純函式，與 I/O 完全隔離

**狀態**：已採納

## 背景

原始 FYP 的社群偵測邏輯與 YouTube 擷取、Firestore 寫入綁在同一段流程裡。結果是演算法無法單獨測試，測試計畫只剩下「用 Chrome 手動點一次看有沒有出圖」，29 個測試項全部標 100% 通過、0 個 pending。這種測試結果沒有說服力，因為它證明不了 modularity 算得對。

## 決策

`backend/app/analysis/` 底下所有模組必須是純的。

**允許的輸入**：`networkx.Graph` / `DiGraph`、`pandas.DataFrame`、原生型別、dataclass
**允許的輸出**：dataclass、dict、DataFrame
**禁止 import**：`sqlalchemy`、`fastapi`、`httpx`、`redis`、`os.environ`、任何專案內的 `db` / `api` / `ingest` 模組

用 `import-linter` 在 CI 強制執行這條界線。

### 模組劃分

```
analysis/
  graph_builder.py     # 留言 DataFrame → DiGraph（不負責抓資料）
  communities.py       # Louvain + 多解析度最佳化
  centrality.py        # PageRank、betweenness、degree
  engagement.py        # 六項加權評分
  sentiment.py         # 模型推論封裝（模型物件由外部注入）
  types.py             # 共用 dataclass
```

`sentiment.py` 的模型不在模組內載入，由呼叫端注入，這樣測試時可以傳假的推論函式。

### 測試策略

| 測試對象 | 方法 |
|---|---|
| `communities.louvain_multi_resolution` | Zachary karate club（已知 4 個社群，modularity ≈ 0.42）；LFR benchmark 圖比對 NMI |
| `centrality.pagerank` | 對照 `networkx.pagerank` 的輸出，容差 1e-6 |
| `engagement.score` | 手算的小型 fixture，驗證六項權重加總為 1.0、分數落在 1–10 |
| `graph_builder` | 邊界情況：空 DataFrame、單一留言、自我回覆、缺失 parent_id |
| `sentiment` | 注入假模型，驗證批次切分與聚合邏輯 |

演算法層覆蓋率目標 90%。

## 後果

- 可以在沒有資料庫、沒有網路的情況下跑完整個演算法測試套件，CI 快
- 換 NLP 模型或換圖函式庫時，影響範圍侷限在單一模組
- 需要多一層 service 做協調，程式碼行數略增
