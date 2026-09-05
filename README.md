# OrbitLink

YouTube 留言網路分析工具。輸入一個頻道或影片連結，產出互動網路圖、社群結構、影響者排名與多語情緒分析。

> 這是 FYP-25-S4-32 專案的獨立重建版，範圍收斂、規格重寫、演算法層可驗證、有 CI 與正式部署。

## 這個專案在解什麼問題

想知道一個 YouTube 頻道的留言區裡誰在跟誰互動、有沒有形成穩定的討論小圈子、哪些人是真正的中心節點而不只是留言多、整體情緒往哪走。既有工具要嘛太貴（Brandwatch、Talkwalker），要嘛需要自己寫程式（Gephi、NetworkX）。OrbitLink 把兩者中間那塊補起來。

## 功能

- YouTube 頻道 / 影片留言擷取（Data API v3）
- 回覆關係網路建構
- 社群偵測（Louvain，多解析度最佳化取最高 modularity）
- 影響者辨識（PageRank、betweenness centrality）
- 參與度評分（六項加權指標）
- 多語情緒分析
- 互動式網路圖（Cytoscape.js）
- 分析結果持久化與歷史比較
- PDF / PNG / CSV 匯出

## 技術棧

FastAPI · PostgreSQL · Redis + RQ · NetworkX · HuggingFace transformers · React + TypeScript · Cytoscape.js · Docker · GitHub Actions

架構決策見 [`docs/adr/`](docs/adr/)。

## 快速開始

```bash
cp .env.example .env      # 填入 YOUTUBE_API_KEY
docker compose up
# API   → http://localhost:8000/docs
# 前端  → http://localhost:5173
```

## 品質

- 演算法層測試覆蓋率 > 90%（`backend/app/analysis/`）
- 整體覆蓋率 > 75%
- Louvain 實作以 Zachary karate club 與 LFR benchmark 驗證，modularity 與 NMI 對照結果見 `docs/algorithm-validation.md`
- 情緒模型在 500 筆人工標註的中英留言樣本上評估，混淆矩陣見同一份文件
- 效能目標與實測見 `docs/nfr.md`

## 文件

| 文件 | 內容 |
|---|---|
| [`docs/roadmap.md`](docs/roadmap.md) | 分階段交付計畫 |
| [`docs/nfr.md`](docs/nfr.md) | 可量測的非功能需求與實測數字 |
| [`docs/adr/`](docs/adr/) | 架構決策紀錄 |
| [`docs/algorithm-validation.md`](docs/algorithm-validation.md) | 演算法與模型驗證 |
| [`docs/data-ethics.md`](docs/data-ethics.md) | PDPA、資料保留、匿名化 |
| [`docs/case-study.md`](docs/case-study.md) | 用本工具做的一份真實分析 |
| [`specs/`](specs/) | 逐條功能規格與驗收條件 |

## 授權

MIT
