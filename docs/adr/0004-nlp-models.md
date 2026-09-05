# ADR-0004：情緒與毒性模型選擇

**狀態**：已採納

## 背景

原始 FYP 宣稱「multilingual sentiment analysis with toxicity scores」，但整份文件沒有指名任何模型、沒有說支援哪些語言、沒有任何評估數字。重建版必須把這一塊做實，因為這是唯一一個能展示「會用 ML 而不只是會呼叫 API」的地方。

## 決策

### 情緒：`cardiffnlp/twitter-xlm-roberta-base-sentiment`

- 多語（訓練涵蓋 8 種語言，對中英混雜的新加坡 / 台灣留言表現尚可）
- 在社群媒體短文本上微調過，比通用情緒模型更貼近留言的語域
- 三分類：negative / neutral / positive，輸出 softmax 機率而非只有標籤
- CPU 推論，batch size 32，約 100 則留言 / 秒

### 毒性：`unitary/multilingual-toxic-xlm-roberta`

自建而非用 Perspective API，理由是 Perspective 有配額與 ToS 限制，且外部依賴會讓演算法層不再是純的。

### 為什麼不用 VADER

VADER 只支援英文，且是規則式詞典，對表情符號與網路用語的處理已經過時。作為 baseline 保留在評估報告中對照。

### 為什麼不用 LLM API

成本隨留言數線性成長，一次分析數千則留言不划算，而且延遲不可控。若之後要加，定位為「對前 50 則高影響力留言做深度摘要」的加值功能，不是主 pipeline。

## 評估要求

不能只說「我們用了 XLM-RoBERTa」。必須交付：

1. 從真實分析結果中隨機抽 500 則留言，人工標註三分類
2. 報告 accuracy、macro F1、每一類的 precision / recall、混淆矩陣
3. 與 VADER baseline 對照
4. 分語言拆開看表現（英文 / 中文 / 混雜）
5. 誠實寫出失敗案例：反諷、粵語口語、大量表情符號的留言

結果寫入 `docs/algorithm-validation.md`。前端在顯示情緒結果時要一併揭露模型的已知準確率，不要讓使用者以為是絕對真值。

## 後果

- Docker image 會變大（約 +1.5GB），部署時要用 multi-stage build 並考慮模型快取
- 首次推論有模型載入延遲，worker 啟動時預載
- 需要花一到兩天做人工標註，但這份評估是整個專案最能區隔的部分
