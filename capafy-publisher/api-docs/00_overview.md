# Developer Skill API Contract

## 1. Scope

This document describes the seller-side capability surface that the current Developer Skill runtime can rely on. With the seller-side integrated backend documentation and the current runtime code as the source of truth, the current runtime uses the **11 `/agent/**` query/handling endpoints**, **1 account info endpoint**, and **2 login CLI entry points** consolidated here.

`api-docs/index.json` only keeps the version number and runtime entry declarations; interface details are governed by this document.

## 2. Base conventions

### 2.1 Base address

```
https://capafy.ai/api
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

### 2.3 Unified response structure

All business endpoints uniformly return `R<T>`:

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

### 2.4 Common data formats

| Type | Description |
|---|---|
| Date | Common format is `yyyy-MM-dd` |
| Timestamp | Most time fields are Unix millisecond timestamps |
| ISO time | A few authentication-related fields use ISO-8601 strings |
| Amount | Amount fields in the document are usually displayed in USD. |

### 2.5 Web confirmation page mandatory rule

Every `url` field returned by a platform endpoint is a **mandatory human web confirmation step**:

- The returned URL already carries a temporary `draftKey` / temporary token; the caller **jumps directly** without appending parameters itself
- After obtaining the URL, the host **must pause**, waiting for the creator in person to complete confirmation on the web
- Once confirmation is complete, continue running the next stage of publish orchestration; the orchestration internally reads back the current source of truth
- Chat confirmation, local helper script output, scripts submitting the web form on behalf of the user, and reverse-engineering the web endpoint are **not equivalent substitutes**

This is an "axiomatic" rule; it is not repeated below — only "the returned `url` is a web confirmation step (see §2.5)" is mentioned.

## 3. Version update

- Before reading this directory, you should first run `python3 self_update.py --check` to check the version.
- Supports Python >= 3.8; Python 3.11+ uses the standard library `tomllib`, 3.8-3.10 use the built-in TOML fallback shipped with the Skill.
- `self_update.py` currently determines the latest version via a remote install manifest and downloads the zip install package using the `downloadUrl` returned by the manifest.
- If the install manifest carries `sha256` / `sha256Hex` / `sha256_hex`, `self_update.py` will verify the digest of the downloaded zip before extracting; if not carried, the update is still allowed to continue.
- The release package does not carry `requirements.txt`; `self_update.py` skips dependency installation after completing the zip update.
- Windows install mode first copies the updater to the system temp directory and then has an external runner replace the formal skill directory, avoiding the running `self_update.py` locking its own directory.
- Because the release package does not install Python dependencies, PEP 668 / externally-managed-environment should not block self-update.
- The current local version is read preferentially from `.temp/self-update-state.json`; only if no install state file exists yet does it fall back to the `version` in `api-docs/index.json`.
- If `self_update.py --check` returns `check_failed`, continue using the current local version and report the check failure as a notice; do not block the runtime.
- If a later real platform response header carries `X-Skill-Version-Status: outdated` or `deprecated`, the normalized platform response should carry `skill_version_status`; the host should remind the creator whether to update at the next human confirmation point.

## 4. Runtime notes

- The auth entry points are `login-init` / `login-verify` / `login-token`; the publish main-chain entry points are `publish-init` / `publish-configure` / `publish-ship` / `publish-status`. `publish-init` must be passed `--env <env_id>` and `--runtime-dir <absolute_path>`; when a single local skill source directory is specified, additionally pass `--skill-dir <single_skill_dir>`.
- `login-init` may only run after the creator has explicitly consented to the Terms of Service and Privacy Policy; the compliance consent gate only covers email OTP login, not existing token login.
- `--env` is the target runtime; if the subject being published is a `metadata.openclaw` skill, `openclaw` must be passed.
- `--runtime-dir` is the project root / workspace root opened in the host session; do not pass the user home, the publisher skill root, the directory of the skill being published itself, or the parent `skills` directory. Claude Code / Codex passes the current session's project root; OpenClaw passes the current OpenClaw workspace.
- `--skill-dir` is the optional single source directory of the skill being published; it must contain `SKILL.md`; it does not change the semantics of `--runtime-dir`, and cannot be the parent `skills` directory.
- When `publish-init` submits selections, it is recommended to use `--selections-file .temp/confirmed-selections.json` to avoid multi-line JSON being damaged by shell quoting. Selections must be top-level `{ "title", "description", "skills", "plugins", "crons" }`; when updating an existing Agent, also add top-level `agent_id`; do not wrap inside `selection_groups`, and do not pass `workflow_intent`.
- `publish-configure` only accepts a dispositions file path via `--dispositions-file <dispositions.json>` when buyout mode needs the creator to choose how to handle sensitive items; do not pass inline JSON.
- Copyable command form: `python3 packager.py publish-init --env codex --runtime-dir /home/admin_wsl/sunnet/project/agent_store --skill-dir /home/admin_wsl/.agents/skills/skill-vetter --selections-file .temp/confirmed-selections.json`. Example paths must be replaced with the actual paths on the local machine.
- `publish-init` first verifies platform login state; if not logged in or the token has expired, it returns `platform_login_required` / `platform_login_invalid` and does not continue local candidate discovery or submission.
- The CLI additionally handles: token persistence, publish working state, upload, and reporting.
- When troubleshooting, first check the local working state from `publish-status`; the login state only keeps two sources — the environment variable and the current skill's `config.json`.
- `login-token --access-token <token>` is used to change the local fallback token / local platform account; what is written here is the `config.json` under the `capafy-publisher` root directory. It is not a blind write: the command first calls `/agent/account`, and only persists the token and the available account fields (`user_id` / `email` / `name`) after confirming the token is usable. If the current process still sets `CAPAFY_ACCESS_TOKEN`, the runtime will continue to prefer the account in the environment variable.
- When `/agent/*` returns `401`, guide the creator to rerun `login-init` + `login-verify`, or provide a new token and run `login-token`; do not retry automatically.
- Endpoints without CLI wrapping are recommended to be called via `python3 -m capafy_platform.http_cli` (after login, `base_url` and token are injected automatically; no manual parameter passing is needed); statistics, payouts, certification, and refunds are currently called directly on demand.
- `GET /agent/account` is used to verify whether the token supplied to `login-token` is still valid and to read back current account info; it belongs to the account info endpoints, not the publish main chain. The endpoint may return the platform standard `R<T>` response, or a bare account object; the runtime uniformly takes the account object.
- All `url` values returned by the platform are mandatory human web confirmation steps; see §2.5.
- `module_index` is the authoritative directory of the current runtime:
  - Modules with `runtime_active=true` belong to the current runtime input set
  - Modules with `runtime_active=false` are only maintainer context and should not be treated as a runtime contract

## 5. Error code summary

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

## 6. Entry and endpoint index (14 items)

> Numbers S12, S13 are still reserved for the pricing module that has not yet been activated; new endpoints use S23 to avoid renumbering existing entries.

### 6.1 Login CLI and account info (3)

| # | Calling method | Handling method | Description |
|---|---|---|---|
| S01 | `login-init` | CLI internal wrapper | Send login verification code |
| S02 | `login-verify` | CLI internal wrapper | Verify OTP and obtain accessToken |
| S05 | `GET /agent/account` | Internal wrapper of `login-token` | Validate the supplied token and read back account info (account info endpoint; not part of the publish main chain) |

`login-token` first calls `/agent/account` (S05) to verify the token, then persists the verified token to the local `config.json` (the file under the capafy-publisher root) to refresh or switch the local fallback account. On failure, the local `config.json` must remain unchanged.

Handling details:

- A successful response accepts either `{ "code": 0, "data": { ... } }` or directly returns `{ "email": "...", ... }`.
- `data: null` may be treated as an empty account object, but HTTP 401, HTTP 4xx/5xx, non-JSON, non-object, and `code != 0` are all failures.
- Written fields only include local login info needed, e.g., `access_token`, `user_id`, `email`, `name`; the CLI response must not contain `access_token`.

Common S05 account fields:

| Field | Type | Description |
|---|---|---|
| `userId` / `user_id` | string/null | Platform user ID; different response shapes may use different naming. |
| `email` | string/null | Email of the current platform account. |
| `name` | string/null | Display name of the current platform account. |
| `status` | string/null | User status; a valid token usually corresponds to a usable account. |
| `developerVerified` | boolean/int/null | Developer certification status; only used for display and flow prompts, does not replace the KYC query endpoint. |
| `accessToken` | string/null | Login verify response may return; `login-token` validation output must not echo it. |

### 6.2 Agent queries and lifecycle gaps (2)

| # | Calling path | Corresponding endpoint | Description |
|---|---|---|---|
| S03 | Internal adapter layer / host platform capability | `GET /agent/agents` | Seller Agent list |
| S04 | Internal readback inside `publish-*` orchestration | `GET /agent/agents/{agentId}` | Latest version details of an Agent |

#### Common enumerations

| Enumeration | Value | Description |
|---|---|---|
| `agentType` | `run_online` | Hosted-type Agent product, corresponds to local `distribution_mode=cloud_hosted` |
| `agentType` | `download` | Download-type / buyout Skill product, corresponds to local `distribution_mode=buyout` |
| `bizType` | `run_online` / `download` | Business type for file uploads etc.; stays consistent with the current version's `agentType` |
| `agentStatus` | `draft` / `under_review` / `review_rejected` / `online` / `offline` / `banned` | List view status |
| `status` | `0` / `1` / `2` / `3` / `4` / `5` / `6` | The overall agent lifecycle status of the **latest version**: draft, under review, review rejected, review passed/pending listing, listed, expired, delisted. `0` = draft (not submitted); do not misread as "submitted / processing" |
| `auditStatus` | `0` / `1` / `2` / `3` / `4` | Review sub-status of the **latest version** (only meaningful when `status` is in the review-flow segment): review not started, auto-review in progress, manual review in progress, review failed, review passed. `0` = review not started; not "pending review / under review" |
| `agentRuntime` | `openclaw` / `codex` / `opencode` / `claude` | Runtime identifier returned by the platform; this skill currently only maps `claude` / `codex` / `openclaw` to local runtimes |

`status in (0, 2)` is the baseline gate for subsequent publish write operations; the specific next step is determined by the JSON payload returned by `publish-*` commands.

#### `GET /agent/agents`

Use:

- Lets the host decide whether this round is creating a new listing or updating an existing one
- Lets the creator pick an `agentId` to reuse
- The list does not contain the latest full card body; for details call `GET /agent/agents/{agentId}`

Returns as `data.list[]`.

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
| `sales` | int/null | Cumulative sales; usually `null` for non-`online` statuses. |
| `rating` | number/null | Cumulative rating display value. |
| `ratingCount` | int/null | Rating count. |
| `reviewCount` | int/null | Number of reviews. |
| `recentSales` | int/null | Recent sales. |

#### `GET /agent/agents/{agentId}`

Use:

- After the creator completes web confirmation, read the latest persisted card / version
- Refresh `agentVersionId`, `status`, `agentType`, `agentRuntime`
- Refresh the card already saved on the platform, the confirmation bits, and the package status

Path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `agentId` | string | Yes | Target Agent ID; must belong to the current seller. |

Detail fields:

| Field | Type | Description |
|---|---|---|
| `agentId` | string | Agent ID. |
| `agentVersionId` | string | Latest version ID returned this time. |
| `agentPackageId` | string/null | Package ID bound to the current version. |
| `agentType` | string | `run_online` / `download`. |
| `agentRuntime` | string/null | Platform runtime identifier, e.g., `codex`, `claude`, `openclaw`. |
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
| `requiredCredentials` | array/object/null | Credential declarations required for hosted running. |
| `securityPrivacy` | object/null | Security and privacy declarations. |
| `billings` | array | All billing plans for the current version. |
| `agentPackageTestCase` | object/null | Package test case configuration. |
| `packageUrl` | string/null | Download-type or hosted package address. |
| `imageId` | string/null | Image / runtime artifact identifier. |
| `createdAt` | long/null | Version creation time, Unix millisecond timestamp. |
| `updatedAt` | long/null | Version update time, Unix millisecond timestamp. |

Common `billings[]` fields:

| Field | Type | Description |
|---|---|---|
| `lineNo` | int | Billing line number, usually `0`, `1`, `2`. |
| `billingMode` | string | `download`, `hourly`, `subscription`. |
| `currency` | string/null | Currency; currently usually `usd`. |
| `oneTimeFee` | number/null | Download-type one-time purchase price. |
| `hourlyPrice` | number/null | Per-hour price for time-based billing. |
| `hourlyMaxMessageCount` | int/null | Time-based message cap. |
| `minPurchaseHours` | int/null | Minimum purchase hours for time-based billing. |
| `cycleType` | string/null | Subscription cycle: `day`, `week`, `month`. |
| `cyclePrice` | number/null | Per-cycle subscription price. |
| `cycleMaxMessageCount` | int/null | Per-cycle message cap for subscriptions. |

Common `securityPrivacy` fields:

| Field | Type | Description |
|---|---|---|
| `agentBaseModel` | array/null | List of base models used by the Agent. |
| `externalApis` | array/null | List of external API declarations. |
| `externalApis[].serviceName` | string/null | External service name. |
| `externalApis[].purpose` | string/null | Purpose of use. |

Common `agentPackageTestCase` fields:

| Field | Type | Description |
|---|---|---|
| `agentId` | string | Agent ID. |
| `agentVersionId` | string | Version ID. |
| `input` | string/null | Test input. |
| `expectedOutputGroups` | array/null | Expected output groups. |

Stability notes:

- If the platform still returns extra fields, treat them as best-effort additional info inside `raw_data`, not a stable minimum contract.
- The backend source of truth for billing fields is `billings[]`; type determination for the publish main chain only reads `agentType`.
- Confirmed skill selection is based on `workflowInfo.selection_groups`; the raw top-level `selectionGroups` may be empty or missing and is not the basis for confirmation. Runtime code normalizes to top-level `selection_groups` via `get_latest_version()`.

#### Lifecycle gaps

The public main chain only exposes `publish-init` / `publish-configure` / `publish-ship`. Underlying write endpoints are used internally by the orchestration and are not expanded as runtime documentation entry points.

| Operation | Current runtime handling |
|---|---|
| Create new listing | Go through the `publish-init --env <env_id> --runtime-dir <absolute_path> --selections` create path; for an explicit single local skill source, additionally carry `--skill-dir` |
| Version update | Go through the `publish-init --env <env_id> --runtime-dir <absolute_path> --selections` update path with non-empty `agent_id`; for an explicit single local skill source, additionally carry `--skill-dir` |
| Save credentials | Go through `publish-configure`, only `cloud_hosted` |
| Upload and report package | Go through `publish-ship` |
| relist / delist / delete-draft | Pure status actions have no API; the current shipped runtime does not support them |

There is currently no standalone endpoint to rescan the project root within a version; when rescanning is needed, go through the `publish-init` update branch and pass `runtime_dir` again, and if the published subject comes from a separate source directory, pass the same `--skill-dir` again. The next step of the publish pipeline is determined by the JSON payload returned by `publish-configure` / `publish-ship`.

### 6.3 Developer queries (9)

These endpoints currently have no dedicated `packager.py` subcommand; recommended to call directly via `python3 -m capafy_platform.http_cli`. After login, `python3 -m capafy_platform.http_cli` automatically resolves `base_url` from the environment variable, explicit arguments, or default values, and reads `access_token` from `config.json`; only the API path needs to be provided:

```bash
python3 -m capafy_platform.http_cli GET "/agent/sales/trend?startDate=2026-04-20&endDate=2026-04-27"
python3 -m capafy_platform.http_cli POST "/agent/refund/developer/response" --json '{"refundId":"...","developerResponseCode":"other","developerResponse":"..."}'
```

| # | Calling method | Corresponding endpoint | Description |
|---|---|---|---|
| S16 | `python3 -m capafy_platform.http_cli` direct call | `GET /agent/developer/payout-record` | Payout records |
| S17 | `python3 -m capafy_platform.http_cli` direct call | `GET /agent/developer/payout-info` | Payout info |
| S14 | `python3 -m capafy_platform.http_cli` direct call | `GET /agent/sales/trend` | Developer overall sales trend |
| S15 | `python3 -m capafy_platform.http_cli` direct call | `GET /agent/agent/{agentId}/stats` | Single Agent business performance |
| S18 | `python3 -m capafy_platform.http_cli` direct call | `GET /agent/refund/developer/list` | Refund list |
| S19 | `python3 -m capafy_platform.http_cli` direct call | `GET /agent/refund/developer/{refundId}/detail` | Refund details |
| S20 | `python3 -m capafy_platform.http_cli` direct call | `POST /agent/refund/developer/response` | Respond to refund |
| S21 | `python3 -m capafy_platform.http_cli` direct call | `POST /agent/developer/cert/start` | Start certification |
| S22 | `python3 -m capafy_platform.http_cli` direct call | `GET /agent/developer/cert` | Certification details |

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
