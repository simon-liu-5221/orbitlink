# 部署指南（M0）

M0 的目標：production URL 打開能看到頁面，頁面顯示後端健康狀態，CI 全綠。

平台（見 ADR-0001 的 M0 更新，全部免綁信用卡）：

| 元件 | 平台 | 帳號 |
|---|---|---|
| 後端 API | Render free web service（Docker） | 需註冊（GitHub 登入） |
| 前端 | Render free static site | 同上 |
| PostgreSQL | Neon free | 作者已有 |
| Redis | Upstash free | 需註冊（GitHub 登入） |
| RQ worker | 不部署（M2 再說） | — |

程式骨架、`render.yaml`、CI 已在 repo 裡。以下照順序做。

---

## 0. 本機確認（已驗證通過）

```bash
cp .env.example .env
docker compose up --build
# http://localhost:5173 顯示 database/redis 兩顆綠燈
```

---

## 1. PostgreSQL — Neon

1. https://console.neon.tech → New Project
2. 名稱 `orbitlink`，region 選 **Singapore**（`ap-southeast-1`）
3. Dashboard → Connection string，複製，並改成 psycopg v3 格式：
   - 原始：`postgresql://user:pwd@ep-xxx.ap-southeast-1.aws.neon.tech/orbitlink?sslmode=require`
   - 改成：`postgresql+psycopg://user:pwd@ep-xxx.ap-southeast-1.aws.neon.tech/orbitlink?sslmode=require`
     （只加 `+psycopg`）
4. 留著，第 4 步貼進 Render。

## 2. Redis — Upstash

1. https://console.upstash.com → 用 GitHub 登入
2. Create Database → 名稱 `orbitlink`，Type **Regional**，Region 選最接近的（`ap-southeast-1` / Singapore），**TLS/SSL 開啟**
3. 資料庫頁面 → 往下找 **`UPSTASH_REDIS_URL`** 或 "Redis Connect" 的 `rediss://` 連線字串（注意是兩個 s）
   - 形如 `rediss://default:xxxxxxxx@apn1-xxx.upstash.io:6379`
4. 留著。

## 3. Render 帳號

1. https://dashboard.render.com → Get Started → **Sign in with GitHub**
2. 授權 Render 存取 `simon-liu-5221/orbitlink`（可選 only select repositories）

## 4. 用 Blueprint 建立服務

1. Render dashboard → **New +** → **Blueprint**
2. 選 `simon-liu-5221/orbitlink` repo → Render 讀取 `render.yaml`，會列出 `orbitlink-api`（web）與 `orbitlink-web`（static）
3. 按 **Apply**。它會要你填 `sync: false` 的環境變數：

   **orbitlink-api：**
   | key | value |
   |---|---|
   | `DATABASE_URL` | 第 1 步的 Neon 字串（含 `+psycopg`） |
   | `REDIS_URL` | 第 2 步的 Upstash `rediss://` 字串 |
   | `CORS_ORIGINS` | 先填 `["https://orbitlink-web.onrender.com"]`（正確網域第 5 步確認後回來改） |
   | `YOUTUBE_API_KEY` | 留空 |

   `JWT_SECRET` / `PSEUDONYM_KEY` 由 Render 自動產生（`generateValue`），不用填。

   **orbitlink-web：**
   | key | value |
   |---|---|
   | `VITE_API_BASE_URL` | `https://orbitlink-api.onrender.com`（第 5 步確認實際網域） |

4. Apply 後 Render 開始 build。API 第一次 build（Docker + uv sync）約 3–5 分鐘。

## 5. 確認網域並修正交叉引用

Blueprint 套用後，每個 service 的實際網域在其 dashboard 頁面（通常就是 `orbitlink-api.onrender.com` / `orbitlink-web.onrender.com`，若名稱被占用會加隨機字尾）。

1. 記下 API 與 web 的實際 URL
2. 若和上面預設不同：
   - `orbitlink-api` → Environment → 改 `CORS_ORIGINS` 成實際的 web URL（JSON 陣列）
   - `orbitlink-web` → Environment → 改 `VITE_API_BASE_URL` 成實際的 API URL → Manual Deploy（static site 環境變數是 build 時注入，改完要重 build）
3. 兩邊都 redeploy

## 6. 驗收

```bash
curl https://orbitlink-api.onrender.com/healthz
# 首次可能等 ~50s（冷啟動），應回：
# {"status":"ok","version":"0.1.0","environment":"production","dependencies":{"database":"up","redis":"up"}}
```

瀏覽器打開 `https://orbitlink-web.onrender.com` → 應顯示 OrbitLink 頁面與 database / redis 兩顆綠燈。

## 7. 監控

UptimeRobot（https://uptimerobot.com，免綁卡）→ 新增 HTTP(s) monitor：
- URL `https://orbitlink-api.onrender.com/healthz`
- 間隔 5 分鐘（順便當保溫，減少冷啟動）

---

## CI 的自動部署

Render 的 `autoDeploy: true` 已經處理：push 到 `main` → Render 自動重新 build 部署。GitHub Actions 只負責 lint / test / build，不碰部署，不需要額外 secret。

## 待辦（M0 收尾）

- [x] 本機 `docker compose up`
- [x] `uv.lock` committed
- [x] push GitHub + Actions 全綠
- [x] Neon project 建立，連線字串取得（已對 Neon 跑 `alembic upgrade head`）
- [x] Upstash Redis 建立，`rediss://` 取得（已測 PING + RQ queue）
- [x] 本機用真實 Neon + Upstash 跑 API，`/healthz` 回 `status: ok`
- [x] Render Blueprint apply，兩個 service 綠（API = `orbitlink-api-nooj`，web = `orbitlink-web`）
- [x] `curl https://orbitlink-api-nooj.onrender.com/healthz` 回 `status: ok`（db + redis up）
- [x] web `VITE_API_BASE_URL` 修正為 `-nooj` 網址並重 build；CORS preflight 通過
- [ ]（選配）UptimeRobot monitor

## 部署後備忘

- API: https://orbitlink-api-nooj.onrender.com （`/docs`, `/healthz`）
- Web: https://orbitlink-web.onrender.com
- Render `orbitlink-api` 名稱被占用 → 服務名 `orbitlink-api-nooj`。`CORS_ORIGINS` 指向 web（clean 名稱，OK）；web `VITE_API_BASE_URL` 指向 `-nooj`。
- push `main` → Render `autoDeploy` 自動重建兩個 service。
- Neon / Upstash 連線字串在 Render 的 env vars（`sync: false`），不在 git。
