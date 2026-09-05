# CLAUDE.md

給 Claude Code 的專案指引。每個 session 開始前先讀這份，再讀對應的 `specs/` 檔案。

---

## 專案是什麼

OrbitLink：YouTube 留言網路分析工具。使用者貼上一個頻道或影片連結，系統抓取留言、建立回覆互動網路，跑社群偵測、影響者辨識與情緒分析，把結果以互動式網路圖與圖表呈現，並可匯出。

**這是重建版，範圍刻意比原始 FYP 小。** 原專案宣稱多平台、地理映射、影像辨識、AI chatbot、CRM 整合，全部不在範圍內。任何 spec 以外的功能一律不要主動實作。

## 技術棧（已定案，不要自行更換）

| 層 | 選擇 |
|---|---|
| 後端 | Python 3.12, FastAPI, Pydantic v2 |
| 分析 | NetworkX, python-louvain, pandas, scikit-learn |
| NLP | HuggingFace transformers（多語情緒），詳見 ADR-0004 |
| 任務佇列 | RQ + Redis |
| 資料庫 | PostgreSQL 16 + SQLAlchemy 2.0 + Alembic |
| 認證 | 自建 JWT（access + refresh），argon2 雜湊 |
| 前端 | React 18 + TypeScript + Vite |
| 前端狀態 | TanStack Query（server state）、Zustand（UI state） |
| 樣式 | Tailwind CSS |
| 圖形視覺化 | Cytoscape.js |
| 圖表 | Recharts |
| 部署 | Docker；後端 Fly.io、前端 Cloudflare Pages、DB Neon、Redis Upstash |
| CI | GitHub Actions |

決策理由寫在 `docs/adr/`。要改棧就先改 ADR。

## 專案結構

```
backend/
  app/
    api/           # FastAPI routers，只做驗證與轉發
    core/          # config, security, logging
    db/            # models, session, migrations
    jobs/          # RQ worker、job 狀態機
    services/      # 應用邏輯（協調 analysis 與 db）
    analysis/      # ★ 純函式演算法層，不得 import db / fastapi / requests
    ingest/        # YouTube API client
  tests/
    unit/          # 對 analysis/ 的測試，用 fixture graph
    integration/   # 對 api/ 的測試，用 testcontainers
frontend/
  src/
    api/           # 型別化的 API client（由 OpenAPI 產生）
    features/      # 依功能分資料夾，不是依檔案類型
    components/
docs/
specs/
```

## 不可違反的規則

1. **`backend/app/analysis/` 是純的。** 只吃 `networkx.Graph` 或 `pandas.DataFrame`，只吐 dataclass / dict。不得 import 資料庫、HTTP client、FastAPI、環境變數。這一層必須能離線測試。
2. **先寫測試。** 每個 spec 的 Acceptance Criteria 先轉成失敗的測試，再實作。commit 訊息裡標明對應的 spec ID。
3. **分析結果一律進資料庫。** 不用 session storage、不用記憶體快取當儲存。
4. **分析永遠是非同步 job。** API 回 `202 + job_id`，前端輪詢 `/jobs/{id}`。不要在 request 裡跑分析。
5. **不存原始留言文字超過 30 天。** 留言作者 ID 一律 HMAC 雜湊後才落地。詳見 ADR-0005。
6. **金鑰只從環境變數讀。** 任何 `.env`、token、API key 不進 git。
7. **不要為了讓測試過而放寬斷言。** 測試失敗就修實作。
8. **每個 API 變更要同步更新 OpenAPI 型別產生**（`npm run gen:api`）。

## 開發流程

一個 spec = 一個 branch = 一個 PR。

```
1. 讀 specs/<area>/<id>.md
2. 寫失敗的測試（unit 先於 integration）
3. 實作到綠燈
4. ruff check && mypy && pytest --cov
5. 更新 spec 的 Status 欄位
```

## 常用指令

```bash
# 後端
uv run uvicorn app.main:app --reload
uv run pytest --cov=app --cov-report=term-missing
uv run ruff check . && uv run mypy app

# worker
uv run rq worker orbitlink

# 前端
npm run dev
npm run test
npm run gen:api       # 從 backend OpenAPI 產生 TS 型別

# 全套
docker compose up
```

## 提交前檢查

- [ ] 測試通過且新增了對應 spec 的測試
- [ ] `ruff` 與 `mypy` 無錯
- [ ] 沒有硬編碼的金鑰或 URL
- [ ] 有需要的話更新了 `docs/` 或 spec 的 Status
