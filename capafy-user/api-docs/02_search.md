# User Skill API Reference

Shared authentication, units and endpoint index: [00_overview.md](00_overview.md).

## A03 `POST /agent/agents/search`

Search by requirements (Agent)

Search products using a natural-language requirement to obtain Agent IDs, the currently displayed versions, and billing options. This endpoint discovers products; purchases still require the create-order endpoint.

#### Endpoint details

`POST /agent/agents/search`

Guest access is allowed. You may include `Authorization: Bearer am_sk_xxx` or `X-Access-Token: am_sk_xxx`; an explicitly supplied token is still validated.


#### Request parameters

Accepts an optional JSON body and URL query parameters. String fields use nonempty body values first, then query parameters; page/pageSize prefer non-null body values. The language is read from `X-Language-Code` first, then `Accept-Language`.

```json
{
  "query": "Help me write a weekly report",
  "minPrice": "9.9",
  "maxPrice": "99",
  "page": 1,
  "pageSize": 5
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| query | string | Required by business validation | Nonempty requirement description; returns 2013 if absent from all sources |
| minPrice | string | No | Minimum price in USD major units; can be used independently |
| maxPrice | string | No | Maximum price in USD major units; can be used independently |
| page | int | No | Defaults to 1; values below 1 are treated as 1 |
| pageSize | int | No | Defaults to 5; valid range is 1-100, with out-of-range values treated as 10 |

#### Response fields

`data.list` is the result array; it is `[]` when empty. There is no total field.

| Field | Type | Description |
| --- | --- | --- |
| list | array | Agents on the current page |
| searchId | string | Always null in this endpoint |
| languageCode | string | Display language if all results share one language; null for mixed languages |

##### list[]

| Field | Type | Description |
| --- | --- | --- |
| agentId | string | Agent business ID |
| userId | string | Agent owner's user ID |
| agentVersionId | string | Card version ID used for the current display (agentVersionId) |
| title | string | Card title |
| languageCode | string | Language code of the returned content |
| titleSlug | string | Agent title slug |
| tags | string | Tags as a JSON string, matching the version's tags |
| categoryId | int | Category ID |
| agentType | string | Agent type, such as run_online / download |
| billingMode | string | Main billing mode; the first billingMode when multiple billing rows exist |
| billings | array | All billing rows of the displayed version; see the table below |
| needPriceSetting | boolean | Always null in this endpoint |
| supportFreeTrial | boolean | Whether the Agent's latest published version supports a free trial |
| agentCard | object | Card information for the displayed version; see the table below |
| salesVolume | int | Sales volume; 0 if missing |
| rating | number | Rating; 0 if missing |
| creditScore | int | Developer credit score; defaults to 100 if missing |
| canContinueAddInstanceOrPurchase | boolean | Whether more instances can be added or further purchases made |
| urlSuffix | string | Agent detail URL suffix; null when not set |
| developerName | string | Developer name |
| developerSlug | string | Developer profile slug |
| developerAvatarUrl | string | Developer avatar URL |
| developerDescription | string | Developer profile description |
| developerFollowerCount | long | Developer follower count |
| developerTotalSalesCount | long | Developer total sales count |
| developerOnlineAgentCount | long | Number of the developer's currently published Agents |
| developerAverageRating | number | Developer average rating |
| dailyFreeQuotaCount | int | Daily free quota configured for this version: -1 means unselected (no quota granted), 0 means manually disabled, and a positive value enables that many uses per day; this is not the user's remaining quota today |
| index | int | Sort index in banner/featured/curated lists, starting at 0 |
| score | number | Relevance score; hidden from ordinary users in some search buckets and may be null |
| compositeScore | number | Combined reranking score; hidden from ordinary users in some search buckets and may be null |
| pageStatsScore | object | Statistics score object; null when absent or hidden |

##### billings[]

| Field | Type | Description |
| --- | --- | --- |
| agentCardBillingId | string | Specific billing ID; pass it unchanged for purchase or renewal after selecting a plan |
| agentVersionId | string | Agent version ID |
| lineNo | int | Display row number; not an order parameter |
| billingMode | string | Billing mode: download / hourly / subscription |
| isMain | int | Featured option: 0=no, 1=yes |
| minPurchaseHours | int | Minimum hours per purchase |
| hourlyPrice | number | Hourly price in USD major units |
| hourlyMaxMessageCount | int | Hourly message limit; null means unlimited |
| oneTimeFee | number | One-time download price in USD major units |
| cycleType | string | `day` / `week` / `month` / `quarter` / `year` |
| cyclePrice | number | Price per cycle in USD major units |
| currency | string | `usd`; amounts are in USD major units |
| cycleMaxMessageCount | int | Message limit per cycle; null means unlimited |
| containerMode | string | Container mode: on_demand / scheduled |
| frequency | string | Scheduled execution frequency: `high` / `low` |
| cronExpression | string | AWS EventBridge six-field cron: min hour day month weekday year |
| patrolPrompt | string | Patrol instruction |
| supportFreeTrial | int | Free trial supported: 0=no, 1=yes |
| freeTrialCount | int | Number of free trial uses supported |
| freeTrialHours | int | Free trial duration in hours |
| createdAt | long | Creation time as a millisecond timestamp |
| updatedAt | long | Update time as a millisecond timestamp |

##### agentCard

| Field | Type | Description |
| --- | --- | --- |
| agentVersionId | string | Agent version ID; use the complete string returned by the server |
| userId | string | Owner user ID |
| agentId | string | Associated `owner Agent ID` |
| agentType | string | Agent type: run_online / download |
| enableLicense | boolean | Whether License management is enabled for a download product |
| licenseWarningMinCount | int | Low remaining License count warning threshold; applies only to download products |
| status | int | Card version status; 4 means published |
| auditStatus | int | Review substatus: 0=not started, 1=automated review, 2=manual review, 3=failed, 4=passed. |
| imageStatus | int | Image status: 0=not started, 1=building, 2=retrying a failed build, 3=built, -1=build failed |
| healthStatus | int | Health status: 0=healthy, 1=unhealthy |
| imageBuildRetryCount | int | Image build retry count; enters the failed state after 3 retries. |
| agentPackageId | string | Agent Package ID bound to the current version |
| title | string | Title; at most 50 characters |
| shortDescription | string | Short description; at most 500 characters |
| tags | string | Tags as a JSON string |
| enableI18n | boolean | Whether localization is supported |
| defaultLanguageCode | string | Default language code |
| categoryId | int | Primary category ID |
| secondaryCategoryId1 | int | First secondary category ID |
| secondaryCategoryId2 | int | Second secondary category ID |
| supportEmail | string | Developer support email; required |
| concurrencyLimit | int | Concurrency limit |
| estimatedExecutionMinutes | int | Estimated duration per execution in minutes |
| versionNo | int | Increasing version number within the same Agent, starting at 0. |
| versionName | string | Version name supplied by the seller. |
| model | string | Selected model; at most 100 characters. |
| logoUrl | string | Card logo image URL; a complete, accessible URL. |
| privacyPolicyUrl | string | Privacy policy URL |
| agreePrivacyPolicy | boolean | Whether the privacy policy is accepted |
| thinSkillTemplateId | string | Thin Skill Template ID bound to this version; nullable, populated after review passes and the template is generated. |
| freeTrialPolicyVersion | string | Current free trial policy version identifier |
| dailyFreeQuotaCount | int | Daily free quota: -1 means unselected (no quota granted), 0 means manually disabled, and a positive value means enabled. |
| auditCategory | string | Category assigned by the LLM during review: finance, legal, medical, tax; false for other categories |
| autoPublish | boolean | Whether to publish this version automatically after review passes; defaults to true. |
| renewalEnabled | boolean | Whether this version allows subsequent renewals |
| createdAt | long | Creation time as a millisecond timestamp |
| updatedAt | long | Update time as a millisecond timestamp |
| deleted | boolean | Soft deletion flag: false=not deleted, true=deleted |

##### pageStatsScore

| Field | Type | Description |
| --- | --- | --- |
| score | number | Final ranking score |
| trendRelativeScore | number | Relative score on the trending page |
| categoryRelativeScore | number | Relative score on the category page |
| searchRelativeScore | number | Relative score on the search page |
| decayedImpressionCount | number | Total impressions after decay |
| decayedClickCount | number | Total clicks after decay |

#### Query and integration rules

- The server sorts by search relevance and platform statistics, selects the current page, and fills in the latest published cards, all billing rows, and developer display information.
- Entries without an Agent or displayable card are skipped, so a page may contain fewer than pageSize items.
- Select a plan from `billings[].agentCardBillingId`, then call the buyer create-order endpoint.
- To query quotes, use `POST /public/agents/subscription/prices`. It allows guests and recognizes a signed-in user when a Web JWT is supplied. Check success for each item and select the specific billing ID from billing.
- minPrice/maxPrice apply independently and accept numeric strings; invalid numbers cannot be used for price filtering.

#### Successful response example

Only key fields are shown below; the tables above define the complete fields.

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "list": [
      {
        "agentId": "agent_123",
        "agentVersionId": "version_123",
        "title": "Office assistant",
        "languageCode": "en",
        "agentType": "run_online",
        "billingMode": "hourly",
        "billings": [
          {
            "agentCardBillingId": "billing_123",
            "lineNo": 0,
            "billingMode": "hourly",
            "isMain": 1,
            "minPurchaseHours": 1,
            "hourlyPrice": 0.5,
            "hourlyMaxMessageCount": 100,
            "oneTimeFee": null,
            "cycleType": null,
            "cyclePrice": null,
            "currency": "usd",
            "cycleMaxMessageCount": null,
            "containerMode": "on_demand",
            "frequency": null,
            "cronExpression": null,
            "supportFreeTrial": 0,
            "freeTrialCount": null,
            "freeTrialHours": null,
            "patrolPrompt": null,
            "agentVersionId": "version_123",
            "createdAt": 1791763200000,
            "updatedAt": 1791763200000
          }
        ],
        "salesVolume": 12,
        "rating": 4.8,
        "creditScore": 100,
        "canContinueAddInstanceOrPurchase": true,
        "score": 0.9
      }
    ],
    "searchId": null,
    "languageCode": "en"
  }
}
```

#### Failure cases

A missing query returns `PARAM_NOT_FOUND(2013)`. An explicitly supplied invalid Access Token returns an authentication error. Search service failures return the corresponding business errors.

#### Using search results

Each Agent in the response list has its own agentId; use it to view details. billings[].agentCardBillingId is the billing ID submitted for purchase; billingMode determines whether hours is needed. canContinueAddInstanceOrPurchase=false means no more instances or purchases are currently allowed; the server validates this again when creating the order.

The search endpoint returns neither total nor hasMore. Increment page to fetch another page; results may contain fewer than pageSize items, so do not infer the total product count. Treat empty results as an empty array and unconfigured fields as null.

## A04 `GET /agent/agent/agents/{agentId}`

Get published Agent details

View a published product's current version, description, security statements, and billing options. The detail path accepts either the actual Agent ID or its configured URL suffix.

#### Endpoint details

`GET /agent/agent/agents/{agentId}`

Guest access is allowed. You may include `Authorization: Bearer am_sk_xxx` or `X-Access-Token: am_sk_xxx`; an explicitly supplied token is still validated.


#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| agentId | path string | Yes | Agent ID or configured detail URL suffix; the server resolves it to the actual Agent ID first |

No body or query parameters. The Agent must exist, have the main status `online`, and have a latest published version.

#### Successful response

The example expands the main display fields; fields always returned as empty in latestOnlineVersion are also listed individually in this chapter.

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "agentId": "agent_123",
    "agentType": "run_online",
    "name": "Demo Agent",
    "desc": "Automation assistant",
    "agentStatus": "online",
    "latestOnlineVersion": {
      "agentId": "agent_123",
      "agentVersionId": "version_123",
      "agentPackageId": "package_123",
      "agentType": "run_online",
      "agentRuntime": "codex",
      "title": "Demo Agent",
      "shortDescription": "Automation assistant",
      "tags": "[\"office\"]",
      "categoryId": 1,
      "supportEmail": "support@example.com",
      "concurrencyLimit": 5,
      "estimatedExecutionMinutes": 30,
      "versionNo": 3,
      "versionName": "v1.0.2",
      "model": "gpt-4.1",
      "logoUrl": "https://example.com/logo.png",
      "workflowInfo": "Skill instructions",
      "detailedDescription": "Detailed description",
      "chatInputPlaceholder": "Enter your question",
      "versionUpdateInfo": "Version changes",
      "welcomeMessage": "Hello",
      "dailyFreeQuotaCount": 0,
      "securityPrivacy": {
        "agentBaseModel": [
          "gpt-4.1"
        ],
        "externalApis": [
          {
            "serviceName": "api.example.com",
            "purpose": "Query data"
          }
        ]
      },
      "billings": [
        {
          "agentCardBillingId": "billing_123",
          "lineNo": 0,
          "billingMode": "hourly",
          "isMain": 1,
          "minPurchaseHours": 1,
          "hourlyPrice": 0.5,
          "hourlyMaxMessageCount": 100,
          "oneTimeFee": null,
          "cycleType": null,
          "cyclePrice": null,
          "currency": "usd",
          "cycleMaxMessageCount": null,
          "containerMode": "on_demand",
          "frequency": null,
          "cronExpression": null,
          "supportFreeTrial": 0,
          "freeTrialCount": null,
          "freeTrialHours": null,
          "patrolPrompt": null
        }
      ]
    }
  }
}
```

##### data fields

| Field | Type | Description |
| --- | --- | --- |
| agentId | string | Agent ID |
| agentType | string | Product type: run_online / download |
| name | string | Product name |
| desc | string | Product short description |
| agentStatus | string | Product status; `online` on success |
| latestOnlineVersion | object | Details of the published card with the highest `version_no` for this Agent, including extensions, billing, and package data. Sensitive fields such as credentials are cleared at the API layer. |

##### latestOnlineVersion business fields

| Field | Type | Description |
| --- | --- | --- |
| agentId | string | Agent ID |
| agentVersionId | string | Agent version ID |
| agentPackageId | string | Agent Package ID |
| agentType | string | Agent type, run_online / download |
| agentRuntime | string | Agent runtime |
| title | string | Title |
| shortDescription | string | Short description |
| tags | string | Tags as a raw JSON string |
| categoryId | int | Category ID |
| supportEmail | string | Support email |
| concurrencyLimit | int | Concurrency limit |
| estimatedExecutionMinutes | int | Estimated execution duration in minutes |
| versionNo | int | Version number |
| versionName | string | Version name |
| model | string | Model |
| logoUrl | string | Card logo image URL |
| workflowInfo | string | Workflow information |
| detailedDescription | string | Detailed description |
| chatInputPlaceholder | string | Chat input placeholder text. |
| versionUpdateInfo | string | Version update information |
| welcomeMessage | string | Read from the version description only for `run_online`; null when not configured |
| securityPrivacy | object | Security and privacy information |
| billings | array | All billing plans of the current version; select an agentCardBillingId when ordering |

##### Fields always empty in latestOnlineVersion

The following fields always return null in this endpoint; dailyFreeQuotaCount always returns 0.

| Field | Type | Description |
| --- | --- | --- |
| packageSource | string | Always null in this endpoint |
| selectedPackageSource | string | Always null in this endpoint |
| status | int | Always null in this endpoint |
| isConfirmedSkills | int | Always null in this endpoint |
| isConfirmedConfigKeys | int | Always null in this endpoint |
| auditStatus | int | Always null in this endpoint |
| enableI18n | boolean | Always null in this endpoint |
| defaultLanguageCode | string | Always null in this endpoint |
| i18nContents | array | Always null in this endpoint |
| secondaryCategoryId1 | int | Always null in this endpoint |
| secondaryCategoryId2 | int | Always null in this endpoint |
| privacyPolicyUrl | string | Always null in this endpoint |
| agreePrivacyPolicy | boolean | Always null in this endpoint |
| freeTrialPolicyVersion | string | Always null in this endpoint |
| dailyFreeQuotaCount | int | Returns 0 in this endpoint |
| autoPublish | boolean | Always null in this endpoint |
| renewalEnabled | boolean | Always null in this endpoint |
| compactionLimit | int | Always null in this endpoint |
| subagentModel | string | Always null in this endpoint |
| previewPorts | array | Always null in this endpoint |
| requiredCredentials | string | Always null in this endpoint |
| enableLicense | boolean | Always null in this endpoint |
| licenseWarningMinCount | int | Always null in this endpoint |
| availableLicenseCount | int | Always null in this endpoint |
| licenseUsageDescription | string | Always null in this endpoint |
| requestPacks | array | Always null in this endpoint |
| agentPackageTestCase | object | Always null in this endpoint |
| packageUrl | string | Always null in this endpoint |
| imageId | string | Always null in this endpoint |
| hasPendingRejectRecord | boolean | Always null in this endpoint |
| createdAt | long | Always null in this endpoint |
| updatedAt | long | Always null in this endpoint |

##### billings[] fields

| Field | Type | Description |
| --- | --- | --- |
| agentCardBillingId | string | Specific billing ID; pass it unchanged for purchase or renewal after selecting a plan |
| lineNo | int | Display row number; not an order parameter |
| billingMode | string | Billing mode: download / hourly / subscription |
| isMain | int | Featured option: 0=no, 1=yes |
| minPurchaseHours | int | Minimum hours per purchase |
| hourlyPrice | number | Hourly price in USD major units |
| hourlyMaxMessageCount | int | Hourly message limit; null means unlimited |
| oneTimeFee | number | One-time download price in USD major units |
| cycleType | string | `day` / `week` / `month` / `quarter` / `year` |
| cyclePrice | number | Price per cycle in USD major units |
| currency | string | `usd`; amounts are in USD major units |
| cycleMaxMessageCount | int | Message limit per cycle; null means unlimited |
| containerMode | string | Container mode: on_demand / scheduled |
| frequency | string | Scheduled execution frequency: `high` / `low` |
| cronExpression | string | AWS EventBridge six-field cron: min hour day month weekday year |
| supportFreeTrial | int | Free trial supported: 0=no, 1=yes |
| freeTrialCount | int | Number of free trial uses supported |
| freeTrialHours | int | Free trial duration in hours |
| patrolPrompt | string | Patrol instruction |

##### securityPrivacy fields

| Field | Type | Description |
| --- | --- | --- |
| agentBaseModel | array | Base models used by the Agent |
| externalApis | array | External APIs called by the Agent |

`externalApis[]`:

| Field | Type | Description |
| --- | --- | --- |
| serviceName | string | External service name |
| purpose | string | Purpose of the call |

#### Failure cases

| code | Scenario |
| --- | --- |
| 400 | Empty or invalid Agent identifier |
| 2004 | Agent does not exist |
| 2010 | Agent is unpublished or has no published version |
| 1007 | Explicitly supplied Access Token is invalid |

#### Selecting a purchase plan

Select a plan from latestOnlineVersion.billings that matches the purchase intent. download uses oneTimeFee; hourly uses hourlyPrice and minPurchaseHours; subscription uses cyclePrice and cycleType. Submit the selected plan's agentCardBillingId when creating an order, rather than lineNo or agentVersionId.

This endpoint returns the currently published version. To renew an existing instance, query its original plan through agent-version-billing instead of using the latest product version directly.

## A29 `POST /public/agents/subscription/prices`

Query purchase billing plans

Query product quotes and display plans in a batch before purchasing. Each product returns success or failure independently. Querying quotes neither charges the user nor creates an order.

#### Endpoint details

`POST /public/agents/subscription/prices`

Guest access is allowed. This public quote endpoint optionally identifies users through a Web JWT: include `Authorization: Bearer <JWT>` when signed in on the Web; otherwise omit Authorization and query as a guest. This path does not identify users through Agent Access Tokens. `X-Track-Id` can track quote identity.


#### Request parameters

Use the `Content-Type: application/json` header.

```json
{
  "agentIds": [
    "agent_123"
  ],
  "callScene": "NORMAL"
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| agentIds | `array<string>` | Yes | Nonempty Agent ID list; elements cannot all be blank; request order and duplicate IDs are preserved |
| callScene | string | No | Supports NORMAL / UPGRADE_INSTANCE, default NORMAL; this quote endpoint does not switch query branches based on this field |

The server determines the user, tracking ID, and IP from the request context.

#### Response fields

data is an array of quotes. Outer code=0 only means the batch call completed; check success for each Agent.

| Field | Type | Description |
| --- | --- | --- |
| agentId | string | Agent ID |
| success | boolean | Whether the query succeeded for this Agent |
| errorCode | string | Business error identifier for this Agent's failed query; may be null on success |
| errorMessage | string | Failure reason for this Agent's query; may be null on success |
| source | string | Quote source: DEFAULT_BILLING / AB_TEST / PURCHASED / PURCHASED_LATEST |
| planCode | string | Quote plan code, such as A or B; not the billing ID for orders |
| planVersion | int | Quote plan version; null if absent |
| marketGroupId | string | Market group ID for this quote; null if absent |
| marketGroupVersion | int | Market group version; null if absent |
| quoteVersionId | string | Quote version identifier, such as B-P002; null if absent |
| priceOptionId | string | Price option identifier; null if absent |
| styleId | string | Popup style identifier; null if not populated |
| styleVersion | int | Display style version; null if absent |
| styleSource | string | Display style source, GLOBAL / AB_TEST; null if absent |
| billing | array | Specific billing options; use the selected agentCardBillingId when ordering |
| requestPacks | array | Request pack configurations for this quote |
| styleConfig | object | Optional display style configuration; a dynamic object, null when unconfigured |

##### billing[]

| Field | Type | Description |
| --- | --- | --- |
| agentCardBillingId | string | Specific billing ID; pass it unchanged for purchase or renewal after selecting a plan |
| lineNo | int | Display row number; not an order parameter |
| billingMode | string | Billing mode: download / hourly / subscription |
| isMain | int | Featured option: 0=no, 1=yes |
| minPurchaseHours | int | Minimum hours per purchase |
| hourlyPrice | number | Hourly price in USD major units |
| hourlyMaxMessageCount | int | Hourly message limit; null means unlimited |
| oneTimeFee | number | One-time download price in USD major units |
| cycleType | string | `day` / `week` / `month` / `quarter` / `year` |
| cyclePrice | number | Price per cycle in USD major units |
| currency | string | `usd`; amounts are in USD major units |
| cycleMaxMessageCount | int | Message limit per cycle; null means unlimited |
| containerMode | string | Container mode: on_demand / scheduled |
| frequency | string | Scheduled execution frequency: `high` / `low` |
| cronExpression | string | AWS EventBridge six-field cron: min hour day month weekday year |
| supportFreeTrial | int | Free trial supported: 0=no, 1=yes |
| freeTrialCount | int | Number of free trial uses supported |
| freeTrialHours | int | Free trial duration in hours |
| patrolPrompt | string | Patrol instruction |

##### requestPacks[]

| Field | Type | Description |
| --- | --- | --- |
| requestPackId | string | Request pack configuration ID |
| sortNo | int | Display order |
| isMain | int | Featured option: 0=no, 1=yes; defaults to 0; when none is featured, the first request pack by sort order is selected by default |
| price | number | Price |
| currency | string | Currency code |
| messageCount | long | Message count |

#### Successful response example

Only fields needed for purchase are expanded.

```json
{
  "code": 0,
  "msg": "ok",
  "data": [
    {
      "agentId": "agent_123",
      "success": true,
      "errorCode": null,
      "errorMessage": null,
      "source": "DEFAULT_BILLING",
      "planCode": "A",
      "billing": [
        {
          "agentCardBillingId": "billing_123",
          "lineNo": 0,
          "billingMode": "hourly",
          "isMain": 1,
          "minPurchaseHours": 1,
          "hourlyPrice": 0.5,
          "hourlyMaxMessageCount": 100,
          "oneTimeFee": null,
          "cycleType": null,
          "cyclePrice": null,
          "currency": "usd",
          "cycleMaxMessageCount": null,
          "containerMode": "on_demand",
          "frequency": null,
          "cronExpression": null,
          "supportFreeTrial": 0,
          "freeTrialCount": null,
          "freeTrialHours": null,
          "patrolPrompt": null
        }
      ],
      "requestPacks": []
    }
  ]
}
```

#### Proceeding to purchase

Select a quote with success=true and a billing option within it, then pass the complete agentCardBillingId to `/agent/orders/buyer/create`. The field name is the singular `billing`; do not use the display row number lineNo as a billing ID.

Renewal pages use the original plan from the instance billing query rather than replacing a purchased instance's billing identity with this endpoint's latest quote. For failed quote items, display errorCode / errorMessage and do not place an order for those items. This endpoint creates no orders and charges nothing.

#### Handling batch results

Each data[] element corresponds to a requested Agent ID. When success=false, read that item's errorCode and errorMessage; other Agents can still be processed. Checking only the outer code=0 is insufficient. Even when success=true, check that billing includes a purchasable option.

planCode, planVersion, quoteVersionId, and style fields identify the quote for display; they do not replace agentCardBillingId in orders. billing and requestPacks may be empty or absent; clients must not construct billing IDs. requestPacks only describes the quote's request pack configuration; it neither indicates a purchase nor supplies fields for this product's create-order request.
