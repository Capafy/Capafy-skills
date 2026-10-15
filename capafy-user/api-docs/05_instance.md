# User Skill API Reference

Shared authentication, units and endpoint index: [00_overview.md](00_overview.md).

## A16 `GET /agent/instance`

List instances (Agent)

View available or retained instances owned by the user to obtain instanceId for message streams, renewal, and renaming.

#### Endpoint details

`GET /agent/instance`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status | query string | No | Defaults to active; supports active / expired |

No body or pagination. active queries only raw active status; expired queries only idle retention status and returns status=expired. Soft-deleted instances are excluded; results are sorted by createdAt descending.

#### Successful response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "instances": [
      {
        "agentVersionId": "version_123",
        "instanceId": "instance_123",
        "agentId": "agent_123",
        "agentTitle": "Office assistant",
        "name": "My assistant",
        "status": "active",
        "createdAt": 1791763200000,
        "expiresAt": 1791849600000
      }
    ]
  }
}
```

data.instances is an array; [] when no records exist.

| Field | Type | Description |
| --- | --- | --- |
| agentVersionId | string | Agent version ID. |
| instanceId | string | Instance ID. |
| agentId | string | Agent ID. |
| agentTitle | string | Title of the Agent version associated with the instance; null if missing |
| name | string | Instance displayName |
| status | string | Returned group active / expired, corresponding to raw active / idle respectively |
| createdAt | long | Creation time as a millisecond timestamp. |
| expiresAt | long | Instance idleAt as a millisecond timestamp; may be null if not populated |

#### Integration rules and failure cases

For renewal, query instance billing with instanceId, then submit to the purchase endpoint. Unsupported status values return BAD_REQUEST(400); missing or invalid Access Tokens return authentication errors.

#### Using the list

data.instances=[] means no instances in the current group. active only indicates instance availability; it does not establish whether a task is running. Confirm task status through the message endpoints. expired corresponds to idle retention; renewal or reactivation conditions must be met before sending further messages.

createdAt is for displaying creation time; expiresAt is the expiration of current runtime availability and may be null. This endpoint does not return the retention deadline purgeAt; the storage-fee response provides the updated deadline as purgeAtAfter.

## A18 `GET /agent/instance/{instanceId}/agent-version-billing`

Query instance billing plans (Agent)

Before renewing, obtain the instance's actually purchased plan, available renewal options, and version renewal policy instead of using a new-purchase quote for an existing instance.

#### Endpoint details

`GET /agent/instance/{instanceId}/agent-version-billing`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| instanceId | path string | Yes | Instance ID owned by the current user |

No body or query parameters. Used to display the purchased plan, renewal policy, and available options before renewal.

#### Response fields

| Field | Type | Description |
| --- | --- | --- |
| instanceId | string | Instance ID |
| agentId | string | Agent ID |
| agentVersionId | string | Agent version ID |
| versionNo | int | Version number |
| versionName | string | Version name |
| status | int | Numeric Agent version status; differs from instance status |
| renewalEnabled | boolean | Whether the Agent version bound to the current instance allows renewal |
| billing | object | Billing option actually purchased for the original instance; may be null for daily-free instances with no billing binding |
| paymentMethod | string | Current subscription payment method; null for nonsubscription billing or no matching subscription |
| subscriptionId | string | Subscription ID for the current instance; null for nonsubscription billing or no matching subscription |
| subscriptionStatus | string | Subscription relationship status for the current instance; null for nonsubscription instances or no matching subscription |
| freeTrialDays | int | Current subscription free trial days; null outside subscription scenarios |
| billings | array | Renewal billing options: developer plans use the original Agent version; experiment plans use the original policy, plan, and quote version |
| dailyFreeQuotaEnabled | boolean | Whether daily free quota is enabled for the instance; this does not indicate remaining uses today |
| dailyFreeQuotaExpireAt | long | Deadline through which daily free quota keeps the instance available, as a millisecond timestamp; not the end of today's entitlement |

##### billing / billings[]

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

#### Successful response example

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "instanceId": "instance_123",
    "agentId": "agent_123",
    "agentVersionId": "version_123",
    "versionNo": 1,
    "versionName": "v1.0.0",
    "status": 4,
    "renewalEnabled": true,
    "billing": {
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
    },
    "paymentMethod": null,
    "subscriptionId": null,
    "subscriptionStatus": null,
    "freeTrialDays": null,
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
    ],
    "dailyFreeQuotaEnabled": false,
    "dailyFreeQuotaExpireAt": null
  }
}
```

#### Proceeding to renewal

- renewalEnabled=false prevents manual renewal or reactivation of that version.
- For hourly renewal, omit billing ID or pass billing.agentCardBillingId; a different hourly option cannot be selected.
- For subscription renewal, choose an eligible subscription ID from billings; the purchase endpoint revalidates original plan ownership and subscription status.
- Renew through `/agent/orders/buyer/create` with instanceId; hourly renewal also requires hours.
- This endpoint only queries; it creates no orders and charges nothing.

#### Failure cases

A missing instance or one belonging to another user returns 8001. A missing associated Agent version returns 2004; unavailable historical billing configuration returns ORDER_BILLING_MODE_INVALID(4005). A missing or invalid Access Token returns an authentication error.

#### Validation before renewal

Read renewalEnabled first; false means the bound version prohibits subsequent renewal. Then read billing.agentCardBillingId and billingMode. Hourly renewal uses the original billing ID; subscription renewal selects an ID from billings that meets the original plan constraints. The create-order endpoint performs the final purchase validation.

Use subscriptionId, subscriptionStatus, and paymentMethod only when the matching subscription exists; they are null for nonsubscription instances. For a canceled subscription whose current period has not ended, prefer resuming automatic renewal if the user wants it. Recreating an expired subscription uses the create-order endpoint with instanceId.

## A17 `PATCH /agent/instance/{instanceId}`

Rename an instance (Agent)

Change the display name of an instance owned by the user. Success returns empty business data; update the local display and reread the list when needed.

#### Endpoint details

`PATCH /agent/instance/{instanceId}`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

Use Content-Type: application/json.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| instanceId | path string | Yes | Instance ID owned by the current user |
| name | body string | Yes | Nonempty and not all whitespace; 1-50 characters |

```json
{
  "name": "My office assistant"
}
```

#### Successful response

```json
{
  "code": 0,
  "msg": "ok",
  "data": null
}
```

This endpoint returns data=null on success. Trim surrounding whitespace before saving; query the instance list again after renaming if needed.

#### Failure cases

| code | Scenario |
| --- | --- |
| 400 | Empty or all-whitespace name, more than 50 characters, or invalid JSON |
| 8001 | Instance missing or not owned by the current user |
| 401 / 1007 | Missing or invalid Access Token |

Parameter validation errors are returned in msg, such as `name must not be blank` and `name length must be between 1 and 50 characters`; actual spacing follows the response.

#### Name validation and refresh

The name must contain non-whitespace content and be at most 50 characters. Trim surrounding whitespace before saving. Success returns data=null, so instanceId, name, and updatedAt cannot be read from this response. Query the instance list to confirm the final name.

## A19 `POST /agent/orders/instance-storage/renew`

Instance storage fee (Agent)

Extend retention for an idle instance to prevent cleanup at expiration. The fee extends storage time; resuming execution requires a separate runtime purchase.

#### Endpoint details

`POST /agent/orders/instance-storage/renew`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

Use Content-Type: application/json; payment always uses Credit.

```json
{
  "instanceId": "instance_123",
  "renewMonths": 3
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| instanceId | string | Yes | Instance ID owned by the user; cannot be empty |
| renewMonths | int | Yes | Retention months, from 1 to 12 |

#### Business rules

- Only idle retained instances qualify; purgeAt must exist and the current time must be strictly earlier than purgeAt.
- Storage costs 2 Credits per month; each month adds 30 days. Total fee = renewMonths * 2.
- After successful deduction, purgeAtAfter = original purgeAt + renewMonths * 30 days.
- This extends instance retention. To resume execution, renew through the buyer create-order endpoint.
- Concurrent requests for the same instance may return 429. This endpoint does not process Idempotency-Key; avoid duplicate submissions.

#### Successful response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "orderId": "2097948161935953921",
    "instanceId": "instance_123",
    "status": "paid",
    "stripCheckoutUrl": null,
    "purgeAtAfter": 1799712000000,
    "amount": 6,
    "currency": "usd"
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| orderId | string | Order ID |
| instanceId | string | Instance ID |
| status | string | paid after successful Credit deduction |
| stripCheckoutUrl | string | This entry point always pays with Credit; returns null |
| purgeAtAfter | long | Scheduled cleanup time after extension, as a millisecond timestamp |
| amount | number | Actual deduction: renewMonths * 2, in USD major units |
| currency | string | usd |

#### Failure cases

| code | Scenario |
| --- | --- |
| 400 | Missing required parameters or months outside 1-12 |
| 8001 | Instance missing or unauthorized |
| 8002 | Instance is not idle, is already cleaned up, or has reached the retention deadline |
| 5007 | Insufficient available Credits or missing wallet |
| 429 | Storage-fee payment for the same instance is processing |
| 401 / 1007 | Missing or invalid Access Token |

#### Fee and deadline example

Buying 3 months of retention costs 6 Credits and extends the original retention deadline confirmed at payment by 90 days. Success returns status=paid; purgeAtAfter is the new cleanup time. It is not the runtime entitlement end time and does not immediately let an idle instance receive messages.

This endpoint does not process Idempotency-Key. If the result is unknown, check orders or business state already received by the client before acting; do not automatically pay for the same months repeatedly. If funds are insufficient, top up and confirm receipt, then submit according to the user's choice.
