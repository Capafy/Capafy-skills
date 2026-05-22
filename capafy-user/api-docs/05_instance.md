# User Skill API Instance

## A16 `GET /agent/instance`

View the current user's instance list.

```http
GET /agent/instance?status=active
Authorization: Bearer {token}
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "instances": [
      {
        "instanceId": "inst_xxx",
        "agentId": "agent_xxx",
        "agentVersionId": "ver_xxx",
        "agentTitle": "TikTok KOL Deep Analysis",
        "name": "My KOL Analysis",
        "status": "active",
        "createdAt": 1711111111111,
        "expiresAt": 1712222222222
      }
    ]
  }
}
```

Query parameters:

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| status | string | No | `active` | Instance group to query. Supports only `active` and `expired`. |

Response fields:

| Field | Type | Description |
|---|---|---|
| data.instances | array | Instance list. Empty when no instance matches the requested status. |
| data.instances[].instanceId | string | Instance ID. Use this for chat, rename, hourly renewal, subscription renewal, or storage renewal. |
| data.instances[].agentId | string | Agent ID. |
| data.instances[].agentVersionId | string/null | Agent version ID bound to the instance. |
| data.instances[].agentTitle | string/null | Agent title from the related Agent Card. |
| data.instances[].name | string/null | User-facing instance display name. |
| data.instances[].status | string | Aggregated display status, only `active` or `expired`. |
| data.instances[].createdAt | long | Instance creation time in Unix milliseconds. |
| data.instances[].expiresAt | long/null | Expiration/display end time in Unix milliseconds. |

`status` supports only:

- `active`
- `expired`

## A17 `PATCH /agent/instance/{instanceId}`

Update the display name of an instance.

```http
PATCH /agent/instance/{instanceId}
Authorization: Bearer {token}
Content-Type: application/json

{ "name": "My new instance name" }
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": null
}
```

Path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| instanceId | string | Yes | Instance ID to rename. |

Request fields:

| Field | Type | Required | Description |
|---|---|---|---|
| name | string | Yes | New display name. Length must be `1-100` characters after validation. |

Rules:

- `name` is required
- Length: `1–100` characters
- This endpoint only updates the instance name; no other fields are modified

## A18 `POST /agent/orders/instance-storage/renew`

Pay the storage renewal fee for an instance in temporary storage, extending its retention period.

```http
POST /agent/orders/instance-storage/renew
Authorization: Bearer {token}
Content-Type: application/json

{
  "instanceId": "inst_xxx",
  "renewMonths": 3
}
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "orderId": "019e1234abcd5678ef901234567890ab",
    "instanceId": "inst_xxx",
    "status": "paid",
    "stripCheckoutUrl": null,
    "purgeAtAfter": 1777622400000,
    "currency": "usd",
    "amount": 6.00
  }
}
```

Request fields:

| Field | Type | Required | Description |
|---|---|---|---|
| instanceId | string | Yes | Instance ID whose temporary storage retention should be extended. |
| renewMonths | int | Yes | Number of storage months to add. Valid range is `1-12`. |

Response fields:

| Field | Type | Description |
|---|---|---|
| data.orderId | string | Instance storage renewal order ID. |
| data.instanceId | string | Renewed instance ID. |
| data.status | string | Order status. Agent-side Credit flow currently returns `paid`. |
| data.stripCheckoutUrl | string/null | Stripe Checkout URL. Currently `null` because this API uses Credit only. |
| data.purgeAtAfter | long | New planned purge time in Unix milliseconds. |
| data.currency | string | Currency, currently `usd`. |
| data.amount | number | Deducted amount. Equals `renewMonths × 2.00`. |

Rules:

- `instanceId` is required — the ID of the instance to renew
- `renewMonths` is required — number of months to renew; range `1–12`
- Currently only allows renewal of instances that belong to the current user and are still within the temporary storage period (status `idle` and not past `purge_at`)
- Fixed deduction of `2.00 credits` per month; total = `renewMonths × 2.00`
- `currency` is currently fixed to `usd`
- Fixed extension of `30 days` per month; total = `renewMonths × 30 days`
- Agent-side path is fixed to `credit` payment; `stripCheckoutUrl` is always `null` here, and `paymentMethod` cannot be set
- Returns a business error (`code=5007`) when Credits are insufficient; do not assume Stripe payment will be triggered automatically
