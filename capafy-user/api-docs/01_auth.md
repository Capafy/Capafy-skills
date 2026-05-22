# User Skill API Auth

## A01 `POST /auth/login`

Send an email verification code and receive a one-time `challengeId`.

```http
POST /auth/login
Content-Type: application/json

{
  "loginMethod": "email",
  "email": "user@example.com"
}
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "challengeId": "ch_8KJx2pQm4sRt7UvW9aBc",
    "expiresInSec": 300
  }
}
```

Request fields:

| Field | Type | Required | Description |
|---|---|---|---|
| loginMethod | string | Yes | Login method. The current Agent-side flow only supports `email`. |
| email | string | Yes | Email address that receives the one-time verification code. |

Response fields:

| Field | Type | Description |
|---|---|---|
| code | int | Business code. `0` means success. |
| msg | string | Response message. Usually `ok` on success. |
| data.challengeId | string | One-time login challenge ID. Pass this to A02. |
| data.expiresInSec | int | Challenge lifetime in seconds, measured from successful OTP send time. |

Key points:

- Currently only `loginMethod=email` is supported
- `challengeId` stays valid for `expiresInSec` seconds after the OTP is sent (currently `300` = 5 minutes); within that window the same `challengeId` can be verified repeatedly — wrong codes do **not** consume it and there is no maximum retry count. Only a successful verify or expiration ends the challenge.
- New email addresses are automatically registered upon successful verification

## A02 `POST /auth/login/verify`

Verify OTP and receive an Agent-domain `accessToken`.

```http
POST /auth/login/verify
Content-Type: application/json

{
  "challengeId": "ch_8KJx2pQm4sRt7UvW9aBc",
  "code": "666666",
  "source": "agent"
}
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "userId": "019d3c7f-fe51-7c57-aa2e-8e1055bb36a5",
    "name": "user@example.com",
    "email": "user@example.com",
    "avatarUrl": null,
    "developerVerified": false,
    "status": "active",
    "credits": 0,
    "creditsFrozen": 0,
    "balancePending": 0,
    "balanceConfirmed": 0,
    "balancePayout": 0,
    "currency": "USD",
    "accessToken": "am_sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  }
}
```

Request fields:

| Field | Type | Required | Description |
|---|---|---|---|
| challengeId | string | Yes | Challenge ID returned by A01. |
| code | string | Yes | Verification code received by email. Treat it as a string to preserve leading zeros. |
| source | string | Yes | Must be `agent` for Agent-domain login. |

Response fields:

| Field | Type | Description |
|---|---|---|
| data.userId | string | User ID. |
| data.name | string/null | Display name; often the same as email for newly created users. |
| data.email | string | Verified email address. |
| data.avatarUrl | string/null | Avatar URL, or `null` when not configured. |
| data.developerVerified | boolean | Whether the account is verified as a developer. |
| data.status | string | User status, normally `active`. |
| data.credits | number | Available buyer Credits balance. |
| data.creditsFrozen | number | Frozen Credits amount. |
| data.balancePending | number | Developer pending balance, usually `0` for buyer-only accounts. |
| data.balanceConfirmed | number | Developer confirmed balance, usually `0` for buyer-only accounts. |
| data.balancePayout | number | Developer payable balance, usually `0` for buyer-only accounts. |
| data.currency | string | Account currency display value. |
| data.accessToken | string | Agent-domain access token. Store and use it for `/agent/**` calls. |

Key points:

- `source` must always be `"agent"`
- After a successful login, use `data.accessToken` for all subsequent `/agent/**` requests
- `challengeId` is consumed only on a **successful** verify or when it expires (per A01's `expiresInSec`); a failed verify does not invalidate it, so the caller can re-prompt the user for a new code value and call this endpoint again with the same `challengeId`

## Local Runtime Token Contract

- `scripts/auth.py save <token>` persists the token to `config.json` in the buyer skill directory
- Although the login endpoint returns the field as `accessToken`, `config.json` stores it as `access_token`
- `config.json` also records the verified account fields `user_id` / `email` / `name`
- `scripts/auth.py load` reads with the following priority:
  1. `CAPAFY_ACCESS_TOKEN`
  2. `CAPAFY_TOKEN`
  3. `config.json` in the buyer skill directory
- `capafy_http.py` only auto-injects `Authorization: Bearer {token}` when the request host matches the platform base URL
- `capafy_http.py --access-token <token>` overrides the token for a single request
- `capafy_http.py --no-auto-platform-token` disables auto-injection for a single request
- If the response header contains `X-Skill-Version-Status: outdated|deprecated`, `capafy_http.py` outputs a local notice without relying on a separate version endpoint
