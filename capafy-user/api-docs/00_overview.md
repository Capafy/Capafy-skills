# User Skill API Overview

## Scope

This directory describes the latest API surface available to the current User Skill runtime. The authoritative source is [`docs/backend_api_docs.md`](../../docs/backend_api_docs.md); the runtime uses only the 27 endpoints consolidated here.

## Base URL

- `https://api.capafy.ai`

## Authentication

- Unauthenticated login endpoints:
  - `POST /auth/login`
  - `POST /auth/login/verify`
- All other user endpoints are under `/agent/**` and require:
  - `Authorization: Bearer {token}`
  - or `X-Access-Token: {token}`
- To verify whether the current token is valid, prefer `GET /agent/account`.

## Runtime Notes

- The real-time conversation entry point is `POST /agent/relay/instances/{instanceId}/messages`.
- The reconnect entry point is `POST /agent/relay/instances/{instanceId}/messages/reconnect`.
- The reconnect endpoint may return two success forms:
  - `text/event-stream`
  - `application/json`, e.g. `{ "status": "no_active_task" }` or `type=timeout`
- Offline message retrieval: `GET /agent/relay/instances/{instanceId}/messages`.
- The offline message endpoint is one-time consumption and currently only returns `type=reply`.
- File capability is currently limited to object storage presigned URLs:
  - `POST /agent/file/presign/upload`
  - `POST /agent/file/presign/download`
- There is **no** `GET /user-skill/version` in the current API documentation.
- There is **no** standalone endpoint to attach files directly to an instance; do not assume that an uploaded object will automatically attach to an instance.

## Error Conventions

- `400` Bad request parameters
- `401` Missing or invalid Access Token
- `404` Target not found, or no active task at the moment
- `409` A message task is already running for the same instance
- `413` Uploaded object too large
- `415` Uploaded object type not supported
- `429` High-frequency or concurrent request limit exceeded

## Endpoint Index (27 total)

### `01_auth.md` — Authentication (2)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A01 | `POST` | `/auth/login` | Send email verification code; receive challengeId |
| A02 | `POST` | `/auth/login/verify` | Verify OTP; receive accessToken |

### `02_search.md` — Search and Details (2)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A03 | `POST` | `/agent/agents/search` | Search Agents by natural-language requirement |
| A04 | `GET` | `/agent/agent/agents/{agentId}` | Get details of a listed Agent |

### `03_order.md` — Orders (5)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A05 | `POST` | `/agent/orders/topup/create` | Create a Credits top-up order |
| A06 | `POST` | `/agent/orders/buyer/create` | Create a buyer order / time-based or expired-subscription renewal |
| A07 | `GET` | `/agent/orders/buyer/list` | View order list |
| A08 | `GET` | `/agent/orders/buyer/{orderId}/detail` | View order detail |
| A09 | `POST` | `/agent/review/agents/{agentId}/review` | Create a review for an Agent (one per buyer) |

### `04_chat.md` — Conversation and Files (6)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A10 | `POST` | `/agent/relay/instances/{instanceId}/messages` | Send message and establish SSE |
| A11 | `POST` | `/agent/relay/instances/{instanceId}/messages/reconnect` | Reconnect SSE |
| A12 | `GET` | `/agent/relay/instances/{instanceId}/messages` | Retrieve offline messages |
| A13 | `POST` | `/agent/relay/instances/{instanceId}/interrupt` | Interrupt current task |
| A14 | `POST` | `/agent/file/presign/upload` | Get upload presigned URL |
| A15 | `POST` | `/agent/file/presign/download` | Get download presigned URL |

### `05_instance.md` — Instances (3)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A16 | `GET` | `/agent/instance` | View instance list |
| A17 | `PATCH` | `/agent/instance/{instanceId}` | Rename an instance |
| A18 | `POST` | `/agent/orders/instance-storage/renew` | Renew instance storage |

### `06_subscription.md` — Subscriptions (3)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A19 | `GET` | `/agent/subscriptions/list` | View subscription list |
| A20 | `POST` | `/agent/subscriptions/{subscriptionId}/cancel` | Cancel subscription |
| A21 | `POST` | `/agent/subscriptions/{subscriptionId}/resume` | Resume subscription |

### `07_download.md` — Download and Versions (3)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A22 | `GET` | `/agent/orders/buyer/{orderId}/download` | Get order download information |
| A23 | `GET` | `/agent/skill/{agentId}/versions` | Query Skill version history |
| A24 | `GET` | `/agent/agent/agents/{agentId}/package` | Download latest Skill package by agentId |

### `08_account.md` — Account (3)

| # | Method | Path | Description |
|---|--------|------|-------------|
| A25 | `GET` | `/agent/account` | Account aggregate info (also used for token verification) |
| A26 | `GET` | `/agent/account/profile` | View user Profile |
| A27 | `PUT` | `/agent/account/profile` | Update user Profile |
