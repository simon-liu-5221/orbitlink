# 非功能需求

原始 FYP 的非功能需求全部是形容詞：「fast interactions」「availability at all times」「supporting a multitude of users」「dynamic scaling, load balancing」，整節沒有一個數字，也沒有任何測試支持。這份重寫成可量測的目標，每一條都要有對應的測試與實測數字。

`實測` 欄位在對應測試建立前留白，不要預先填寫。

## 效能

| ID | 目標 | 量測方式 | 實測 |
|---|---|---|---|
| PERF-01 | 頁面 API（列專案、開專案、讀結果）p95 < 300ms | `pytest-benchmark` + 部署後 k6 | |
| PERF-02 | 1,000 則留言的完整分析 p95 < 45 秒 | worker 端計時，30 次取樣 | |
| PERF-03 | 10,000 則留言的完整分析 p95 < 6 分鐘 | 同上，10 次取樣 | |
| PERF-04 | 網路圖在 2,000 節點下互動維持 ≥ 30 fps | Chrome DevTools Performance，記錄拖曳 10 秒 | |
| PERF-05 | 首屏 LCP < 2.5s（Cloudflare Pages，4G 節流） | Lighthouse CI | |
| PERF-06 | 情緒推論吞吐 ≥ 80 則/秒（單 CPU worker，batch 32） | 基準測試腳本 | |

## 容量

| ID | 目標 | 量測方式 | 實測 |
|---|---|---|---|
| CAP-01 | 單一分析支援上限 50,000 則留言，超過則拒絕並提示 | 整合測試 | |
| CAP-02 | 20 個並行使用者、5 個並行分析 job 下 PERF-01 不退化 | k6 負載測試 | |
| CAP-03 | 圖形視覺化在 > 2,000 節點時自動降級為抽樣顯示 | 前端單元測試 | |

## 可用性

| ID | 目標 | 量測方式 | 實測 |
|---|---|---|---|
| AVAIL-01 | 月可用度 ≥ 99.0%（不含計畫內維護） | UptimeRobot 監控 `/healthz` | |
| AVAIL-02 | worker 崩潰後 job 不遺失，重啟 60 秒內恢復處理 | 混沌測試：跑分析中 kill worker | |
| AVAIL-03 | 每日資料庫備份，RPO 24 小時，還原演練每季一次 | Neon 自動備份 + 手動還原紀錄 | |

## 安全

| ID | 目標 | 量測方式 | 實測 |
|---|---|---|---|
| SEC-01 | 密碼以 argon2id 雜湊，無明文儲存 | 程式碼審查 + 單元測試 | |
| SEC-02 | 使用者 A 無法讀取使用者 B 的任何專案資源 | 整合測試逐個端點驗證 403 | |
| SEC-03 | 依賴套件無 high / critical 漏洞 | CI 跑 `pip-audit` 與 `npm audit` | |
| SEC-04 | 所有金鑰來自環境變數，儲存庫掃描無洩漏 | CI 跑 `gitleaks` | |
| SEC-05 | 未認證請求分析端點限流 10 req/min/IP | 整合測試 | |

## 可維護性

| ID | 目標 | 量測方式 | 實測 |
|---|---|---|---|
| MAINT-01 | `app/analysis/` 測試覆蓋率 ≥ 90% | `pytest --cov` 在 CI gate | |
| MAINT-02 | 整體後端覆蓋率 ≥ 75% | 同上 | |
| MAINT-03 | `mypy --strict` 在 `app/analysis/` 無錯 | CI gate | |
| MAINT-04 | 演算法層不得 import db / api / http | `import-linter` CI gate | |
| MAINT-05 | 從空機器到本機可運行 ≤ 3 個指令 | README 照做驗證 | |

## 可用性（使用者體驗）

| ID | 目標 | 量測方式 | 實測 |
|---|---|---|---|
| UX-01 | 新使用者從註冊到看到第一張網路圖 ≤ 5 分鐘 | 5 位受測者計時 | |
| UX-02 | 每個錯誤狀態都有具體訊息與下一步動作，無裸露的 500 | 錯誤狀態盤點表 | |
| UX-03 | 主要流程符合 WCAG 2.1 AA 對比度 | axe DevTools 掃描 | |
| UX-04 | 分析進行中的每個階段都有具名的狀態顯示 | 手動驗證對照 ADR-0002 狀態機 | |

## 不在範圍內

明確聲明以下項目本專案不做，避免像原 FYP 那樣宣稱做不到的事：

- 水平自動擴展與負載平衡（單一 API 實例 + 單一 worker）
- 多區域部署
- 即時串流分析（分析是批次的）
- 99.9% 以上的可用度承諾
