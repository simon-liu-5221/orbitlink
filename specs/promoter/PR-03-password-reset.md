# PR-03：重設密碼

**Status**: done
**Actor**: Promoter
**相關 ADR**: ADR-0001（自建 JWT），決定 A1（可抽換寄信後端）

## 目的

使用者忘記密碼時，透過信箱收到的一次性連結設定新密碼，不需要聯絡支援。

## Trigger

使用者在登入頁點「忘記密碼」，輸入 email。

## Pre-conditions

- 帳號存在（不論是否已完成 email 驗證）

## Normal Flow

1. 使用者輸入 email
2. `POST /api/v1/auth/forgot-password`
3. 後端若查到帳號，作廢該帳號先前尚未使用的重設 token，簽發一個新的一次性 token（雜湊後存 `auth_tokens`，`purpose='password_reset'`），寄出含連結的信
4. 不論帳號是否存在，都回 `200` 且訊息相同，不透露帳號存在與否
5. 使用者點信中連結，前端開啟 `/reset-password?token=...`
6. 使用者輸入新密碼，前端即時驗證強度
7. `POST /api/v1/auth/reset-password`
8. 後端消耗 token（單次有效）、驗證密碼強度、以 argon2id 雜湊寫入、撤銷該使用者所有 refresh session（每個裝置都登出）
9. 若該帳號 email 尚未驗證，一併標記為已驗證（點到信中連結已證明擁有信箱）
10. 回 `200`，前端導向登入頁

## Alternative / Exception Flows

| 情況 | 系統行為 | HTTP |
|---|---|---|
| email 未註冊 | 仍回 200、訊息相同、不寄信 | 200 |
| 重設 token 過期（1 小時） | 回 410，`error_code=TOKEN_EXPIRED`，前端提供重新索取 | 410 |
| 重設 token 無效或已使用 | 回 400，`error_code=TOKEN_INVALID` | 400 |
| 新密碼不符強度要求 | 回 422，`error_code=WEAK_PASSWORD`，列出所有未達成的條件 | 422 |
| 同一 token 重放（已成功重設一次） | 回 400 | 400 |
| 一小時內同一 IP 第 6 次索取 | 限流 | 429 |
| 重設成功後用舊密碼登入 | 失敗 | 401 |
| 重設成功後用舊的 refresh cookie 續期 | 失敗 | 401 |

## Post-conditions

- `users.password_hash` 換成新密碼的 argon2id 雜湊
- 該使用者所有 `purpose='refresh'` 且未使用的 `auth_tokens` 都標記 `used_at`
- 使用的重設 token 標記 `used_at`，無法重放
- 若原本 `email_verified=false`，變為 `true`

## Acceptance Criteria

- [x] **AC-1** Given 已註冊的 email，When POST forgot-password，Then 回 200 且 `auth_tokens` 新增一筆 `purpose='password_reset'`、只存 SHA-256 digest 的記錄 — `test_password_reset_api.py::test_forgot_password_issues_a_hashed_single_use_token`
- [x] **AC-2** Given 未註冊的 email，When POST forgot-password，Then 回應的狀態碼與 body 與已註冊的情況完全相同，且沒有寄出任何信 — `test_forgot_password_is_silent_about_unknown_addresses`
- [x] **AC-3** Given 有效的重設 token 與合法的新密碼，When POST reset-password，Then 回 200、`password_hash` 更新為新密碼的 argon2id 雜湊、且 token 無法重放（第二次回 400） — `test_reset_password_changes_the_hash_and_burns_the_token`
- [x] **AC-4** Given 25 小時前產生的重設 token，When POST reset-password，Then 回 410 `error_code=TOKEN_EXPIRED` — `test_expired_reset_token_is_410`
- [x] **AC-5** Given 亂碼或不存在的 token，When POST reset-password，Then 回 400 `error_code=TOKEN_INVALID` — `test_unknown_reset_token_is_400`
- [x] **AC-6** Given 新密碼少於 12 字元或缺少數字，When POST reset-password，Then 回 422 且列出所有未達成的條件（不是只列第一個） — `test_weak_new_password_lists_every_problem`（含斷言：被拒的弱密碼不會消耗 token）
- [x] **AC-7** Given 重設成功，When 用舊密碼登入，Then 回 401；When 用新密碼登入，Then 回 200 — `test_old_password_stops_working_new_one_starts`
- [x] **AC-8** Given 使用者在兩個裝置登入後重設密碼，When 用重設前的 refresh cookie 呼叫 refresh，Then 回 401（所有 session 已撤銷） — `test_reset_revokes_every_existing_session`
- [x] **AC-9** Given 同一帳號連續索取兩次重設連結，When 用第一個 token 重設，Then 回 400（舊 token 已被新的取代） — `test_requesting_a_second_link_invalidates_the_first`
- [x] **AC-10** Given `email_verified=false` 的帳號，When 透過重設連結成功設定新密碼，Then `email_verified` 變為 true 且可以登入 — `test_reset_verifies_an_unverified_account`
- [x] **AC-11** Given 一小時內同一 IP 第 6 次 forgot-password 請求，When POST，Then 回 429 — `test_forgot_password_rate_limit_refuses_the_sixth`

## Out of scope

- 密碼歷史（不允許重用前 N 個舊密碼）
- 強制定期換密碼
- 簡訊 / TOTP 等其他重設管道
- 已登入使用者「修改密碼」（那是 PR-04 個人資料，會複用同一套雜湊與 session 撤銷邏輯）

## 實作備註

- 重設 token 與 email 驗證 token 共用 `auth_tokens` 表與 `_consume_token` 邏輯，只差 `purpose`
- 索取新連結時要作廢舊的未使用連結（AC-9）：`_invalidate_tokens(db, user_id, PASSWORD_RESET)`
- 重設成功一定要 `revoke_all_sessions`：密碼外洩的前提下，攻擊者可能已經有一個 live session，換密碼卻不踢掉等於沒換
- forgot-password 不透露帳號存在（AC-2）：帳號不存在時直接回 200，不寄信。主要成本在 DB 查詢，兩條路徑都會做
- 連結格式：`{FRONTEND_BASE_URL}/reset-password?token=...`，與驗證信一致的風格
- 開發環境的信寄到 MailHog（`EMAIL_BACKEND=smtp`），CI 用預設 log 後端

## 實作結果（M3 PR #2）

- `auth_service.request_password_reset` / `reset_password`；HTTP 層 `POST /auth/forgot-password`、`POST /auth/reset-password`
- `email.password_reset_message(...)`
- 限流 `rate_limit_forgot_password`（5/hr/IP）
- schema `ForgotPasswordRequest`、`ResetPasswordRequest`
- 測試 `tests/integration/test_password_reset_api.py`，AC-1..AC-11 逐條對應
