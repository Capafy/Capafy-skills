# Developer Skill API Contract

## 1. Scope

This document describes the seller-side capability surface that the current Developer Skill runtime can rely on. The runtime code and seller-side backend contract are the sources of truth for the endpoints and fields listed here.

`api-docs/index.json` only keeps the version number and runtime entry declarations; interface details are governed by this document.

## 2. Base conventions

### 2.1 Base address

```
https://api.capafy.ai
```

### 2.2 Authentication

- Login only goes through `login-init` / `login-verify` / `login-token`; the underlying auth requests are wrapped by the CLI. `login-token` must first call `/agent/account` to validate the supplied token, and may only persist after validation passes; the runtime does not directly call other authentication endpoint paths.
- Before email OTP login, the host must first do the compliance consent gate: take the current platform base URL, strip a trailing `/api` to derive the web base, present `{web_base}/terms-of-service` and `{web_base}/privacy-policy` to the creator, and require explicit consent to the Terms of Service and Privacy Policy. Vague replies (such as "ok", "go", "continue", "next") do not count as explicit consent; `login-init` must not be run before explicit consent. `CAPAFY_ACCESS_TOKEN`, the local `config.json`, or `login-token` use the authentication path after the token has already been issued, and do not repeat the consent prompt.
- `/agent/**` endpoints require an Access Token; one of the following two request headers may be used:

  ```http
  Authorization: Bearer {accessToken}
  ```
  ```http
  X-Access-Token: {accessToken}
  ```

- Token source priority: `CAPAFY_ACCESS_TOKEN` environment variable > local `config.json`.
- Publish orchestration and the platform adapter layer automatically read in this priority; no manual parameter passing is needed.
- **When the user directly pastes a token in the conversation, or requests switching the platform account / user**: run `login-token`. The command first calls `/agent/account` with the token, and only writes to the local `config.json` (the file under the capafy-publisher root) — as the new local fallback account — when a valid account object is returned; 401, network failure, non-JSON, business error codes, or non-object responses are all treated as failure. On failure, the local `config.json` must not be written or overwritten; the command output and error output must not echo the token. The user skill's account file is not touched here; the user skill has its own switching logic.
- This direct-token rule also applies when the token appears in the same natural-language publishing request as a Publisher installation request. Recognize `token:`, `token：`, `access_token:`, `access_token：`, `access token:`, and `access token：` labels case-insensitively. After installation, run `login-token` before `publish-init`; a successful validation replaces the developer Skill (`capafy-publisher`) root `config.json`, while a failed validation leaves it unchanged. Never silently continue with the old local token or use `capafy-user/config.json`.

### 2.3 Response structures

Platform HTTP business endpoints return `R<T>`:

```json
{
  "code": 0,
  "msg": "ok",
  "data": {}
}
```

| Field | Type | Description |
|---|---|---|
| `code` | int | Business code; `0` indicates success |
| `msg` | string | Response message |
| `data` | object / array / null | Business data |

Public `packager.py` commands return one of three CLI envelopes:

```json
{"ok": true, "status": "...", "requires_action": false}
{"ok": true, "status": "...", "requires_action": true, "action_type": "..."}
{"ok": false, "status": "error", "requires_action": false, "error": "..."}
```

- A normal success exits `0` and sets `requires_action: false`.
- An expected pause, including selection and deep scan, exits `0` and sets `requires_action: true`.
- A true failure exits `1`, sets `status: error`, and sets `requires_action: false`.
- Raw HTTP request fields, response fields, and compatibility aliases documented below belong to the adapter/API layer. They are not part of the default CLI output unless a command explicitly documents them.

### 2.4 Common data formats

| Type | Description |
|---|---|
| Date | Common format is `yyyy-MM-dd` |
| Timestamp | Most time fields are Unix millisecond timestamps |
| ISO time | A few authentication-related fields use ISO-8601 strings |
| Amount | Amount fields in the document are usually displayed in USD. |

### 2.5 Web confirmation page mandatory rule

Every confirmation-page `url` returned by a publish or certification workflow is a **mandatory human web confirmation step**:

- The returned URL already carries a temporary `draftKey` / temporary token; the caller **jumps directly** without appending parameters itself
- After obtaining the URL, the host **must pause**, waiting for the creator in person to complete confirmation on the web
- Once confirmation is complete, continue running the next stage of publish orchestration; the orchestration internally reads back the current source of truth
- Chat confirmation, local helper script output, scripts submitting the web form on behalf of the user, and reverse-engineering the web endpoint are **not equivalent substitutes**

This is an "axiomatic" rule; it is not repeated below — only "the returned `url` is a web confirmation step (see §2.5)" is mentioned.

## 3. Runtime notes

- CLI entry points are `login-init`, `login-verify`, `login-token`, `publish-init`, `publish-submit`, `publish-status`, `publish-remote-status`, `publish-list`, and `publish-refresh-url`.
- Login commands never expose tokens, OTPs, raw responses, request bodies, or token-store paths. `login-token` validates through `/agent/account` before persisting the local fallback; `401` requires a fresh login or token.
- `login-init` returns `challenge_id` and `expires_in_sec`. Measure validity from the successful send time and use the returned value rather than a fixed lifetime. A verification attempt consumes the challenge; after failed or expired verification, request a new challenge and email code before retrying.
- `publish-init` requires `--env` and `--runtime-dir`; an explicit single skill source additionally uses `--skill-dir`. Submit top-level `title`, `description`, and `skills` through `--selections-file`; updating an Agent also carries top-level `agent_id`.
- Optional `lang` applies only to a new listing and accepts `en`, `es`, `fr`, `de`, `it`, `ja`, `zh`, `zh-TW`, `ar`, `nl`, `ko`, or `pt` case-insensitively.
- `publish-submit` exposes only `prepare` and `continue_upload`. `prepare` performs or rebuilds local staging and security preparation; `continue_upload` verifies source/staging/reviewed-credential digests, validates, packages, uploads, and calls `POST /agent/agents/{agentId}/uploadPackageCredentials` exactly once. It uses a dispositions file for Download sensitive-value choices and an environment-selection file only for Run Online. `--deep-scan` cannot be combined with either findings-file or environment-selection-file input.
- Use `python3 -m capafy_platform.http_cli` for endpoints without dedicated CLI wrappers; after login, base URL and token are injected automatically. Example:

  ```bash
  python3 -m capafy_platform.http_cli GET "/agent/sales/trend?startDate=2026-04-20&endDate=2026-04-27"
  ```

- Use `--json-stdin` instead of `--json` when shell argument quoting would alter a JSON body (for example, Windows PowerShell). They are mutually exclusive; empty or invalid stdin is rejected before sending a request. For platform responses containing `code`, the HTTP CLI exits nonzero for a business error even when HTTP status is 200; it still prints the response for diagnosis. Generic external responses are not interpreted using the platform business-code convention.

- `publish-status` is local-only. `publish-remote-status` reads the latest platform version. An expired confirmation URL is refreshed through `GET /agent/agents/{agentId}/editLink`.
- The confirmed skill selection is read from `workflowInfo.selection_groups`; the raw top-level `selectionGroups` is not authoritative.

## 4. Error code summary

This table is the **single source of truth** for all error codes. Interfaces return based on `code` in the unified response body; the response does not contain backend enum names; the "symbolic name" below is only an internal backend codename.

| Scenario | Common `code` | Description |
|---|---|---|
| Access Token not provided or invalid | `401` | Unauthorized or Access Token invalid |
| `agentId` does not exist or does not belong to the current seller | `2004` | Agent does not exist, or the current seller has no permission to operate |
| Current version status does not permit this operation | `2019` | E.g., still trying to write publish artifacts when not in editable state `(0, 2)` |
| Query date format error | `400` | Request parameter error |
| Query date range exceeds 90 days | `2021` | Query time range exceeds 90 days |
| Refund ticket does not exist or does not belong to the current seller | `4012` | Refund ticket does not exist, or the current seller has no permission to operate |
| Refund status does not allow current operation | `4013` | Current refund status does not allow this operation |
| Developer refund response has timed out | `4014` | Developer refund response invalid or timed out |
| Developer certification re-initiated | `4037` | Developer certification already completed |

## 5. Entry and endpoint index

### 5.1 Login CLI and account info

| Calling method | Handling method | Description |
|---|---|---|
| `login-init` | CLI internal wrapper | Send login verification code |
| `login-verify` | CLI internal wrapper | Verify OTP and persist the issued access token without echoing it |
| `GET /agent/account` | Internal wrapper of `login-token` | Validate the supplied token and read back account info (account info endpoint; not part of the publish main chain) |

`login-token` first calls `/agent/account` to verify the token, then persists the verified token to the local `config.json` (the file under the capafy-publisher root) to refresh or switch the local fallback account. On failure, the local `config.json` must remain unchanged.

Handling details:

- A successful response accepts either `{ "code": 0, "data": { ... } }` or directly returns `{ "email": "...", ... }`.
- `data: null` may be treated as an empty account object, but HTTP 401, HTTP 4xx/5xx, non-JSON, non-object, and `code != 0` (including `code: null`) are all failures. The explicitly supported raw account object without a `code` field remains compatible.
- Written fields only include local login info needed, e.g., `access_token`, `user_id`, `email`, `name`; the CLI response must not contain `access_token`.
- `login-init`, `login-verify`, and `login-token` never expose the request body, raw response, OTP, token-store path, or issued/supplied token in their public CLI payloads.

Common account fields:

| Field | Type | Description |
|---|---|---|
| `userId` / `user_id` | string/null | Platform user ID; different response shapes may use different naming. |
| `email` | string/null | Email of the current platform account. |
| `name` | string/null | Display name of the current platform account. |
| `status` | string/null | User status; a valid token usually corresponds to a usable account. |
| `developerVerified` | boolean/int/null | Developer certification status; only used for display and flow prompts, does not replace the KYC query endpoint. |
| `accessToken` | string/null | Raw login-verify HTTP response may return this field; no public login CLI command echoes it. |

### 5.2 Agent queries and lifecycle gaps

| Calling path | Corresponding endpoint | Description |
|---|---|---|
| Internal adapter layer / host platform capability | `GET /agent/agents` | Seller Agent list |
| Internal readback inside `publish-*` orchestration | `GET /agent/agents/{agentId}` | Latest version details of an Agent |
| `publish-refresh-url --agent-id <agent_id> [--step init|publish]` | `GET /agent/agents/{agentId}/editLink` | Refresh a human web confirmation URL for the latest editable version; does not rerun init or publish |

#### Common enumerations

| Enumeration | Value | Description |
|---|---|---|
| `agentType` | `run_online` | Run Online Agent product |
| `agentType` | `download` | Download Agent / Skill product |
| `bizType` | `run_online` / `download` | Business type for file uploads etc.; stays consistent with the current version's `agentType` |
| `agentStatus` | `draft` / `under_review` / `review_rejected` / `online` / `offline` / `banned` | List view status |
| `status` | `0` / `1` / `2` / `3` / `4` / `5` / `6` | The overall agent lifecycle status of the **latest version**: draft, under review, review rejected, review passed/pending listing, listed, expired, delisted. `0` = draft (not submitted); do not misread as "submitted / processing" |
| `auditStatus` | `0` / `1` / `2` / `3` / `4` | Review sub-status of the **latest version** (only meaningful when `status` is in the review-flow segment): review not started, auto-review in progress, manual review in progress, review failed, review passed. `0` = review not started; not "pending review / under review" |
| `agentRuntime` | `openclaw` / `codex` / `claude-sdk` / `hermes` | Runtime identifier returned by the platform; this skill maps `claude-sdk` / `codex` / `openclaw` / `hermes` to local runtimes |

`status in (0, 2)` is the baseline gate for subsequent publish write operations; the specific next step is determined by the JSON payload returned by `publish-*` commands.

#### `GET /agent/agents`

Use:

- Lets the host decide whether this round is creating a new listing or updating an existing one
- Lets the creator pick an `agentId` to reuse
- The list does not contain the latest full card body; for details call `GET /agent/agents/{agentId}`

Returns as `data.list[]`.

`publish-list` deliberately normalizes each item to this smaller snake_case CLI contract:

| CLI field | Source HTTP field |
|---|---|
| `agent_id` | `agentId` |
| `name` | `name` |
| `description` | `desc` |
| `agent_type` | `agentType` |
| `agent_status` | `agentStatus` |
| `latest_agent_version_id` | `latestAgentVersionId` |
| `updated_at` | `updatedAt` |

The CLI does not forward list statistics, certification fields, or the raw list response.

List item fields:

| Field | Type | Description |
|---|---|---|
| `agentId` | string | Agent ID; used by the update, details, statistics, etc. endpoints. |
| `name` | string | Agent main table name. |
| `desc` | string/null | Agent main table description. |
| `agentType` | string | `run_online` / `download`. |
| `agentStatus` | string | List view status: `draft`, `under_review`, `review_rejected`, `online`, `offline`, `banned`, etc. |
| `developerVerified` | int/boolean/null | Display value of the current seller's developer certification status. |
| `latestAgentVersionId` | string/null | Latest version ID associated with the current list item; may be empty in some scenarios. |
| `updatedAt` | long/null | Last updated time, Unix millisecond timestamp. |

Additional statistics or certification fields may be returned by the backend but are not part of the normalized `publish-list` contract.

#### `GET /agent/agents/{agentId}`

Use:

- After the creator completes web confirmation, read the latest persisted card / version
- Refresh `agentVersionId`, `status`, `agentType`, `agentRuntime`
- Refresh the card already saved on the platform, the confirmation bits, and the package status

Path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `agentId` | string | Yes | Target Agent ID; must belong to the current seller. |

`publish-remote-status` returns a canonical snake_case `latest_version` object containing only:

- `agent_id`, `agent_version_id`, `agent_package_id`
- `agent_type`, `agent_runtime`
- `platform_status`, `audit_status`
- `is_confirmed_skills`, `is_confirmed_config_keys`
- `version_no`, `version_name`, `title`, `short_description`
- normalized `selection_groups`

It does not forward the full card, billing data, credential payload, package URL, raw response, or duplicate camelCase aliases.

Detail fields:

| Field | Type | Description |
|---|---|---|
| `agentId` | string | Agent ID. |
| `agentVersionId` | string | Latest version ID returned this time. |
| `agentPackageId` | string/null | Package ID bound to the current version. |
| `agentType` | string | `run_online` / `download`. |
| `agentRuntime` | string/null | Platform runtime identifier, e.g., `codex`, `claude-sdk`, `openclaw`, `hermes`. |
| `status` | int | Main status of the latest version; see common enumerations. |
| `auditStatus` | int/null | Review sub-status of the latest version; see common enumerations. |
| `isConfirmedSkills` | int/boolean/null | Whether the web confirmation page has confirmed skill / file selection. |
| `isConfirmedConfigKeys` | int/boolean/null | Whether the hosted credential configuration has been confirmed. |
| `versionNo` | int | Version number. |
| `versionName` | string/null | Version name. |
| `title` | string/null | Card title. |
| `shortDescription` | string/null | Short description. |
| `detailedDescription` | string/null | Detailed description. |
| `versionUpdateInfo` | string/null | Version update notes. |
| `welcomeMessage` | string/null | Welcome message shown after the buyer purchases successfully. |
| `logoUrl` | string/null | Logo URL. |
| `tags` | string/null | Tag string. |
| `categoryId` | number/null | Category ID. |
| `categoryName` | string/null | Category display name. |
| `workflowInfo` | object/string/null | Workflow description and structured selection information saved by the platform; confirmed skill selection is based on the `selection_groups` inside. |
| `createdAt` | long/null | Version creation time, Unix millisecond timestamp. |
| `updatedAt` | long/null | Version update time, Unix millisecond timestamp. |

When `publish-init` creates a new Agent or version, every candidate in the uploaded `workflowInfo.selection_groups` is initialized with `selection: "excluded"`. The first web confirmation page therefore starts with no candidate selected; the creator must explicitly check the skills and workspace documents to publish.

Stability notes:

- Platform fields not listed in the public CLI contracts above are adapter-layer details and may be ignored by the CLI.
- Billing, security/privacy, package-test, and package URL fields may still occur in raw backend details, but the current publisher runtime does not consume them for the publish main chain.
- Confirmed skill selection is based on `workflowInfo.selection_groups`; the raw top-level `selectionGroups` may be empty or missing and is not the basis for confirmation. Runtime code normalizes to top-level `selection_groups` via `get_latest_version()`.

#### `GET /agent/agents/{agentId}/editLink`

Use:

- Refresh an expired human web confirmation URL for the latest editable version
- Resume a paused confirmation step without rerunning `publish-init`, `publish-submit`, or `publish-submit`

Returned `url` is still a mandatory creator web confirmation step; see §2.5. If the latest version is not editable, the endpoint fails instead of creating a new version.

#### `POST /agent/agents/{agentId}/uploadPackageCredentials`

This is the only package/configuration write used by the current Publisher Skill. It replaces the retired `/uploadPackage` and `/credentials` endpoints.

Request body:

| Field | Type | Required | Description |
|---|---|---|---|
| `agentVersionId` | string | Yes | Editable version belonging to the path Agent. |
| `packageUrl` | string | Yes | Uploaded package URL. |
| `requiredCredentials` | string | Run Online only | JSON object encoded as a string. Download omits this field. |

The request contains no `packageHash`, `distributionMode`, `configuration`, `idempotencyKey`, `configRevision`, or staging/scan metadata. `prepare` never calls this endpoint; `continue_upload` calls it only after local validation and upload.

The response is `R<AgentUploadEditLinkVO>` with `agentId`, `agentVersionId`, `agentPackageId`, `agentRuntime`, and `url`. The URL carries `draftKey` and `page=review`; it is the mandatory final human review/configuration page. For Run Online, a successful merged submission resets `isConfirmedConfigKeys` to `0` until the creator reconfirms the keys. Download does not require configuration-key confirmation.

The retired endpoints below return HTTP 426 `SKILL_UPDATE_REQUIRED` and perform no write:

- `POST /agent/agents/{agentId}/uploadPackage`
- `POST /agent/agents/{agentId}/credentials`

#### Lifecycle gaps

The public main chain exposes `publish-init` and the two `publish-submit` actions. Underlying write endpoints are used internally by the orchestration and are not expanded as runtime documentation entry points.

| Operation | Current runtime handling |
|---|---|
| Create new listing | Go through the `publish-init --env <env_id> --runtime-dir <absolute_path> --selections-file <path>` create path; for an explicit single local skill source, additionally carry `--skill-dir` |
| Version update | Go through the `publish-init --env <env_id> --runtime-dir <absolute_path> --selections-file <path>` update path with non-empty `agent_id`; for an explicit single local skill source, additionally carry `--skill-dir` |
| Prepare credentials | `publish-submit --action prepare` freezes reviewed credentials locally; it performs no platform write |
| Upload package and credentials | `publish-submit --action continue_upload` calls the merged endpoint once |
| relist / delist / delete-draft | Pure status actions have no API; the current shipped runtime does not support them |

There is currently no standalone endpoint to rescan the project root within a version; when rescanning is needed, go through the `publish-init` update branch and pass `runtime_dir` again, and if the published subject comes from a separate source directory, pass the same `--skill-dir` again. The next step of the publish pipeline is determined by the JSON payload returned by `publish-submit` / `publish-submit`.

### 5.3 Developer queries

These endpoints currently have no dedicated `packager.py` subcommand; recommended to call directly via `python3 -m capafy_platform.http_cli`. After login, `python3 -m capafy_platform.http_cli` automatically resolves `base_url` from the environment variable, explicit arguments, or default values, and reads `access_token` from `config.json`; only the API path needs to be provided:

```bash
python3 -m capafy_platform.http_cli GET "/agent/sales/trend?startDate=2026-04-20&endDate=2026-04-27"
python3 -m capafy_platform.http_cli POST "/agent/refund/developer/response" --json '{"refundId":"...","developerResponseCode":"other","developerResponse":"..."}'
```

| Calling method | Corresponding endpoint | Description |
|---|---|---|
| `python3 -m capafy_platform.http_cli` direct call | `GET /agent/developer/payout-record` | Payout records |
| `python3 -m capafy_platform.http_cli` direct call | `GET /agent/developer/payout-info` | Payout info |
| `python3 -m capafy_platform.http_cli` direct call | `GET /agent/sales/trend` | Developer overall sales trend |
| `python3 -m capafy_platform.http_cli` direct call | `GET /agent/agent/{agentId}/stats` | Single Agent business performance |
| `python3 -m capafy_platform.http_cli` direct call | `GET /agent/refund/developer/list` | Refund list |
| `python3 -m capafy_platform.http_cli` direct call | `GET /agent/refund/developer/{refundId}/detail` | Refund details |
| `python3 -m capafy_platform.http_cli` direct call | `POST /agent/refund/developer/response` | Respond to refund |
| `python3 -m capafy_platform.http_cli` direct call | `POST /agent/developer/cert/start` | Start certification |
| `python3 -m capafy_platform.http_cli` direct call | `GET /agent/developer/cert` | Certification details |

#### Earnings and payouts

`GET /agent/developer/payout-info` queries payout method, wallet balance, and payout info.

`GET /agent/developer/payout-info` return fields:

| Field | Type | Description |
|---|---|---|
| `payoutMethod` | string/null | Payout method, e.g., `wire_transfer`; `null` when not configured. |
| `currency` | string | Wallet currency; currently usually `usd`. |
| `balancePending` | number | Pending settlement balance, unit USD. |
| `balanceConfirmed` | number | Confirmed balance, unit USD. |
| `balancePayout` | number | Pending payout balance, unit USD. |
| `totalPayout` | number | Cumulative paid-out amount, unit USD. |
| `accountNumber` | string/null | Masked bank account display value, e.g., `****2020`. |

`GET /agent/developer/payout-record` queries the most recent 5 payout records.

`GET /agent/developer/payout-record` return fields:

| Field | Type | Description |
|---|---|---|
| `payoutRecordId` | string | Payout record ID. |
| `payoutMonth` | string | Billing period month, usually `yyyy-MM`. |
| `payoutMethod` | string/null | Payout method, e.g., `wire_transfer`. |
| `status` | string | Payout status: `pending` / `paid`. |
| `amount` | number | Payout amount, unit USD. |
| `currency` | string | Payout record currency; historical empty values are compatible as `usd`. |
| `operatorId` | string/null | Platform operator ID. |
| `paymentReference` | string/null | Payout voucher number / transaction number. |
| `remark` | string/null | Remark info. |
| `paidAt` | long/null | Actual payout time, Unix millisecond timestamp. |
| `createdAt` | long | Creation time, Unix millisecond timestamp. |
| `updatedAt` | long | Update time, Unix millisecond timestamp. |

Current gaps: no paginated payout record query API; payout method modification and verification require going through the web flow.

#### Statistics

`GET /agent/sales/trend` queries the developer's overall sales trend. Query is `startDate` / `endDate`, format `yyyy-MM-dd`; default last 3 days, max 90 days. Returns `startDate`, `endDate`, `days`, `data[]`; `data[]` contains `date`, `orders`, `revenue`, `refundCount`, `refundAmount`, `netRevenue`, `newBuyers`, `returningBuyers`. Range ≤ 7 days returns daily details; range > 7 days returns one summary entry with `date=null`.

`GET /agent/sales/trend` Query parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `startDate` | string | No | Start date, format `yyyy-MM-dd`; default last 3 days. |
| `endDate` | string | No | End date, format `yyyy-MM-dd`. |

`GET /agent/sales/trend` return fields:

| Field | Type | Description |
|---|---|---|
| `startDate` | string | Actual query start date. |
| `endDate` | string | Actual query end date. |
| `days` | int | Number of days in the query range. |
| `data` | array | Trend data list. |
| `data[].date` | string/null | Date in detail mode; `null` in summary mode. |
| `data[].orders` | int | Number of orders. |
| `data[].revenue` | number | Revenue, unit USD. |
| `data[].refundCount` | int | Number of refund tickets. |
| `data[].refundAmount` | number | Refund amount, unit USD. |
| `data[].netRevenue` | number | Net revenue, unit USD. |
| `data[].currency` | string | Currency; currently fixed `usd`. |
| `data[].newBuyers` | int | Number of new buyers. |
| `data[].returningBuyers` | int | Number of returning buyers. |

`GET /agent/agent/{agentId}/stats` queries single Agent performance. Query is `startDate` / `endDate`; default last 7 days, max 90 days. Returns `agentId`, `sales`, `revenue`, `rating`, `reviewCount`, `daily[]`; `daily[]` contains `date`, `orders`, `revenue`. When range > 7 days, `daily` returns an empty array; `rating` / `reviewCount` are not affected by the date range.

`GET /agent/agent/{agentId}/stats` parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `agentId` | string | Yes | Path parameter, target Agent ID. |
| `startDate` | string | No | Query, start date, format `yyyy-MM-dd`; default last 7 days. |
| `endDate` | string | No | Query, end date, format `yyyy-MM-dd`. |

`GET /agent/agent/{agentId}/stats` return fields:

| Field | Type | Description |
|---|---|---|
| `agentId` | string | Agent ID. |
| `startDate` | string | Actual query start date. |
| `endDate` | string | Actual query end date. |
| `sales` | int | Number of settled orders. |
| `revenue` | number | Settled revenue, unit USD. |
| `currency` | string | Currency; currently fixed `usd`. |
| `rating` | number | Current cumulative rating, not affected by the date range. |
| `reviewCount` | int | Current cumulative review count, not affected by the date range. |
| `daily` | array | Daily performance list; empty array when range > 7 days. |
| `daily[].date` | string | Statistic date. |
| `daily[].orders` | int | Number of settled orders for the day. |
| `daily[].revenue` | number | Settled revenue for the day, unit USD. |
| `daily[].currency` | string | Currency; currently fixed `usd`. |

Current gap: no developer-side order details or review management API.

#### Refunds

Refund enumerations:

| Field | Values |
|---|---|
| `arbitrationStatus` | `pending_developer_response` / `pending_arbitration` / `approved` / `rejected` |
| `refundReasonCode` | `accidental_purchase` / `not_working` / `not_as_described` / `no_output` / `other` |
| `developerResponseCode` | `delivered_as_described` / `mostly_used` / `user_error` / `inaccurate_description` / `other` |
| `resolvedReason` | `developer_response_timeout` / `arbitration_decision` |
| `refundPath` | `credit` / `stripe` / `stripe_to_credit` |

`GET /agent/refund/developer/list` queries the refund list, with optional query `arbitrationStatus`.

`GET /agent/refund/developer/list` Query parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `arbitrationStatus` | string | No | Refund arbitration status filter; if not passed, returns all refund tickets. |

Refund list item fields:

| Field | Type | Description |
|---|---|---|
| `refundId` | string | Refund ticket ID. |
| `orderId` | string | Associated order ID. |
| `buyerId` | string | Buyer user ID. |
| `developerId` | string | Developer user ID. |
| `orderType` | string | Order type. |
| `agentId` | string | Agent ID. |
| `agentVersionId` | string | Agent card version ID. |
| `agentCardBillingId` | string | Agent billing plan ID. |
| `agentTitle` | string | Agent title. |
| `agentVersionName` | string | Agent version name. |
| `instanceId` | string/null | Instance ID; may be `null` for orders without an instance. |
| `paymentMethod` | string | Payment method, `credit` / `stripe`. |
| `currency` | string | Currency; currently fixed `usd`. |
| `amount` | number | Refund amount. |
| `originalRefundPath` | string | Original refund path, `credit` / `stripe`. |
| `refundPath` | string/null | Actual refund path, `credit` / `stripe`; `null` before refund execution. |
| `arbitrationStatus` | string | Refund arbitration status. |
| `resolvedReason` | string/null | Refund resolution reason. |
| `refundStatus` | string | Refund execution result. |
| `developerDeadlineAt` | long | Developer response deadline, Unix millisecond timestamp. |
| `developerRespondedAt` | long/null | Developer response time, Unix millisecond timestamp. |
| `arbitrationAt` | long/null | Platform arbitration time, Unix millisecond timestamp. |
| `completedAt` | long/null | Refund completion time, Unix millisecond timestamp. |
| `createdAt` | long | Creation time, Unix millisecond timestamp. |
| `updatedAt` | long | Update time, Unix millisecond timestamp. |

`GET /agent/refund/developer/{refundId}/detail` adds, on top of the list fields, refund reason, developer reply, arbitration, and refund execution fields.

Refund detail path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `refundId` | string | Yes | Refund ticket ID. |

Refund detail extra fields:

| Field | Type | Description |
|---|---|---|
| `refundReasonCode` | string | Buyer refund reason code. |
| `refundReason` | string/null | Buyer refund reason description. |
| `refundReasonAttachments` | array<string>/null | List of buyer refund reason attachment links. |
| `developerResponseCode` | string/null | Developer reply code. |
| `developerResponse` | string/null | Developer reply description. |
| `developerResponseAttachments` | array<string>/null | List of developer reply attachment links. |
| `operatorId` | string/null | Platform operator ID; usually `null` before arbitration. |
| `refundDemotionReason` | string/null | Refund demotion reason; `null` when not demoted. |
| `stripeRefundId` | string/null | Stripe Refund object ID; only present after a refund via the original Stripe payment channel is accepted. |
| `arbitrationNote` | string/null | Platform arbitration note. |
| `paymentAt` | long/null | Order payment time, Unix millisecond timestamp. |

`POST /agent/refund/developer/response` submits the developer response. Request body fields: `refundId` required and at most 36 characters; `developerResponseCode` required; `developerResponse` required and at most 2000 characters; `developerResponseAttachments` optional and at most 5 links.

Developer refund response request body:

| Field | Type | Required | Description |
|---|---|---|---|
| `refundId` | string | Yes | Refund ticket ID, at most 36 characters. |
| `developerResponseCode` | string | Yes | Developer reply code; must be one of the enumeration values. |
| `developerResponse` | string | Yes | Developer reply description, at most 2000 characters. |
| `developerResponseAttachments` | array<string> | No | List of developer reply attachment links, at most 5. |

A successful response is the unified `R<T>`; currently `data` may be treated as `null`.

Business rules: only the `pending_developer_response` status can be responded to; must be submitted before `developerDeadlineAt`; after success the status enters `pending_arbitration`; the developer response is not the final arbitration.

#### KYC / Developer certification

`POST /agent/developer/cert/start` initiates or continues certification; the request body may be empty or `{}`. Returns `url`, which is a web confirmation step; the host must pause and wait for the creator to complete it. Specific error: `4037` means developer certification is already completed; cannot be re-initiated.

`POST /agent/developer/cert/start` return fields:

| Field | Type | Description |
|---|---|---|
| `url` | string | Temporary link to the developer certification page; this is a mandatory web confirmation step, see §2.5. |

`GET /agent/developer/cert` queries certification status.

`GET /agent/developer/cert` return fields:

| Field | Type | Description |
|---|---|---|
| `paymentStatus` | string | Certification fee payment status; currently known values include `pending_payment`, `paid`, `payment_failed`, `refunded`. |
| `kycStatus` | string | KYC status; currently known values include `pending`, `submitted_pending_payment`, `reviewing`, `approved`, `rejected`. |
| `paymentMethod` | string/null | Current certification path, e.g., `wire_transfer`; may be `null` when not started. |
| `country` | string/null | Country code, ISO 3166-1 alpha-2. |
| `certifiedAt` | string/null | Time of certification completion, ISO-8601. |
| `fee` | object | Certification fee info. |
| `fee.currency` | string | Currency; currently fixed `usd`. |
| `fee.amount` | number | Certification fee amount, unit USD. |
| `fee.status` | string | Certification fee status. |
| `fee.paidAt` | string/null | Payment success time, ISO-8601. |

The complete enumerations for `paymentStatus`, `fee.status`, and `kycStatus` are not yet fixed in the current platform documentation; the host should display them according to the actual return without making hard branch assumptions.
