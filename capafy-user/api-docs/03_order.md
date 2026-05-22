# User Skill API Order

## A05 `POST /agent/orders/topup/create`

Create a Credits top-up order and return a Stripe Checkout link.

```http
POST /agent/orders/topup/create
Authorization: Bearer {token}
Content-Type: application/json

{ "amount": 10 }
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "orderId": "019e1234abcd5678ef901234567890ab",
    "status": "pending_payment",
    "stripCheckoutUrl": "https://checkout.stripe.com/c/pay/cs_test_xxx"
  }
}
```

Request fields:

| Field | Type | Required | Description |
|---|---|---|---|
| amount | number | Yes | Top-up amount. Must be at least `10`. |

Response fields:

| Field | Type | Description |
|---|---|---|
| data.orderId | string | Top-up order ID. |
| data.status | string | Top-up order status. Creation normally returns `pending_payment`. |
| data.stripCheckoutUrl | string | Stripe Checkout URL. The field name is currently `stripCheckoutUrl`. |

Key points:

- `amount >= 10`
- The current field name in the response is **`stripCheckoutUrl`**
- This only means a payment order was created — it does not mean the top-up is complete

## A06 `POST /agent/orders/buyer/create`

Create a buyer order, renew a time-based instance, or renew an expired subscription instance.

```http
POST /agent/orders/buyer/create
Authorization: Bearer {token}
Content-Type: application/json

{
  "agentId": "7b9d61e2-4c18-7dd8-9b14-1f37eac0b35c",
  "hours": 2,
  "billingLineNo": 0,
  "instanceId": null
}
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "orderId": "hou-7b9d61e2-4c18-7dd8-9b14-1f37eac0b35c",
    "status": "paid",
    "stripCheckoutUrl": null,
    "amount": 12.00,
    "instanceId": "7b9d646a-b049-7e41-a677-1a4e1e0125db",
    "usageStartAt": 1775030400000,
    "usageEndAt": 1775034000000,
    "welcomeMessage": "Hello! How can I help you today?",
    "canContinueAddInstanceOrPurchase": true
  }
}
```

Request fields:

| Field | Type | Required | Description |
|---|---|---|---|
| agentId | string | Conditional | Required for new orders. Optional for renewals because `instanceId` identifies the target. |
| hours | int | Conditional | Required for hourly purchases and hourly renewals. Valid system range is `1-24`, and the value must also satisfy the plan's `minPurchaseHours`. Do not send it for subscription renewal. |
| billingLineNo | int | No | Billing plan line number: `0`, `1`, or `2`. Defaults to `0`. Applies to new orders only. |
| instanceId | string | No | Existing instance ID. When present, the endpoint uses renewal semantics. |

Recommended parameter combinations:

| Scenario | agentId | hours | billingLineNo | instanceId |
|---|---|---|---|---|
| New Download order | Required | Omit | Optional, defaults to `0` | Omit |
| New hourly order | Required | Required | Optional, defaults to `0` | Omit |
| New Credit subscription | Required | Omit | Optional, defaults to `0` | Omit |
| Hourly renewal | Optional | Required | Usually omit | Required |
| Expired subscription renewal | Optional | Omit | Usually omit | Required |

Response fields:

| Field | Type | Description |
|---|---|---|
| data.orderId | string | Order ID or first bill ID. Prefixes commonly include `buy-`, `hou-`, and `cre-`. |
| data.status | string | Order or first-bill status. Successful Credit calls usually return `paid`. |
| data.stripCheckoutUrl | string/null | Stripe Checkout URL. Agent-side order creation currently uses Credit, so this is normally `null`. |
| data.amount | number | Amount charged for this order or first bill. |
| data.instanceId | string/null | Created or reused instance ID when the order has an instance. |
| data.usageStartAt | long/null | Usage start time in Unix milliseconds. Hourly scenarios normally have a value after successful Credit payment. |
| data.usageEndAt | long/null | Usage end time in Unix milliseconds. Hourly scenarios normally have a value after successful Credit payment. |
| data.welcomeMessage | string/null | Seller-configured welcome message. Show it once after successful purchase when present. |
| data.canContinueAddInstanceOrPurchase | boolean/null | Availability flag. `false` means the Agent is sold out or otherwise blocked for new purchase/instance creation. |

Calling rules:

- Pass `agentId` when creating a new order
- Pass `instanceId` and `hours` when renewing a time-based instance
- Pass `instanceId` without `hours` when renewing an expired subscription instance
- The current Agent-side order creation endpoint uses `credit` payment by default; passing `paymentMethod` is not needed or supported
- `billingLineNo` is optional (`0`, `1`, `2`); defaults to `0` if omitted — selects one of the multiple billing plans for the current listed version of the Agent
- `billingLineNo` is only meaningful for new orders. Renewal keeps the original instance's billing context
- If `stripCheckoutUrl` is returned, the user must open the link to complete payment
- `welcomeMessage` is the seller-configured Agent welcome line, returned on a successful order; may be `null` if the seller did not configure one. When present, surface it to the user once the purchase succeeds
- `canContinueAddInstanceOrPurchase` is a boolean availability flag. `true` (or absent) = the Agent can still take new orders / instances; `false` = the Agent is sold out and the platform has blocked further purchases or new instance creation. When `false`, treat the order as not actionable: do NOT retry, do NOT propose workarounds, tell the user the Agent is sold out (see SKILL.md 3.2 for the standard handling)

Renewal rules:

- Time-based instance renewal reuses the existing `instanceId` and requires `hours`
- Expired subscription instance renewal reuses the existing `instanceId`, creates a new subscription relationship and first bill, and must not include `hours`
- Do not pass `instanceId` for a new order
- For subscription renewal, the old subscription must be `expired`; non-expired subscription instances are not valid renewal targets

## A07 `GET /agent/orders/buyer/list`

View the current user's order / billing list.

```http
GET /agent/orders/buyer/list?status=paid
Authorization: Bearer {token}
```

Common `status` values:

- `pending_payment`
- `payment_failed`
- `paid`
- `refunded`
- `completed`

Query parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| status | string | No | Filter by order/bill status. Omit it when the caller needs all displayable order records. |

List item fields:

| Field | Type | Description |
|---|---|---|
| orderId | string | Order ID or subscription bill ID. |
| buyerId | string | Buyer user ID. |
| developerId | string | Seller user ID. |
| developerName | string/null | Seller display name, when available. |
| developerEmail | string/null | Seller email, when available. |
| agentId | string | Agent ID. |
| agentVersionId | string | Agent version ID at purchase time. |
| agentCardBillingId | string | Billing plan ID used by this order. |
| agentTitle | string/null | Agent title. |
| instanceId | string/null | Related instance ID. Download orders commonly return `null`. |
| refundId | string/null | Refund workflow ID, or `null` when no refund exists. |
| paymentMethod | string | Payment method, commonly `credit` or `stripe`. |
| status | string | Order or bill status. |
| amount | number | Payable amount. |
| actualAmount | number/null | Amount snapshot currently recorded for the order. Do not use this alone to infer paid status. |
| paymentFailureReason | string/null | Failure reason for payment-failed records. |
| stripeHostedInvoiceUrl | string/null | Stripe hosted invoice URL; usually `null` for Credit payments. |
| stripePaymentIntentId | string/null | Stripe PaymentIntent ID when applicable. |
| paymentDeadlineAt | long/null | Payment deadline in Unix milliseconds. |
| paymentAt | long/null | Successful payment time in Unix milliseconds. |
| refundDeadlineAt | long/null | Refund application deadline. |
| refundedAt | long/null | Refund completion time. |
| completedAt | long/null | Order completion time. |
| createdAt | long | Creation time in Unix milliseconds. |
| updatedAt | long | Last update time in Unix milliseconds. |

Order ID prefixes:

| Prefix | Meaning |
|---|---|
| `buy-` | Download order. |
| `hou-` | Hourly order. |
| `cre-` | Credit subscription bill. |
| `str-` | Stripe subscription bill. |

## A08 `GET /agent/orders/buyer/{orderId}/detail`

View the detail of a single order or subscription bill.

```http
GET /agent/orders/buyer/{orderId}/detail
Authorization: Bearer {token}
```

Path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| orderId | string | Yes | Order ID or subscription bill ID from A06/A07. Do not pass `subscriptionId` here. |

Response fields:

| Field | Type | Description |
|---|---|---|
| orderId | string | Current order or bill ID. |
| subscriptionId | string/null | Subscription ID. Only subscription bill scenarios have a value. |
| buyerId | string | Buyer user ID. |
| developerId | string | Seller user ID. |
| developerName | string/null | Seller display name. |
| developerEmail | string/null | Seller email. |
| agentId | string | Agent ID. |
| agentVersionId | string | Agent version ID at purchase time. |
| agentCardBillingId | string | Billing plan ID used by this order. |
| agentTitle | string | Agent title. |
| agentLogoUrl | string/null | Agent logo URL. |
| instanceId | string/null | Related instance ID. |
| refundId | string/null | Refund workflow ID, or `null` when no refund exists. |
| oneTimeFee | number/null | Download price. Only Download Agent orders have a value. |
| minPurchaseHours | int/null | Minimum purchase hours. Only hourly orders have a value. |
| hourlyPrice | number/null | Hourly price. Only hourly orders have a value. |
| purchaseTime | int/null | Purchased duration in minutes. Only hourly orders have a value. |
| amount | number | Payable amount. |
| actualAmount | number | Paid amount recorded by the platform. |
| refundAmount | number | Refunded amount. |
| settlementRatio | number/null | Settlement ratio, when applicable. |
| developerAmount | number/null | Seller receivable amount. |
| developerActualAmount | number/null | Seller actual settled amount. |
| platformFeeRate | number/null | Platform fee rate. |
| platformFeeAmount | number/null | Platform fee amount. |
| platformActualAmount | number/null | Platform actual settled amount. |
| containerRunFee | number/null | Container run fee for subscription/container scenarios. |
| paymentMethod | string | Payment method, commonly `credit` or `stripe`. |
| paymentFailureReason | string/null | Payment failure reason. |
| stripeHostedInvoiceUrl | string/null | Stripe hosted invoice URL. Credit payments usually return `null`. |
| status | string | Order or bill status, not subscription relationship status. |
| isSettled | boolean | Whether this order has been settled. |
| usageStartAt | long/null | Usage start time for hourly orders. |
| usageEndAt | long/null | Usage end time for hourly orders. |
| paymentDeadlineAt | long/null | Payment deadline. |
| paymentAt | long/null | Successful payment time. |
| firstDownloadAt | long/null | First download time; mainly meaningful for Download orders. |
| refundDeadlineAt | long/null | Refund application deadline. |
| refundedAt | long/null | Refund completion time. |
| completedAt | long/null | Order completion time. |
| createdAt | long | Creation time in Unix milliseconds. |

Status values commonly include `pending_payment`, `payment_failed`, `paid`, `refunding`, `refunded`, and `completed`.

## A09 `POST /agent/review/agents/{agentId}/review`

Create a review for a specific Agent. Only one review is allowed per buyer per Agent.

```http
POST /agent/review/agents/{agentId}/review
Authorization: Bearer {token}
Content-Type: application/json

{
  "rating": 5,
  "comment": "Fast response, great results."
}
```

Path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| agentId | string | Yes | Agent ID being reviewed. |

Request fields:

| Field | Type | Required | Description |
|---|---|---|---|
| rating | int | Yes | Integer rating from `1` to `5`. |
| comment | string | Yes | Review text, up to `500` characters. |

Response fields:

| Field | Type | Description |
|---|---|---|
| code | int | `0` on success. |
| data | null | Success returns `data: null`; no `reviewId` is returned. |

Key points:

- `rating` must be between `1` and `5`
- `comment` is limited to `500` characters
- The buyer must have a valid purchase record for the Agent; otherwise returns `4048`
- If the same buyer has already reviewed the same Agent, returns `4049`
- If a review was previously deleted by the buyer, this endpoint revives the original record and updates its content
- If a review was flagged as a violation by the platform, re-publishing is not allowed and returns `4050`
- Returns `data: null` on success; no `reviewId` is returned

## Notes

- Refunds and refund status queries have been moved to web-only operations and are not handled via in-Skill API calls. See SKILL.md section 3.6.
