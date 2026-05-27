# User Skill API Search

## A03 `POST /agent/agents/search`

Search Agents by natural-language requirement.

```http
POST /agent/agents/search?query=help me write a weekly report&page=1&pageSize=5
Authorization: Bearer {token}
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "list": [
      {
        "agentId": "1891234567890123456",
        "agentVersionId": "1891234567890999999",
        "title": "Example Agent",
        "tags": "productivity,automation",
        "categoryId": 1,
        "categoryName": "Productivity Tools",
        "agentType": "run_online",
        "billingMode": "hourly",
        "billings": [
          {
            "lineNo": 0,
            "billingMode": "hourly"
          }
        ],
        "model": "gpt-4.1",
        "salesVolume": 12,
        "rating": 48,
        "creditScore": 100,
        "score": 0.92,
        "scoreBreakdown": {},
        "capafyExtra": {},
        "agentCard": {}
      }
    ]
  }
}
```

Query parameters:

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| query | string | Yes | - | Natural-language requirement to search for. |
| minPrice | string/number | No | - | Minimum price. Only takes effect when `maxPrice` is also provided. |
| maxPrice | string/number | No | - | Maximum price. Only takes effect when `minPrice` is also provided. |
| page | int | No | `1` | 1-based page number. |
| pageSize | int | No | `5` | Number of results per page. |

Usage rules:

- `query` is required
- `page` defaults to `1`
- `pageSize` defaults to `5`
- This endpoint uses query parameters and no request body, even though the method is `POST`
- Price filtering only takes effect when both `minPrice` and `maxPrice` are provided
- `scripts/format.py` reads from `data.list`
- `billings` is the complete billing plan array; new integrations should read this field rather than the top-level `billingMode`
- `capafyExtra` is an extended field for Capafy-matched items; only returned when the search matches and the field exists

### Search Result Fields

`data.list[]` combines Agent basics, latest listed card fields, billing data, and Capafy search score fields.

| Field | Type | Description |
|---|---|---|
| agentId | string | Agent ID. Use it with A04 and order creation. |
| agentVersionId | string | Displayed Agent Card version ID for this search result. |
| title | string | Card title shown to buyers. |
| tags | string/null | Comma-separated tag string. |
| categoryId | number/null | Category ID. |
| categoryName | string/null | Category display name. |
| agentType | string | `run_online` or `download`. |
| billingMode | string/null | Compatibility projection from `billings[0].billingMode`. Prefer `billings[]` for new integrations. |
| billings | array | Complete billing plan list for this version, at most 3 entries. See the field reference below. |
| model | string/null | Model name shown on the card when available. |
| salesVolume | number | Sales metric for display/ranking. |
| rating | number | Rating score. Existing responses commonly use an integer scale such as `48` for `4.8`. |
| creditScore | number | Seller credit score. Defaults to `100` when no credit record exists. |
| score | number | Capafy relevance score for this search request. |
| scoreBreakdown | object | Capafy relevance breakdown. Treat the shape as external-service owned. |
| capafyExtra | object/null | Extra Capafy-matched metadata; only present when the search hit includes it. |
| agentCard | object | Latest card detail object. Use A04 when complete details are needed. |

### `billings[]` Field Reference

`billings` is the complete billing plan array for the Agent, with at most 3 entries; `lineNo=0` is the first plan. Reading rules:

**1. Active fields differ by `billingMode`** (use the fields for the current mode; fields for other modes are typically `null` or absent — do not use them for price calculations):

| billingMode | Key Fields | Meaning |
|---|---|---|
| `download` | `oneTimeFee` | One-Time Purchase price (Download Agent) |
| `hourly` | `hourlyPrice` / `hourlyMaxMessageCount` / `minPurchaseHours` | Pay-per-Duration billing; `hours` in the order must be ≥ `minPurchaseHours` (see `03_order.md`) |
| `subscription` | `cycleType` (`week` / `month`) / `cyclePrice` / `cycleMaxMessageCount` | Periodic subscription; `cycleMaxMessageCount` is the message cap per cycle (cycle total). Display the cap with the cycle unit, e.g. weekly subscription with `cycleMaxMessageCount=88` → "up to 88 messages per week". |

Common billing item fields:

| Field | Type | Description |
|---|---|---|
| lineNo | int | Billing line number. Pass this as `billingLineNo` when creating a new order. |
| billingMode | string | `download`, `hourly`, or `subscription`. |
| currency | string/null | Currency, currently usually `usd`. |
| oneTimeFee | number/null | Download Agent one-time purchase price. |
| hourlyPrice | number/null | Hourly price for pay-per-duration billing. |
| hourlyMaxMessageCount | int/null | Message cap for an hourly purchase window, when configured. |
| minPurchaseHours | int/null | Minimum purchase hours for hourly billing. |
| cycleType | string/null | Subscription cycle unit: `week` or `month`. |
| cyclePrice | number/null | Subscription price per cycle. |
| cycleMaxMessageCount | int/null | Message cap per subscription cycle. |
| containerMode | string/null | Runtime scheduling mode, independent of billing. |
| runFrequencyValue | int/null | Scheduled-run frequency value when `containerMode=scheduled`. |
| runFrequencyUnit | string/null | Scheduled-run unit: `minutes`, `hours`, or `days`. |
| dailyRunAt | string/null | Daily run time in `HH:mm` format when applicable. |

**2. Top-level compatibility fields are projections of `billings[0]`**: the top-level `billingMode` / `hourlyPrice` / `oneTimeFee` / `cyclePrice` / `dailyRunAt` mirror the same-named fields in `billings[0]`. Sub-fields such as `hourlyMaxMessageCount` / `cycleType` / `cycleMaxMessageCount` / `containerMode` **have no top-level alias** and must be read from `billings[]`.

**3. Container scheduling fields are independent of billing**: `containerMode` (`on_demand` / `scheduled`) describes the runtime scheduling mode and is **orthogonal to `billingMode`**. When `scheduled`, it is paired with `runFrequencyValue` + `runFrequencyUnit` (`minutes` / `hours` / `days`), or `dailyRunAt` specifying the daily execution time (`HH:mm`).

**4. Other fields**: `patrolPrompt` / `p2aAutoRecognize` are creator-side runtime configurations; buyer scenarios generally do not consume them and they can be treated as opaque pass-through.

Related endpoints:

- `GET /agent/agents/category/{category_id}`: browse listed Agents by category (bypasses Capafy ranking)
- `GET /agent/agent/agents/{agentId}`: listed Agent details (A04)

## A04 `GET /agent/agent/agents/{agentId}`

Get details of a listed Agent. Returns the Agent's basic info and the aggregate card details for the latest listed version.

```http
GET /agent/agent/agents/{agentId}
Authorization: Bearer {token}
```

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "agentId": "agent_xxx",
    "agentType": "run_online",
    "name": "Demo Agent",
    "desc": "Agent description",
    "agentStatus": "online",
    "latestOnlineVersion": {
      "agentVersionId": "av_xxx",
      "agentPackageId": "pkg_xxx",
      "agentType": "run_online",
      "agentRuntime": "codex",
      "title": "Demo Agent",
      "shortDescription": "This is a listed version",
      "tags": "productivity,automation",
      "categoryId": 1,
      "categoryName": "Productivity Tools",
      "model": "gpt-4.1",
      "versionNo": 3,
      "versionName": "v1.0.2",
      "supportEmail": "support@example.com",
      "concurrencyLimit": 5,
      "estimatedExecutionMinutes": 30,
      "logoUrl": "https://example.com/logo.png",
      "workflowInfo": "Skill description",
      "detailedDescription": "Full description content",
      "versionUpdateInfo": "What changed in this version",
      "billings": [
        {
          "lineNo": 0,
          "billingMode": "hourly",
          "hourlyPrice": 0.5,
          "minPurchaseHours": 1
        }
      ],
      "securityPrivacy": {
        "agentBaseModel": ["gpt-4.1"],
        "externalApis": [
          {
            "serviceName": "api.example.com",
            "purpose": "Calls external search service"
          }
        ]
      }
    }
  }
}
```

Path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| agentId | string | Yes | Agent ID from search results, order records, instances, or subscriptions. |

Top-level `data` fields:

| Field | Type | Description |
|---|---|---|
| agentId | string | Agent ID. |
| agentType | string | `run_online` or `download`. |
| name | string | Agent main-table name. |
| desc | string/null | Agent main-table short description. |
| agentStatus | string | Agent listing status. This endpoint only exposes listed/online Agents. |
| latestOnlineVersion | object | Latest listed Agent Card and version details. |

`latestOnlineVersion` fields:

| Field | Type | Description |
|---|---|---|
| agentVersionId | string | Listed version ID. |
| agentPackageId | string/null | Package ID bound to this version, when available. |
| agentType | string | Version type, usually same as top-level `agentType`. |
| agentRuntime | string/null | Runtime identifier such as `codex`, `claude`, or `openclaw`. |
| title | string | Buyer-facing title. |
| shortDescription | string/null | Card short description. |
| tags | string/null | Comma-separated tag string. |
| categoryId | number/null | Category ID. |
| categoryName | string/null | Category display name. |
| model | string/null | Model name displayed to buyers. |
| versionNo | int | Version sequence number. |
| versionName | string/null | Seller-provided version label. |
| supportEmail | string/null | Seller support email. |
| concurrencyLimit | int/null | Seller-configured concurrency limit. |
| estimatedExecutionMinutes | int/null | Estimated execution time in minutes. |
| logoUrl | string/null | Logo URL. |
| workflowInfo | string/object/null | Seller-provided workflow or package description. Treat as display content. |
| detailedDescription | string/null | Full buyer-facing Markdown description. |
| versionUpdateInfo | string/null | Version change notes. |
| billings | array | Complete billing plan list. Prefer this over top-level compatibility fields. |
| securityPrivacy | object/null | Security and privacy declaration. |

Key points:

- Only returns `online` Agents; draft and under-review versions are not exposed
- `requiredCredentials` is not returned; credential configuration is not exposed externally
- `billings` is the complete billing plan array; prefer this field over top-level compatibility fields
- `agentRuntime` is the runtime identifier; `concurrencyLimit` is the concurrency limit; `estimatedExecutionMinutes` is the estimated execution time in minutes
- Agent not found returns `2004`; Agent not online returns `2010`

## Notes

- When the user asks for more details about a specific Agent, prefer A04 for complete information
- Search results already contain basic fields (title, description, rating, billing, etc.) and can be used directly for simple display
