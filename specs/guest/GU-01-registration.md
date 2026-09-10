# GU-01：註冊帳號

**Status**: done
**Actor**: Guest

## 目的

訪客建立帳號以使用分析功能。

## Trigger

訪客在首頁點「註冊」。

## Pre-conditions

- 訪客未登入
- 欲使用的 email 尚未註冊

## Normal Flow

1. 訪客填寫 email、使用者名稱、密碼
2. 前端即時驗證格式與密碼強度
3. `POST /api/v1/auth/register`
4. 後端驗證、以 argon2id 雜湊密碼、建立使用者、寄出驗證信
5. 回 `201`，前端顯示「請至信箱完成驗證」
6. 訪客點擊信中連結，`GET /api/v1/auth/verify?token=...`，帳號啟用
7. 導向登入頁

## Alternative / Exception Flows

| 情況 | 系統行為 | HTTP |
|---|---|---|
| email 已註冊 | 仍回 201 且寄出「此信箱已註冊」的提示信，不透露帳號存在 | 201 |
| 使用者名稱已被使用 | 回 422，提示更換 | 422 |
| 密碼不符強度要求 | 回 422，列出未達成的條件 | 422 |
| email 格式無效 | 回 422 | 422 |
| 驗證 token 過期（24 小時） | 顯示過期頁面並提供重寄 | 410 |
| 驗證 token 無效 | 回 400 | 400 |
| 未驗證的帳號嘗試登入 | 回 403，`error_code=EMAIL_NOT_VERIFIED` | 403 |
| 一小時內同一 IP 第 6 次註冊 | 限流 | 429 |

## Post-conditions

- `users` 表新增一筆，`email_verified=false`、`subscription_plan='trial'`、`trial_ends_at = now + 30 days`
- 密碼欄位為 argon2id 雜湊，無明文
- 驗證信已送出

## Acceptance Criteria

- [x] **AC-1** Given 合法輸入，When POST，Then 回 201 且資料庫新增一筆 `email_verified=false` 的使用者 — `test_auth_api.py::test_register_creates_an_unverified_trial_user`
- [x] **AC-2** Given 任一註冊，When 查詢資料庫，Then `password_hash` 以 `$argon2id$` 開頭且不等於原始密碼 — 同上（斷言 hash 以 `$argon2id$` 開頭且不含明文）
- [x] **AC-3** Given 一個已註冊的 email，When 再次註冊，Then 回應與全新 email 的回應在狀態碼、body 與回應時間上無法區分 — `test_registering_a_known_email_is_indistinguishable`（狀態碼與 body 完全相同；`burn_password_time()` 讓兩條路徑各做一次 argon2 運算）
- [x] **AC-4** Given 密碼少於 12 字元或缺少數字，When POST，Then 回 422 且訊息列出所有未達成的條件（不是只列第一個） — `test_weak_password_lists_every_unmet_requirement`（`password_policy_errors` 回傳 list 而非第一個錯誤）
- [x] **AC-5** Given 有效的驗證 token，When GET verify，Then `email_verified` 變為 true 且 token 失效無法重用 — `test_verify_activates_the_account_and_the_token_is_single_use`
- [x] **AC-6** Given 25 小時前產生的 token，When GET verify，Then 回 410 — `test_expired_verification_token_is_410`
- [x] **AC-7** Given `email_verified=false` 的帳號，When 登入，Then 回 403 且 `error_code=EMAIL_NOT_VERIFIED` — `test_unverified_account_cannot_sign_in`
- [x] **AC-8** Given 一小時內同一 IP 第 6 次註冊請求，When POST，Then 回 429 — `test_register_rate_limit_refuses_the_sixth`（redis 固定視窗，5/hr/IP）
- [x] **AC-9** Given 註冊成功，When 檢查 `trial_ends_at`，Then 等於建立時間加 30 天 — `test_register_creates_an_unverified_trial_user` 一併驗證 `trial_ends_at`

## Out of scope

- OAuth / 社群登入
- 雙因素驗證
- 邀請碼機制
- 付款流程（原 FYP 有「Create Account: Payment」的 use case，重建版把付款移出範圍，試用期結束後帳號轉為唯讀而非收費）

## 實作備註

- AC-3 的時間不可區分是重點：不能因為「email 已存在」就跳過雜湊計算，否則回應時間會洩漏帳號存在。已存在時仍執行一次假的雜湊運算
- 密碼強度規則：至少 12 字元、至少一個數字、至少一個字母。不強制特殊符號（NIST SP 800-63B 建議）
- 驗證 token 用 `secrets.token_urlsafe(32)`，雜湊後存資料庫，不存明文
- 開發環境用 MailHog（`docker compose up mailhog`，收件匣 http://localhost:8025），production 用 Resend 或 SES

## 實作結果（M3 PR #1）

- 密碼雜湊 `app/core/security.py`；驗證/重設/refresh 三種一次性 token 共用 `auth_tokens` 表，資料庫只存 SHA-256 digest
- 寄信是可抽換後端（決定 A1）：預設 `log`（CI 不需任何外部服務），`EMAIL_BACKEND=smtp` 走 MailHog 或正式供應商
- 註冊流程在 `app/services/auth_service.py`，HTTP 層只負責轉錯誤碼，方便對 AC 做服務層測試
