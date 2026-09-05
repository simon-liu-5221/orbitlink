# ADR-0001：技術棧選擇

**狀態**：已採納
**日期**：待填

## 背景

原始 FYP 文件的架構圖標示 React + D3.js 的 Web 應用，但開發工具清單列的是 React Native 元件（`@expo/vector-icons`、`react-native-svg`、`react-native-chart-kits`），兩者互相矛盾，後端也只寫「Python」沒有框架。重建版必須先把技術棧釘死。

## 決策

### 後端：FastAPI（而非 Flask / Django）

分析 API 的請求與回應 schema 複雜（巢狀的社群指標、節點屬性），Pydantic 的型別驗證直接省下大量手寫驗證碼，而且自動產生的 OpenAPI 規格可以拿去產生前端 TypeScript 型別，前後端型別一致不用靠人維護。Django 帶的 ORM 與 admin 在這個專案用不到。

### 資料庫：PostgreSQL（而非 Firestore）

原專案用 Firestore。改掉的三個理由：

1. **需要 SQL 聚合。** 「這個頻道過去六次分析的平均情緒走勢」在 Firestore 要在應用層拉全部文件再算，在 Postgres 是一句 `GROUP BY`。原專案的 Predictive Analysis 之所以做不出來，根本原因就是資料層不支援時間序列查詢。
2. **需要 JOIN。** 分析結果、節點、社群、留言之間是明確的關聯結構，不是文件型資料。
3. **JSONB 已經夠彈性。** 需要 schema-less 的地方（分析參數、模型輸出）用 `JSONB` 欄位處理，不需要整個資料庫都是 NoSQL。

代價：失去 Firestore 的即時同步。改用前端輪詢 job 狀態，對這個使用情境足夠。

### 任務佇列：RQ + Redis（而非 Celery / FastAPI BackgroundTasks）

一次分析要抓數千則留言再跑圖演算法與模型推論，時間在分鐘級，不能放在 HTTP request 裡。`BackgroundTasks` 沒有持久化，程序重啟就掉。Celery 功能過剩且設定複雜。RQ 夠用、程式碼可讀、job 狀態可以直接查。

### 前端：React + TypeScript + Vite

TypeScript 是硬要求：分析結果的資料結構深，沒有型別會不斷在 runtime 炸。Vite 取代 CRA。

### 圖形視覺化：Cytoscape.js（而非 D3.js）

D3 是通用視覺化函式庫，畫網路圖要自己實作力導向佈局、縮放、節點選取、效能最佳化。Cytoscape.js 專門為圖形而生，內建多種佈局演算法（cose-bilkent、fcose）、事件系統與 2000+ 節點的效能處理。省下的時間拿去做分析本身。

### 部署：Fly.io（後端）+ Cloudflare Pages（前端）

原專案用 Render，free tier 會冷啟動休眠，示範時第一次請求要等 50 秒。Fly.io 可以設定最小機器數避免休眠，且原生支援跑多個 process（api + worker）。

## 後果

- 需要維護 Docker Compose 讓本機環境可重現
- 前端型別必須由 OpenAPI 產生，API 改動時要記得重跑 `npm run gen:api`
- Postgres + Redis + 兩個部署目標，比單一 Firebase 專案複雜，換來的是可測試性與 SQL 能力的展示
