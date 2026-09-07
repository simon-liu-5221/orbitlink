# 交付路線圖

假設每週投入 12–15 小時，總長約 12 週。每個里程碑結束時系統都必須是可以跑、可以展示的狀態。

原則：**垂直切片優於水平切片。** 不要先做完整個後端再做前端。每個里程碑都要有一條從 UI 到資料庫走通的路徑。

---

## M0 — 骨架與部署管線（第 1 週）

先讓「Hello World」走完整條路，這樣後面每次交付都只是往裡面填東西。

- [x] Monorepo 結構、`docker-compose.yml`（api + worker + postgres + redis，另加 frontend 方便一鍵啟動）
- [x] FastAPI 骨架 + `/healthz`（回報 db / redis 連線狀態）
- [x] Alembic 初始 migration（`0001_baseline`，無 domain 表，建立 migration 基準）
- [x] React + Vite + Tailwind 骨架，輪詢 `/healthz` 並顯示狀態燈
- [x] GitHub Actions：ruff、ruff format、mypy、import-linter、alembic、pytest、vitest、build
- [x] `.env.example` 與 secrets 設定（root + frontend）
- [x] `uv lock` 產生並 commit `backend/uv.lock`
- [x] 本機 `docker compose up` 全套跑通：5 個 container、`/healthz` 回 `ok`、前端經 Vite proxy 打到 API、worker 監聽 `orbitlink` queue、`alembic upgrade head` 套用 `0001_baseline`
- [x] 本機 CI 檢查全綠：`ruff` / `ruff format` / `mypy` / `lint-imports` / `pytest`（6 passed，含 2 integration）/ 前端 `typecheck` / `vitest`（2 passed）/ `build`
- [x] push 到 GitHub（`simon-liu-5221/orbitlink`，public），Actions 全綠（backend + frontend 兩個 job 全部步驟通過）
- [x] 雲端部署：Render（`orbitlink-api-nooj.onrender.com` API + `orbitlink-web.onrender.com` static）、Neon（Postgres, Singapore）、Upstash（Redis, Singapore）。見 `docs/deployment.md` 與 `render.yaml`（ADR-0001 M0 更新：Fly.io 要綁卡，改用 Render free；worker 延到 M2）
- [ ]（選配）UptimeRobot monitor 打 `/healthz`，5 分鐘間隔（兼保溫，減少 Render free 冷啟動）

**驗收**：✅ production URL `https://orbitlink-web.onrender.com` 打開顯示 OrbitLink 頁面與 database / redis 兩顆綠燈；`/healthz` 回 `status: ok`；CORS 正確；GitHub Actions 全綠。**M0 完成。**

> 已知限制（延到後續里程碑）：Render free 15 分鐘休眠 + ~50s 冷啟動（AVAIL-01 暫緩，見 nfr.md）；RQ worker 未部署（Render 無免費 worker，M2 決定付費或搬遷）。
> 本機 compose 把 Postgres / Redis 發佈在 host 的 55432 / 56379（避開本機已安裝的 PostgreSQL 16）；container 之間仍是 5432 / 6379。

> 這一週看起來沒有功能，但它是整個專案能不能收尾的關鍵。原 FYP 沒有這一步，所以測試只能在 localhost 手動做。

---

## M1 — 演算法層與驗證（第 2–3 週）

在碰任何 API 之前先把核心價值做出來且證明它是對的。

- [ ] `analysis/graph_builder.py` — 留言 DataFrame → DiGraph
- [ ] `analysis/communities.py` — Louvain 多解析度最佳化
- [ ] `analysis/centrality.py` — PageRank、betweenness、degree
- [ ] `analysis/engagement.py` — 六項加權評分
- [ ] `analysis/sentiment.py` — 模型注入式封裝
- [ ] 單元測試，覆蓋率 ≥ 90%
- [ ] Zachary karate club + LFR benchmark 驗證腳本
- [ ] `import-linter` 規則加入 CI

**驗收**：`pytest backend/tests/unit` 在無網路、無資料庫的環境下全綠。`docs/algorithm-validation.md` 第一版完成，含 modularity 與 NMI 對照表。

---

## M2 — 擷取與 job 管線（第 4–5 週）

- [ ] YouTube Data API client（分頁、配額處理、錯誤映射）
- [ ] `analysis_jobs` 資料表與狀態機（ADR-0002）
- [ ] RQ worker 與心跳
- [ ] 假名化（HMAC）與留言原文保留策略（`docs/data-ethics.md`）
- [ ] `POST /analyses` → `202`、`GET /jobs/{id}` 輪詢
- [ ] 整合測試：完整 job 跑通、配額耗盡、資料不足、worker 崩潰恢復

**驗收**：用 curl 送一個真實頻道連結，能在資料庫看到完整的分析結果。kill worker 後 job 會恢復。

---

## M3 — 認證與專案管理（第 6 週）

- [ ] 註冊、登入、refresh token、密碼重設
- [ ] 專案 CRUD、重新命名、封存、搜尋
- [ ] 資源隔離測試（SEC-02，每個端點都要驗 403）
- [ ] 前端：登入頁、專案清單、專案詳情

**驗收**：兩個帳號互相看不到對方的資料，有測試證明。

---

## M4 — 視覺化（第 7–8 週）

這是 demo 時第一眼看到的東西，值得多花時間。

- [ ] Cytoscape.js 網路圖：力導向佈局、社群上色、節點大小依 PageRank
- [ ] 節點點擊顯示側欄詳情
- [ ] 篩選：最小 degree、社群、情緒區間
- [ ] Recharts：情緒分布、時間走勢、參與度散點圖
- [ ] 大圖降級策略（CAP-03）
- [ ] 分析進行中的階段化進度 UI（對照狀態機，不是單純轉圈）

**驗收**：2,000 節點的圖可以流暢拖曳，PERF-04 有實測數字。

---

## M5 — 匯出、回饋與管理端（第 9 週）

- [ ] PNG / PDF / CSV 匯出
- [ ] 使用者回饋與評分
- [ ] 管理端：使用者清單、搜尋、停權、查看回饋

**驗收**：匯出的 PDF 在另一台機器打開排版正常。

---

## M6 — 歷史趨勢（第 10 週）

原 FYP 的 Predictive Analysis 是最空的一塊。這裡把它做成誠實的版本。

- [ ] 同一專案多次分析的比較視圖
- [ ] 情緒、參與度、社群數量的時間走勢
- [ ] 簡單外插預測：只在有 ≥ 5 次歷史分析時啟用，用留出集報告 MAE，並在 UI 明確標示這是外插而非模型預測
- [ ] 資料不足時顯示「需要更多歷史分析」而不是編造數字

**驗收**：資料不足時不出現假資料。有 MAE 數字。

> 如果第 10 週時間不夠，這個功能砍掉比做半套好。文件裡直接寫「不在範圍內」，比宣稱有 ML 預測但拿不出驗證更有說服力。

---

## M7 — 硬化與量測（第 11 週）

- [ ] k6 負載測試，填完 `docs/nfr.md` 的實測欄位
- [ ] `pip-audit`、`npm audit`、`gitleaks` 加入 CI
- [ ] 限流、結構化日誌、Sentry
- [ ] 錯誤狀態盤點，消除所有裸露 500
- [ ] Lighthouse CI

**驗收**：`docs/nfr.md` 沒有空白的實測欄位，未達標的項目誠實標記並說明原因。

---

## M8 — 案例研究與作品呈現（第 12 週）

這一週決定這個專案在面試時的價值。

- [ ] 500 則留言人工標註，完成 `docs/algorithm-validation.md`
- [ ] `docs/case-study.md`：挑一個真實頻道做完整分析，寫出你發現了什麼
- [ ] README 補上截圖與 demo GIF
- [ ] 錄一段 3 分鐘的 demo 影片
- [ ] 部署 demo 帳號，附種子資料，讓人不用註冊就能看到結果
- [ ] 寫一篇技術部落格，主題選一個：Louvain 多解析度最佳化怎麼做、為什麼把演算法層做成純函式、情緒模型在中英混雜留言上的實際表現

**驗收**：把 URL 丟給一個不認識這專案的人，他五分鐘內看得懂這是什麼、有什麼發現。

---

## 時間不夠時的取捨順序

從後往前砍：M6 → M5 管理端 → M5 匯出。

**M0、M1、M7、M8 不可砍。** 部署管線、演算法驗證、量測數字、案例研究，這四項才是把這個專案跟其他學生作品區隔開來的地方。功能少一點沒關係，做不完但講得清楚為什麼，比功能多但沒有一項經得起追問要好。
