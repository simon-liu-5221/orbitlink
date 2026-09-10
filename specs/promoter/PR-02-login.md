# PR-02：登入與工作階段

**Status**: done
**Actor**: Promoter
**相關 ADR**: ADR-0001（自建 JWT），決定 B1（refresh token 放 httpOnly cookie，前端同源代理 `/api/*`）

## 目的

已註冊的使用者登入取得工作階段，並且在不重新輸入密碼的情況下維持登入狀態。

## Trigger

使用者在登入頁輸入 email 與密碼。

## Pre-conditions

- 帳號存在且 `email_verified=true`

## Normal Flow

1. 使用者輸入 email、密碼，可勾選「記住我」
2. `POST /api/v1/auth/login`
3. 後端以 argon2id 驗證密碼，簽發兩個 token
4. 回 `200`，body 含短效 access token（JWT），refresh token 走 `Set-Cookie`（httpOnly）
5. 前端把 access token 留在記憶體，導向專案列表
6. access token 過期時前端呼叫 `POST /api/v1/auth/refresh`，用 cookie 換一組新的
7. 使用者按登出，`POST /api/v1/auth/logout`，refresh token 作廢、cookie 清除

## Alternative / Exception Flows

| 情況 | 系統行為 | HTTP |
|---|---|---|
| 密碼錯誤 | 回 401，`error_code=INVALID_CREDENTIALS` | 401 |
| email 不存在 | 回應與密碼錯誤完全相同 | 401 |
| 帳號未驗證 | 回 403，`error_code=EMAIL_NOT_VERIFIED`（GU-01 AC-7） | 403 |
| refresh token 已用過 / 已撤銷 / 過期 | 回 401，`error_code=INVALID_REFRESH_TOKEN`，前端導回登入頁 | 401 |
| 沒有 refresh cookie | 同上 | 401 |
| 一分鐘內同一 IP 第 11 次登入嘗試 | 限流 | 429 |
| 未帶 access token 存取受保護端點 | 回 401 | 401 |

## Post-conditions

- `auth_tokens` 新增一筆 `purpose='refresh'` 的記錄，只存 SHA-256 digest
- 每次 refresh 舊 token 標記 `used_at`、發新的一組（rotation）
- 登出後該 refresh token 無法再使用

## Acceptance Criteria

- [x] **AC-1** Given 正確的帳密，When POST login，Then 回 200，body 含 access token 與使用者資料，且 `Set-Cookie` 帶 httpOnly 的 refresh token — `test_auth_api.py::test_login_returns_an_access_token_and_sets_the_refresh_cookie`
- [x] **AC-2** Given 密碼錯誤與 email 不存在兩種情況，When POST login，Then 兩者的狀態碼與 body 完全相同 — `test_wrong_password_and_unknown_email_look_the_same`
- [x] **AC-3** Given 未驗證的帳號，When POST login，Then 回 403 且 `error_code=EMAIL_NOT_VERIFIED` — `test_unverified_account_cannot_sign_in`
- [x] **AC-4** Given 勾選「記住我」，When POST login，Then refresh cookie 的 Max-Age 是 30 天而非 7 天 — `test_remember_me_extends_the_refresh_cookie`
- [x] **AC-5** Given 有效的 refresh cookie，When POST refresh，Then 回新的 access token，且**舊的 refresh token 再用會回 401** — `test_refresh_rotates_the_token_and_the_old_one_dies`
- [x] **AC-6** Given 過期的 refresh token，When POST refresh，Then 回 401 — `test_expired_refresh_token_is_401`
- [x] **AC-7** Given 已登出的工作階段，When 用該 refresh token 呼叫 refresh，Then 回 401 — `test_logout_revokes_the_session`
- [x] **AC-8** Given 沒有 token、亂碼 token、或用別的金鑰簽的 token，When 存取受保護端點，Then 都回 401 — `test_analysis_api.py::test_requests_without_a_valid_token_are_401`
- [x] **AC-9** Given 資料庫外洩，When 檢查 `auth_tokens`，Then 沒有任何一筆可直接當作 refresh token 使用（只存 SHA-256 digest）— `test_login_returns_an_access_token_and_sets_the_refresh_cookie` 斷言 cookie 明文查不到對應列
- [x] **AC-10** Given email 大小寫不同，When 登入，Then 仍然成功 — `test_login_is_case_insensitive_on_email`

## Out of scope

- OAuth / 社群登入、雙因素驗證（同 GU-01）
- 「目前登入的裝置」列表與逐一撤銷（`revoke_all_sessions` 已備好，UI 留到 M8）
- 帳號鎖定（改用限流，避免被拿來當阻斷服務的工具）

## 實作備註

- **兩種 token 刻意不同型別**：access token 是短效 HS256 JWT，無狀態、不查資料庫；refresh token 是不透明亂數，資料庫只存 digest，因此可以撤銷。ADR-0001 寫「自建 JWT（access + refresh）」，refresh 那半故意不做成 JWT 就是為了可撤銷
- **決定 B1**：前端靜態站把 `/api/*` rewrite 到 API（見 `render.yaml`），所以 cookie 是第一方的，`SameSite=Lax` 就夠，不需要 `SameSite=None` 加跨站 CORS credentials
- Rotation 讓被竊的 refresh token 最多只能用一次：真正的使用者下次 refresh 時會失敗，異常因此浮出水面
- `login` 順帶做 `check_needs_rehash`，未來調整 argon2 參數時舊帳號會自動升級
- production 開機時會拒絕 `dev-only` 或短於 32 bytes 的 `JWT_SECRET`（`app/core/config.py`），避免用公開的預設值簽章
