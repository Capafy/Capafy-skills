# User Skill API Subscription

## A20 `GET /agent/subscriptions/list`

View the current user's subscription list.

```http
GET /agent/subscriptions/list?status=active
Authorization: Bearer {token}
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "subscriptions": [
      {
        "subscriptionId": "sub_xxx",
        "agentId": "agent_xxx",
        "agentVersionId": "ver_xxx",
        "agentTitle": "Demo Agent",
        "status": "active",
        "cycle": "monthly",
        "pricePerCycle": 29.00,
        "nextBillingDate": "2026-04-27",
        "paymentMethod": "credit"
      }
    ]
  }
}
```

Query parameters:

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| status | string | No | All displayable statuses | Subscription status filter. Supports `active`, `retrying`, `canceled`, and `expired`. |

Response fields:

| Field | Type | Description |
|---|---|---|
| data.subscriptions | array | Subscription list. |
| data.subscriptions[].subscriptionId | string | Subscription ID. Use it for cancel/resume operations. |
| data.subscriptions[].agentId | string | Agent ID. |
| data.subscriptions[].agentVersionId | string/null | Agent version ID bound to the subscription. |
| data.subscriptions[].agentTitle | string/null | Agent title, when the related version is still available. |
| data.subscriptions[].status | string | Display status: `active`, `retrying`, `canceled`, or `expired`. |
| data.subscriptions[].cycle | string/null | Display cycle, commonly `weekly` or `monthly`; unknown backend values may pass through. |
| data.subscriptions[].pricePerCycle | number/null | Price for each billing cycle. |
| data.subscriptions[].nextBillingDate | string/null | Next billing date or current-cycle end date in `yyyy-MM-dd`. |
| data.subscriptions[].paymentMethod | string/null | Payment method, commonly `credit` or `stripe`. |

`status` supports only:

- `active`
- `retrying`
- `canceled`
- `expired`

## A21 `POST /agent/subscriptions/{subscriptionId}/cancel`

Cancel auto-renewal; the current cycle remains valid.

```http
POST /agent/subscriptions/{subscriptionId}/cancel
Authorization: Bearer {token}
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "subscriptionId": "sub_xxx",
    "status": "canceled",
    "effectiveDate": "2026-04-27"
  }
}
```

Path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| subscriptionId | string | Yes | Subscription ID from A20. |

Response fields:

| Field | Type | Description |
|---|---|---|
| data.subscriptionId | string | Canceled subscription ID. |
| data.status | string | Display status after cancellation, normally `canceled`. |
| data.effectiveDate | string/null | Date when cancellation takes effect. The current cycle remains valid until this date. |

## A22 `POST /agent/subscriptions/{subscriptionId}/resume`

Resume auto-renewal for a canceled but not yet expired subscription.

```http
POST /agent/subscriptions/{subscriptionId}/resume
Authorization: Bearer {token}
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "subscriptionId": "sub_xxx",
    "status": "active",
    "nextBillingDate": "2026-04-27"
  }
}
```

Path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| subscriptionId | string | Yes | Subscription ID from A20. |

Response fields:

| Field | Type | Description |
|---|---|---|
| data.subscriptionId | string | Resumed subscription ID. |
| data.status | string | Display status after resume, normally `active`. |
| data.nextBillingDate | string/null | Next billing date in `yyyy-MM-dd`. |

Rules:

- Only subscriptions with status `canceled` whose current cycle has not yet ended can be resumed
- Resuming continues the current cycle; a new cycle is not started
