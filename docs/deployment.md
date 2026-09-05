# 部署指南（M0）

M0 的目標：production URL 打開能看到頁面，頁面顯示後端健康狀態，CI 全綠。

程式骨架、`docker-compose.yml`、CI 已經在 repo 裡。以下是需要**你的帳號**才能完成的雲端設定，照順序做。

---

## 0. 前置

```bash
cp .env.example .env
# 產生真正的秘密（deploy 用，不要用 dev 預設值）
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('PSEUDONYM_KEY=' + secrets.token_urlsafe(32))"
```

本機先確認整套跑得起來：

```bash
docker compose up --build
# http://localhost:5173      → 前端，應顯示 database/redis 兩顆綠燈
# http://localhost:8000/docs → API 文件
```

安裝 CLI：

```bash
# Fly.io
curl -L https://fly.io/install.sh | sh      # Windows: iwr https://fly.io/install.ps1 -useb | iex
fly auth login

# Cloudflare（前端用 Pages，可用 dashboard 或 wrangler）
npm i -g wrangler && wrangler login
```

---

## 1. 資料庫 — Neon

1. https://neon.tech 建一個 project（region 選 Singapore）。
2. 複製 connection string，改成 psycopg v3 格式：
   `postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`
3. 先留著，第 3 步設進 Fly secrets。

## 2. Redis — Upstash

1. https://upstash.com 建一個 Redis database（region 同上，選 **TLS enabled**）。
2. 複製 `rediss://…` URL（注意是兩個 s）。

## 3. 後端 — Fly.io

`backend/fly.toml` 已備好，app 名稱是 placeholder `orbitlink-api`。

```bash
cd backend
fly launch --no-deploy --copy-config --name orbitlink-api --region sin

fly secrets set \
  DATABASE_URL="postgresql+psycopg://…?sslmode=require" \
  REDIS_URL="rediss://…" \
  JWT_SECRET="…" \
  PSEUDONYM_KEY="…" \
  YOUTUBE_API_KEY=""     # M2 再填

fly deploy
```

`fly.toml` 定義了兩個 process group：`app`（API，跑 migration 後啟動 uvicorn）與 `worker`（RQ）。部署後：

```bash
fly scale count app=1 worker=1
fly status
curl https://orbitlink-api.fly.dev/healthz     # 應回 {"status":"ok",...}
```

## 4. 前端 — Cloudflare Pages

Dashboard → Workers & Pages → Create → Pages → Connect to Git：

| 設定 | 值 |
|---|---|
| Framework preset | Vite |
| Build command | `npm run build` |
| Build output directory | `frontend/dist` |
| Root directory | `frontend` |
| Environment variable | `VITE_API_BASE_URL = https://orbitlink-api.fly.dev` |

部署後打開 `*.pages.dev`，應該看到 M0 頁面與兩顆綠燈。

回頭把該網域加進後端 CORS：

```bash
fly secrets set CORS_ORIGINS='["https://orbitlink.pages.dev"]' -a orbitlink-api
```

## 5. CI secrets（GitHub）

M0 的 CI 只跑 lint / test / build，不需要 secrets。若之後要加自動部署（M0 選項未啟用），需要：

- `FLY_API_TOKEN`（`fly tokens create deploy`）
- `CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID`

## 6. 監控

UptimeRobot 加一個 monitor 打 `https://orbitlink-api.fly.dev/healthz`，5 分鐘間隔（AVAIL-01）。

---

## 待辦（M0 收尾）

- [ ] 本機 `docker compose up` 兩顆綠燈
- [ ] `uv lock` 產生並 commit `backend/uv.lock`（可重現建置）
- [ ] Neon / Upstash / Fly / Cloudflare 四項設定完成
- [ ] production URL 顯示健康狀態
- [ ] GitHub Actions 全綠
- [ ] UptimeRobot monitor 啟用
- [ ] roadmap.md 的 M0 checklist 打勾
