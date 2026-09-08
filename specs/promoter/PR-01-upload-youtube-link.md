# PR-01：上傳 YouTube 連結並啟動分析

**Status**: in-progress
**Actor**: Promoter
**相關 ADR**: ADR-0002

> M2 分階段實作：連結解析 + YouTube client 在 `feat/PR-01-ingest`（PR 2）；job 執行串接在
> `feat/M2-analysis-service`（PR 3）；`POST /analyses` 端點與 AC 驗收在 `feat/PR-01-api`（PR 4）。

## 目的

使用者貼上一個 YouTube 頻道或影片連結，系統擷取留言並啟動完整分析，使用者可以離開頁面稍後回來看結果。

## Trigger

使用者在專案頁面貼上連結並按「開始分析」。

## Pre-conditions

- 使用者已登入
- 專案存在且屬於該使用者
- 該專案沒有正在進行中的分析 job

## Normal Flow

1. 使用者貼上連結，前端即時做格式驗證並顯示辨識到的類型（頻道 / 影片）
2. 使用者確認分析參數（留言數上限，預設 5,000）
3. 前端 `POST /api/v1/projects/{id}/analyses`
4. 後端驗證連結、解析出 video ID 或 channel ID、建立 `analysis_jobs` 記錄、推入 RQ 佇列，回 `202 { job_id }`
5. 前端導向進度頁，每 2 秒輪詢 `GET /api/v1/jobs/{job_id}`
6. 進度頁依 ADR-0002 的狀態機顯示具名階段（擷取留言中 / 建立網路中 / 分析中 / 儲存中）
7. job 完成後前端自動導向結果頁

## Alternative / Exception Flows

| 情況 | 系統行為 | HTTP |
|---|---|---|
| 連結格式無效 | 前端擋下並提示範例格式；後端也驗證 | 422 |
| 影片 / 頻道不存在或私人 | job 立即 failed，`error_code=RESOURCE_NOT_FOUND` | 202 → job failed |
| 影片關閉留言 | job failed，`error_code=COMMENTS_DISABLED`，訊息說明原因 | 202 → job failed |
| YouTube API 配額耗盡 | job failed，`error_code=QUOTA_EXCEEDED`，顯示配額重置時間（太平洋時間午夜） | 202 → job failed |
| 留言數超過 CAP-01 上限 50,000 | 拒絕建立 job，提示縮小範圍 | 422 |
| 該專案已有進行中的 job | 拒絕，提示先等待或取消 | 409 |
| 使用者不擁有該專案 | 拒絕 | 403 |
| 一分鐘內第 11 次請求 | 限流 | 429 |
| 使用者離開頁面 | job 繼續在後端執行，回來時可從專案頁看到進行中的 job | — |
| 使用者按取消 | job 標記 cancelled，worker 在下一個檢查點停止 | 200 |

## Post-conditions

- `analysis_jobs` 有一筆記錄，狀態為終態之一（completed / failed / cancelled）
- 成功時 `analyses` 及其關聯表有完整結果
- 作者身分已依 `docs/data-ethics.md` 假名化

## Acceptance Criteria

- [ ] **AC-1** Given 合法的影片連結，When POST，Then 回 202 且 body 含 job_id，且資料庫有一筆 `queued` 的 job
- [x] **AC-2** Given 各種連結格式（`youtube.com/watch?v=`、`youtu.be/`、`youtube.com/@handle`、`youtube.com/channel/UC...`、含額外 query 參數、`shorts/`、`live/`、`m.youtube.com`），When 解析，Then 都能正確取出 ID — `parse_youtube_url`，`test_urls.py::test_parses_supported_formats`（12 個格式）
- [~] **AC-3** Given 非 YouTube 的 URL 或亂碼字串，When 解析，Then 拋 `InvalidYouTubeURLError` 且訊息含預期格式範例 — `test_rejects_bad_links_with_format_guidance`（純函式層完成；端點回 422 在 PR 4）
- [ ] **AC-4** Given 使用者 A 的專案 ID，When 使用者 B POST，Then 回 403 且不洩漏該專案是否存在
- [ ] **AC-5** Given 該專案已有 `analyzing` 狀態的 job，When 再次 POST，Then 回 409
- [ ] **AC-6** Given YouTube API 回 quota exceeded，When job 執行，Then job 狀態為 failed 且 `error_code=QUOTA_EXCEEDED`
- [ ] **AC-7** Given job 執行中，When 呼叫 `GET /jobs/{id}`，Then 回傳的 status 屬於狀態機定義的合法值，progress 為 0–100 的整數
- [ ] **AC-8** Given job 進入 completed，When 查詢資料庫，Then 沒有任何一筆記錄含有原始 YouTube channel ID（全部已假名化）
- [ ] **AC-9** Given 未認證的請求，When POST，Then 回 401
- [ ] **AC-10** Given 一分鐘內同一 IP 發出 11 次請求，When 第 11 次，Then 回 429

## Out of scope

- 排程分析 / 定期自動重跑
- 非 YouTube 的資料來源
- 使用者自行上傳 CSV
- 一次分析多個連結

## 實作備註

- 連結解析要獨立成純函式 `parse_youtube_url(url) -> YouTubeTarget`，方便對 AC-2 做表格驅動測試
- 頻道分析先取該頻道最近 N 支影片（預設 10 支），再逐支抓留言，這個 N 要可設定
- YouTube API 的 `commentThreads.list` 每次最多 100 筆，要處理 `nextPageToken` 分頁
- 抓留言時同時取 `parentId` 以建立回覆關係，這是整個網路圖的來源，缺了就沒有邊
- 配額成本：`commentThreads.list` 每次 1 unit，預設每日 10,000 units。5,000 則留言約 50 units，實務上瓶頸不是配額而是時間
