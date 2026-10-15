# User Skill API Overview

## Scope

This directory describes the current API contract used by the User Skill runtime, consolidated into 30 method/path combinations here. Maintainers synchronize it from `user_skill/docs/backend_api_docs.md` in the source repository; installed skills rely on the bundled modules below.

## Base URL

Resolve the API base from `scripts/common/defaults.py`, overridden by `CAPAFY_PLATFORM_BASE_URL`. Release builds set the appropriate production or test default.

## Authentication

The HTTP CLI prints platform business responses and exits nonzero when a response contains an error `code`, even if HTTP status is 200. External hosts keep their own response semantics. Use `--json-stdin` when shell quoting would alter a JSON body; it cannot be combined with `--json`.

- Unauthenticated login endpoints:
  - `POST /auth/login`
  - `POST /auth/login/verify`
- Search and listed details allow guests; explicitly supplied Access Tokens are still validated. For guest requests use the HTTP CLI's `--no-auth`.
- Public quotes use optional Web JWT identity. Call `python3 scripts/capafy_http.py POST /public/agents/subscription/prices --no-auth --json '{"agentIds":["<agentId>"],"callScene":"NORMAL"}'` for guest quotes. Never auto-inject the buyer Access Token on this path.
- Other buyer endpoints require `Authorization: Bearer {token}` or `X-Access-Token: {token}`.
- To verify whether the current token is valid, prefer `GET /agent/account`.

## Runtime Notes

- Before user workflows, run `python3 scripts/self_update_v2.py --ensure-supported`. It reads the public `/public/client-agent-version/user` manifest's `minSupportedVersion`, upgrades unsupported versions automatically, and exits nonzero on manifest/update failure or locked pending files. Supported versions only receive an optional update notice. After an update or pending-file promotion, re-read SKILL.md and rerun the gate. `--check` only inspects the version and does not enforce the gate.
- The real-time conversation entry point is `POST /agent/relay/instances/{instanceId}/messages`.
- The reconnect entry point is `POST /agent/relay/instances/{instanceId}/messages/reconnect`.
- The reconnect endpoint may return two success forms:
  - `text/event-stream`
  - `application/json`: `{ "status": "no_active_task" }`
- Real-time and reconnected SSE use `message`, `timeout`, and `done` events. `timeout` is an SSE event, not a separate reconnect JSON response.
- Current-round history: `GET /agent/relay/instances/v2/{instanceId}/messages`, via `scripts/message_history.py`. See `04_chat.md` for parameters and reading rules.
- File capability is currently limited to object storage presigned URLs:
  - `POST /agent/file/presign/upload`
  - `POST /agent/file/presign/download`
- There is **no** `GET /user-skill/version` in the current API documentation.
- There is **no** standalone endpoint to attach files directly to an instance; do not assume that an uploaded object will automatically attach to an instance.

## Shared Response Rules

IDs are complete strings, timestamps are Unix milliseconds, and USD/Credit amounts use main units (10 means USD 10). Ordinary APIs return `{code,msg,data}`; HTTP 200 alone is not success. Relay SSE and successful history/interrupt responses are raw payloads, so do not blindly unwrap `data`. Missing/null usage fields remain unknown. New purchases use the selected `agentCardBillingId`; `lineNo` is display order only.

## Error Conventions

- `400` Bad request parameters
- `401` Missing or invalid Access Token
- `404` Target not found, or no active task at the moment
- `409` A message task is already running for the same instance
- `413` Uploaded object too large, or one V2 history body exceeds 1 MiB (business code 8019)
- `415` Uploaded object type not supported
- `429` High-frequency or concurrent request limit exceeded

## Endpoint Index (30 total)

### `01_auth.md` — Authentication (2)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A01 | `POST` | `/auth/login` | Send email verification code; receive challengeId |
| A02 | `POST` | `/auth/login/verify` | Verify OTP; receive accessToken |

### `02_search.md` — Search, Details and Pricing (3)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A03 | `POST` | `/agent/agents/search` | Search Agents by natural-language requirement |
| A04 | `GET` | `/agent/agent/agents/{agentId}` | Get details of a listed Agent |
| A29 | `POST` | `/public/agents/subscription/prices` | Query public billing quotes; optional Web JWT, never Agent Access Token |

### `03_order.md` — Orders (6)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A05 | `POST` | `/agent/orders/topup/create` | Create a Credits top-up order |
| A30 | `POST` | `/agent/orders/topup/{orderId}/payment-result` | Confirm the original top-up order status |
| A06 | `POST` | `/agent/orders/buyer/create` | Create a buyer order / time-based or expired-subscription renewal |
| A07 | `GET` | `/agent/orders/buyer/list` | View order list |
| A08 | `GET` | `/agent/orders/buyer/{orderId}/detail` | View order detail |
| A09 | `POST` | `/agent/review/agents/{agentId}/review` | Create a review for an Agent (one per buyer) |

### `04_chat.md` — Conversation and Files (6)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A10 | `POST` | `/agent/relay/instances/{instanceId}/messages` | Send message and establish SSE |
| A11 | `POST` | `/agent/relay/instances/{instanceId}/messages/reconnect` | Reconnect SSE |
| A12 | `GET` | `/agent/relay/instances/v2/{instanceId}/messages` | Paginated current-round history |
| A13 | `POST` | `/agent/relay/instances/{instanceId}/interrupt` | Interrupt current task |
| A14 | `POST` | `/agent/file/presign/upload` | Get upload presigned URL |
| A15 | `POST` | `/agent/file/presign/download` | Get download presigned URL |

### `05_instance.md` — Instances (4)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A16 | `GET` | `/agent/instance` | View instance list |
| A17 | `PATCH` | `/agent/instance/{instanceId}` | Rename an instance |
| A18 | `GET` | `/agent/instance/{instanceId}/agent-version-billing` | Get the instance's Agent version, purchased plan, and all version billing plans |
| A19 | `POST` | `/agent/orders/instance-storage/renew` | Renew instance storage |

### `06_subscription.md` — Subscriptions (3)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A20 | `GET` | `/agent/subscriptions/list` | View subscription list |
| A21 | `POST` | `/agent/subscriptions/{subscriptionId}/cancel` | Cancel subscription |
| A22 | `POST` | `/agent/subscriptions/{subscriptionId}/resume` | Resume subscription |

### `07_download.md` — Download and Versions (3)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A23 | `GET` | `/agent/orders/buyer/{orderId}/download` | Get order download information |
| A24 | `GET` | `/agent/skill/{agentId}/versions` | Query Skill version history |
| A25 | `GET` | `/agent/agent/agents/{agentId}/package` | Download latest Skill package by agentId |

### `08_account.md` — Account (3)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A26 | `GET` | `/agent/account` | Account aggregate info (also used for token verification) |
| A27 | `GET` | `/agent/account/profile` | View user Profile |
| A28 | `PUT` | `/agent/account/profile` | Update user Profile |
