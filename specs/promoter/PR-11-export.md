# PR-11：匯出圖形（PNG / PDF / CSV）

**Status**: done
**Actor**: Promoter
**相關 spec**: PR-10（網路圖，PNG 來源）、PR-13（圖表，PDF 報告的一部分）

## 目的

使用者想把分析結果帶走——存一張網路圖截圖、把節點資料丟進 Excel、或印一份完整報告給別人看。

## Trigger

使用者在分析結果頁點擊匯出按鈕。

## Pre-conditions

- 分析已完成且使用者已在結果頁

## Normal Flow

1. 使用者在網路圖區塊點「Export image」，Cytoscape 直接把目前畫面（套用篩選/取樣後看到的那個視圖）轉成 PNG 並下載
2. 使用者點「Export data (CSV)」，下載目前可見節點（同樣套用篩選/取樣）的資料表：暱稱、社群、PageRank、betweenness、參與度、留言數、按讚數、平均情緒、影響力排名
3. 使用者點「Export report (PDF)」，前端把結果頁的幾個區塊（摘要統計、網路圖、三張圖表、影響者/參與度排行）依序截圖組成一份多頁 PDF 並下載
4. 三種匯出都是純前端動作，不打任何新的後端端點

## Alternative / Exception Flows

| 情況 | 系統行為 |
|---|---|
| 節點數為 0（沒有網路圖可看） | Export image / CSV 按鈕停用，不嘗試匯出空畫面 |
| PDF 匯出中某個區塊還沒渲染完成（例如圖表還在載入） | 等待該區塊出現後再截圖，不會截到空白 |
| CSV 欄位含逗號或雙引號（理論上暱稱是純 hex 不會發生，但轉換函式要通用） | 該欄位正確加上雙引號並跳脫 |
| 匯出函式庫（jsPDF / html2canvas）尚未載入 | 點擊當下才動態載入，不影響頁面初始載入速度 |

## Post-conditions

- 無資料庫寫入、無新端點

## Acceptance Criteria

- [x] **AC-1** Given 網路圖已渲染，When 點擊「Export image」，Then 呼叫 Cytoscape 的 `.png()` 並觸發下載，檔名含分析 id — `NetworkGraphSection.tsx::exportImage`（`cy.png({ output: "blob-promise" })`）+ `NetworkGraph.test.tsx::hands the live instance up via onCyReady`
- [x] **AC-2** Given 使用者套用了篩選（例如排除某個社群），When 點擊「Export data (CSV)」，Then CSV 只含篩選後仍可見的節點，不含被篩掉的 — `csv.test.ts::one row per node, in the given order`（`exportCsv` 用 `filtered.nodes`，即篩選/取樣後的清單）
- [x] **AC-3** Given 一般節點資料，When 轉成 CSV，Then 欄位順序固定、標頭正確、數值格式化一致 — `csv.test.ts::header row is fixed and in order` + `null fields become empty...`
- [x] **AC-4** Given 欄位值含逗號或雙引號，When 轉成 CSV，Then 該欄位正確跳脫（純函式，可離線測試不需真的下載） — `csv.test.ts::a field containing a comma/quote/newline is quoted`
- [x] **AC-5** Given 結果頁的區塊已渲染，When 點擊「Export report (PDF)」，Then 依序（統計 → 網路圖 → 圖表 → 影響者 → 參與度）產生對應頁面，順序可驗證（mock html2canvas/jsPDF 驗證呼叫順序） — `pdfReport.test.ts::captures every section in order and adds a page between each`
- [x] **AC-6** Given jsPDF 與 html2canvas 是額外的重依賴，When 頁面首次載入，Then 兩者都不在初始 bundle 裡（動態 import，只在按下匯出按鈕時才載入） — jsPDF/html2canvas 都用 `import()` 動態載入（`pdfReport.ts`），build 後在獨立 chunk（`jspdf.es.min` 390KB、`html2canvas.esm` 201KB），主 bundle 維持 240KB
- [x] **AC-7** Given 節點數為 0，When 檢視匯出按鈕，Then 「Export image」與「Export data」停用（不给點） — `NetworkGraphSection.tsx` 的按鈕 `disabled={!filtered || filtered.nodes.length === 0}`；節點數為 0 時整個區塊提早回傳空狀態，按鈕根本不會渲染

## Out of scope

- 匯出成其他格式（Excel、GraphML、JSON）
- 自訂 PDF 版面（頁首頁尾、浮水印）
- 排程自動匯出 / email 報告
- 伺服器端渲染 PDF（決定：純前端生成，Render free 沒有空間跑 headless browser）

## 實作備註

- **全部前端生成，不碰後端**：PNG 用 Cytoscape 內建的 `cy.png()`；CSV 用已經抓到的節點資料組字串；PDF 用 `html2canvas` 把 DOM 區塊拍成圖片，再用 `jsPDF` 排版組頁
- **匯出「目前看到的」而不是「全部資料」**：PNG 和 CSV 都反映使用者當下的篩選/取樣狀態（PR-10 的 `filterGraph`/`sampleTopByPagerank` 結果），不是重新抓一份未篩選的資料——匯出跟畫面看到的一致，使用者比較不會困惑
- **jsPDF 用 4.x 不是 2.x**：2.x 的 `dompurify` 依賴有一個 critical CVE（`GHSA-55q2-fjhq-7xh7`），雖然這個專案不會用到 jsPDF 觸發該漏洞的 `.html()` 功能，但 `npm audit`（SEC-03）會抓到，直接升級到 4.x 比較乾淨
- PNG／CSV／PDF 三個函式庫都用動態 `import()`，跟 PR-10/PR-13 的 Cytoscape/Recharts 一樣做 code-splitting（PERF-05）

## 實作結果（M5 PR #1）

- `src/features/export/csv.ts`（純函式：`nodesToCsv`、欄位跳脫）
- `src/features/export/pdfReport.ts`（把區塊 ref 依序截圖組 PDF，動態 import html2canvas/jsPDF）
- `src/features/export/downloadFile.ts`（Blob + `<a download>` 小工具）
- 按鈕內嵌在既有元件：PNG/CSV 在 `NetworkGraphSection.tsx`（本來就持有目前篩選/取樣後的節點清單），PDF 在 `AnalysisResultPage.tsx` 頂端（本來就持有每個區塊的 ref）
- `NetworkGraph.tsx` 新增 `onCyReady` callback，把存活的 Cytoscape instance 往上交給 `NetworkGraphSection`，PNG 匯出才拿得到 `cy.png()`
- 測試：`csv.test.ts`（純函式）+ `pdfReport.test.ts`（mock html2canvas/jsPDF 驗證呼叫順序）
