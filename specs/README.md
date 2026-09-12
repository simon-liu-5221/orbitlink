# 功能規格

每個功能一個檔案。原始 FYP 的 40 個 use case 已經有 Trigger / Pre-condition / Normal Flow / Post-condition，格式很好，這裡直接沿用並補上兩樣它缺的東西：**驗收條件**與**明確排除項**。

## 為什麼要補驗收條件

原文件的 use case 描述了系統「會做什麼」，但沒有定義「做到什麼程度算對」。所以測試計畫只能寫「Fully functional」，29 項全部 100% 通過。驗收條件是把每一條 flow 轉成可以寫成測試的斷言。

## 檔案格式

見 `TEMPLATE.md`。每個 spec 必須有：

- **ID**：`<AREA>-<NN>`，用於 branch 名稱與 commit 訊息
- **Status**：`draft` → `specced` → `in-progress` → `done`
- **Acceptance Criteria**：每一條都能對應到一個測試函式
- **Out of scope**：明確寫下這個 spec 不做什麼，防止範圍蔓延

## 給 Claude Code 的工作方式

```
branch: feat/AN-01-detect-communities
commit: feat(AN-01): add multi-resolution louvain detection
```

一次只做一個 spec。實作前先把 Acceptance Criteria 逐條轉成失敗的測試。

## 索引

### Guest（未註冊使用者）
| ID | 功能 | Status |
|---|---|---|
| GU-01 | 註冊帳號 | done |
| GU-02 | 瀏覽首頁與功能介紹 | draft |
| GU-03 | 檢視使用者評價 | draft |
| GU-04 | 聯絡支援 | draft |

### Promoter（註冊使用者）
| ID | 功能 | Status |
|---|---|---|
| PR-01 | 上傳 YouTube 連結並啟動分析 | done |
| PR-02 | 登入 / 登出 / 記住我 | done |
| PR-03 | 重設密碼 | done |
| PR-04 | 檢視與更新個人資料 | draft |
| PR-05 | 刪除帳號 | draft |
| PR-06 | 個人儀表板 | draft |
| PR-07 | 專案 CRUD（建立 / 重新命名 / 開啟 / 封存 / 刪除） | draft |
| PR-08 | 專案搜尋與篩選 | draft |
| PR-09 | 專案備註 | draft |
| PR-10 | 檢視網路圖 | done |
| PR-11 | 匯出圖形（PNG / PDF / CSV） | draft |
| PR-12 | 提交回饋與評分 | draft |

### Analysis（分析引擎）
| ID | 功能 | Status |
|---|---|---|
| AN-01 | 社群偵測 | done |
| AN-02 | 參與度指標 | done |
| AN-03 | 情緒分析 | done（AC-9 F1 延到 M8）|
| AN-04 | 影響者辨識 | done |
| AN-05 | 分析 job 狀態與進度 | done |
| AN-06 | 歷史趨勢比較 | draft |

### Admin
| ID | 功能 | Status |
|---|---|---|
| AD-01 | 使用者管理（檢視 / 搜尋 / 停權） | draft |
| AD-02 | 檢視回饋與評價 | draft |
| AD-03 | 編輯網站內容 | draft |
