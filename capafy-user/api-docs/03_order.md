# User Skill API Reference

Shared authentication, units and endpoint index: [00_overview.md](00_overview.md).

## A06 `POST /agent/orders/buyer/create`

Create a buyer order

Use Credit to purchase download products, hourly runtime, or subscriptions, or renew an existing instance owned by the user. This endpoint affects the balance; use idempotency headers whenever possible.

#### Endpoint details

`POST /agent/orders/buyer/create`

Requires Access Token authentication; only the current user's data is accessible.


##### Idempotency header

Optional `Idempotency-Key`; a UUID is recommended. At most 128 characters after trimming; longer values return 400. The same user, endpoint, and key replay the first successful response within 24 hours. Use a new key for a new business request; reuse the original key and body when retrying a timeout. A different body with the same key returns `400`; a first request still being processed may return `429`, so retry later with the original key. Failures are not cached.
#### Request parameters

Use the `Content-Type: application/json` header. A nonempty `instanceId` triggers renewal; otherwise a new purchase order is created. The Agent entry point always uses Credit payment.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| agentId | string | Required for new purchases | Agent ID, at most 36 characters; instanceId determines ownership for renewal |
| hours | int | Required for hourly billing | Integer from 1 to 24, meeting the selected plan's minPurchaseHours; not needed for downloads or subscriptions |
| agentCardBillingId | string | Required for new purchases | Complete billing ID returned by the server; pass unchanged; renewal retains the original ID if omitted |
| instanceId | string | Required for renewal | Instance ID, at most 36 characters; omit for new purchases |

##### New purchase request

```json
{
  "agentId": "agent_123",
  "agentCardBillingId": "billing_123",
  "hours": 2
}
```

##### Hourly renewal request

```json
{
  "instanceId": "instance_123",
  "hours": 2
}
```

##### Subscription renewal request

```json
{
  "instanceId": "instance_123",
  "agentCardBillingId": "billing_456"
}
```

#### Billing selection and renewal rules

1. New purchases use the latest published version. The billing ID must belong to that Agent. Developer billing must match the latest published version; experiment billing reads the corresponding configuration using the complete ID.
2. For new purchases, obtain a specific billing ID from search results, details, or the quote endpoint.
3. Before renewal, call `GET /agent/instance/{instanceId}/agent-version-billing` to read the original plan and available billings; retain the original billing identity.
4. Hourly renewal retains the original ID and cannot switch tiers. Subscription renewal can select a subscription billing ID within the original plan: developer plans must belong to the original Agent version, and experiment plans must meet the original policy and plan constraints.
5. Renewal requires an instance owned by the user that has not been cleaned up and is within the retention period. The bound version must allow renewal (renewalEnabled=true) and be published or expired.
6. Hourly, subscription, and free trial instances follow their respective renewal policies. Renewing a free trial converts it to a paid purchase; conditions are validated by the original instance's policy.
7. Manual subscription renewal requires the original subscription to have expired, or to be canceled with the instance idle / the original paid cycle ended. retrying is rejected; wait for the retry result or cancel first.
8. Subscription renewal creates a new subscription relationship and initial bill while reusing the instance. A canceled subscription still within its valid period can resume automatic renewal through the resume-subscription endpoint.

#### Successful response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "orderId": "hou-order_123",
    "status": "paid",
    "stripCheckoutUrl": null,
    "amount": 12,
    "currency": "usd",
    "usageStartAt": 1791763200000,
    "usageEndAt": 1791770400000,
    "welcomeMessage": "Hello"
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| orderId | string | Order ID; for subscriptions, the initial bill ID, usable directly to query order details |
| status | string | paid after successful Credit deduction |
| stripCheckoutUrl | string | This entry point always pays with Credit; returns null |
| amount | number | Order amount in USD major units |
| currency | string | usd |
| usageStartAt | long | Start time for hourly orders and manual subscription renewals; may be null for ordinary new subscriptions or downloads |
| usageEndAt | long | End time for hourly orders and manual subscription renewals; may be null for ordinary new subscriptions or downloads |
| welcomeMessage | string | Version welcome message; null when unconfigured |

#### Failure cases

| code | Scenario |
| --- | --- |
| 400 | Invalid request parameters or different body for the same key |
| 4005 | Missing billing ID, unavailable configuration, mismatched plan ownership, or invalid billing price |
| 429 | Concurrent ordering or the same idempotent request is still processing |
| 2004 / 2010 | Agent missing, unpublished, or version unavailable |
| 4073 | New purchase developer billing does not match the latest published version |
| 4074 | Original subscription payment is being retried |
| 8017 | Renewal disabled for the original version |
| 8001 / 8002 | Instance missing, unauthorized, cleaned up, or beyond retention |
| 5007 | Insufficient available Credits or missing wallet |

Hourly hours below the minimum purchase requirement, insufficient concurrency capacity, or an original subscription state that disallows renewal also return corresponding business errors. When the balance is insufficient, top up and confirm receipt before retrying the purchase.

#### Minimum requests by purchase scenario

| Scenario | Must provide | May omit |
| --- | --- | --- |
| New download purchase | agentId, download plan's agentCardBillingId | hours, instanceId |
| New hourly purchase | agentId, hourly plan's agentCardBillingId, hours | instanceId |
| New subscription | agentId, subscription plan's agentCardBillingId | hours, instanceId |
| Hourly instance renewal | instanceId, hours | agentId, agentCardBillingId; the original plan is retained if billing ID is omitted |
| Subscription instance renewal | instanceId | agentId, hours; agentCardBillingId can be specified within the allowed scope |

Example request for a new download or subscription purchase; select the billing ID for the intended use:

```json
{"agentId":"agent_123","agentCardBillingId":"billing_456"}
```

#### Using the order result

Save orderId after success. For downloads, use this order to obtain installation information. For hosted products, query the user's instance list and locate instanceId using the matching agentId and agentVersionId; query instanceId in the order details when the order association needs confirmation. This create endpoint does not return instanceId directly.

New subscriptions return the initial bill ID, not subscriptionId. Obtain the subscription relationship ID from the subscription list or instance billing query for subscription management. If a network timeout prevents receiving a response, do not immediately order again with a different idempotency key.

## A05 `POST /agent/orders/topup/create`

Create a top-up order (Agent)

Add Credit balance before purchasing. This endpoint creates a top-up order and provides a Stripe payment page; confirm the actual credit through the payment-result query.

#### Endpoint details

`POST /agent/orders/topup/create`

Requires Access Token authentication; only the current user's data is accessible.


##### Idempotency header

Optional `Idempotency-Key`; a UUID is recommended. At most 128 characters after trimming; longer values return 400. The same user, endpoint, and key replay the first successful response within 24 hours. Use a new key for a new business request; reuse the original key and body when retrying a timeout. A different body with the same key returns `400`; a first request still being processed may return `429`, so retry later with the original key. Failures are not cached.
#### Request parameters

Use the `Content-Type: application/json` header.

```json
{
  "amount": 10,
  "callbackUrl": "https://example.com/topup/result"
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| amount | number | Yes | Top-up amount from 10 to 2000 USD inclusive; 1 USD equals 1 Credit |
| callbackUrl | string | No | At most 2048 characters; Stripe Checkout uses the same return URL for completion and cancellation; defaults to server configuration |

Use USD major units for the JSON amount; the server validates after amount conversion. The resulting balance cannot exceed 2000 Credits; the existing balance plus top-up exceeding this limit returns 400.

#### Successful response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "orderId": "2097948161935953920",
    "status": "pending_payment",
    "stripCheckoutUrl": "https://checkout.stripe.com/c/pay/cs_test_xxx"
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| orderId | string | Top-up order ID; use unchanged to query its payment result |
| status | string | pending_payment after successful creation |
| stripCheckoutUrl | string | Stripe Checkout payment page URL |

#### Payment flow

1. Create a top-up order and save orderId.
2. Open stripCheckoutUrl to complete Stripe payment.
3. The server appends orderId and successful query parameters to callbackUrl; successful is only a return-page hint. Call `POST /agent/orders/topup/{orderId}/payment-result` to query the platform status; do not infer receipt from the return-page hint.
4. After paid, query `GET /agent/account`, then purchase the Agent with Credit.

Creating a top-up order does not increase Credits. A successful payment webhook updates the order to paid and adds the balance; failed payment records payment_failed and a failure reason.

#### Failure cases

| code | Scenario |
| --- | --- |
| 400 | Missing amount, below 10 or above 2000, resulting balance above 2000, return URL too long, or different body for the same key |
| 429 | Concurrent user top-ups or first request with the same key still processing |
| 6001 | Account missing or unavailable |
| 5005 | Failed to create Stripe Customer or Checkout |
| 401 / 1007 | Missing or invalid Access Token |

#### Return URL and receipt confirmation

callbackUrl can return the browser to the caller's page; the server appends orderId and successful. successful is only a display hint, not proof of platform credit. After the payment page redirects back, query payment-result using the original top-up orderId.

The balance plus this top-up cannot exceed 2000 Credits. Successful creation returns status=pending_payment; do not purchase using that amount immediately. After paid, refresh the account and use the latest balance.

## A30 `POST /agent/orders/topup/{orderId}/payment-result`

Query top-up payment result (Agent)

Confirm the top-up result after Stripe payment or return-page redirection. Use orderId returned by top-up creation, rather than a product order or subscription bill ID.

#### Endpoint details

`POST /agent/orders/topup/{orderId}/payment-result`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| orderId | path string | Yes | Complete orderId returned when creating the top-up order |

No body or query parameters. Only the current user's top-up orders can be queried.

#### Successful response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "orderId": "2097948161935953920",
    "status": "paid",
    "paymentFailureReason": null
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| orderId | string | Top-up order ID |
| status | string | Top-up status: pending_payment / payment_failed / paid |
| paymentFailureReason | string | Payment failure reason; normally null in other states |

#### Status handling

| status | Client handling |
| --- | --- |
| pending_payment | Platform has not confirmed receipt; query the same order again later |
| payment_failed | Display paymentFailureReason; create a new top-up order if the user chooses |
| paid | Platform has processed successful payment; refresh the account Credit balance before purchasing |

This endpoint only reads the platform order status. It does not actively confirm payment with Stripe, charge, or credit the wallet. Do not query top-ups through the buyer product-order details endpoint.

#### Failure cases

A missing top-up order or one belonging to another user returns `TOPUP_ORDER_NOT_FOUND(4001)`; a missing or invalid Access Token returns `401` / `1007`.

#### Query sequence

Create a top-up order -> open the payment page -> query this endpoint with the original orderId -> GET /agent/account after paid -> continue purchasing. Repeat the query later for pending_payment; do not automatically create another order for the same top-up already in payment.

If the order is payment_failed, display paymentFailureReason and let the user decide whether to top up again. This endpoint neither retries charges nor regenerates the payment page.

## A07 `GET /agent/orders/buyer/list`

List buyer orders

View the current buyer's product transactions and subscription payment bills to obtain orderId for details or download information. Refunded records are currently hidden.

#### Endpoint details

`GET /agent/orders/buyer/list`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status | query string | No | Order or bill status; omitted or blank returns all non-refunded orders; otherwise filters by the exact status |

No body or pagination; returns descending createdAt order. refunded is always excluded. Possible results include pending_payment, retrying, payment_failed, paid, refunding, and completed. status=refunded returns an empty array. The query uses order status, rather than subscription relationship status.

#### Successful response

```json
{
  "code": 0,
  "msg": "ok",
  "data": [
    {
      "orderId": "hou-order_123",
      "agentId": "agent_123",
      "agentVersionId": "version_123",
      "agentCardBillingId": "billing_123",
      "orderSource": "agent",
      "paymentMethod": "credit",
      "currency": "usd",
      "status": "paid",
      "amount": 12,
      "actualAmount": 12,
      "paymentAt": 1791763200000
    }
  ]
}
```

The example shows only key fields; complete data[] fields are listed below. data=[] when no orders exist.

| Field | Type | Description |
| --- | --- | --- |
| orderId | string | Product order or subscription bill ID; not a subscription relationship ID |
| buyerId | string | Buyer user ID |
| developerId | string | Developer user ID |
| developerName | string | Developer name |
| developerEmail | string | Developer email from the Agent's latest published version; empty string if unavailable |
| agentId | string | Agent ID |
| agentVersionId | string | Agent Card ID |
| agentCardBillingId | string | Agent billing plan ID |
| agentTitle | string | Agent title |
| instanceId | string | Instance ID |
| refundId | string | Refund ticket ID |
| orderSource | string | Order source, such as web / agent |
| paymentMethod | string | Payment method |
| currency | string | Currency |
| stripeHostedInvoiceUrl | string | Stripe hosted invoice page link |
| stripePaymentIntentId | string | Stripe PaymentIntent ID |
| status | string | Order status |
| amount | number | Amount due in USD major units |
| actualAmount | number | Amount snapshot; combine status and paymentAt to determine payment |
| paymentFailureReason | string | Payment failure reason |
| paymentDeadlineAt | long | Payment deadline |
| paymentAt | long | Successful payment time |
| refundDeadlineAt | long | Refund deadline |
| refundedAt | long | Refund time |
| completedAt | long | Completion time |
| createdAt | long | Creation time |
| updatedAt | long | Update time |

#### Integration rules and failure cases

- Download orders, hourly orders, and Credit / Stripe subscription bills share this list. Top-ups and storage fees use their respective business endpoints.
- orderId in a subscription creation response directly identifies the initial bill; later renewal bills have separate orderIds.
- Unsupported status values normally match no records and return an empty array.
- A missing or invalid Access Token returns an authentication error.

#### Identifying orders and bills

Use orderId exactly as returned by the server. buy- identifies download orders, hou- hourly orders, and cre- / str- Credit / Stripe subscription bills. Each subscription cycle creates a separate bill; orderId from the list can be used directly to query order details.

instanceId may be null for downloads; unpaid Stripe orders may also lack an associated instance. When paymentAt is null, a positive actualAmount alone does not prove successful payment. No records returns data=[], without pagination. Query status=pending_payment for pending payments.

## A08 `GET /agent/orders/buyer/{orderId}/detail`

Get buyer order details

Check the status, amount, version, and instance association of one product order or subscription payment bill owned by the buyer. A subscription relationship ID cannot replace this endpoint's bill ID.

#### Endpoint details

`GET /agent/orders/buyer/{orderId}/detail`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| orderId | path string | Yes | Complete order / bill ID from the list or create-order response |

No body or query parameters. Use the bill orderId for subscription queries; subscriptionId identifies the subscription relationship and cannot replace the order ID.

#### Response fields

All order types use the following structure; inapplicable or unpopulated fields may be null. Amounts are in USD major units; ratio fields are numeric ratios.

| Field | Type | Description |
| --- | --- | --- |
| orderId | string | Order ID |
| subscriptionId | string | Associated subscription ID |
| buyerId | string | Buyer user ID |
| developerId | string | Developer user ID |
| developerName | string | Developer name |
| developerEmail | string | Filled from the developer email of the Agent's latest published version; may be an empty string if missing |
| agentId | string | Agent ID |
| agentVersionId | string | Agent Card ID |
| agentCardBillingId | string | Agent billing plan ID |
| billingPlanCode | string | Plan code snapshot at purchase; A for developer billing |
| agentTitle | string | Agent title |
| agentLogoUrl | string | Agent Logo URL |
| instanceId | string | Instance ID |
| requestPackId | string | Request pack configuration ID; null for other order types |
| messageCount | long | Purchased request count snapshot; null for non-request-pack orders |
| refundId | string | Refund ticket ID |
| orderSource | string | Order source: web / agent |
| currency | string | Currency |
| oneTimeFee | number | Download price snapshot |
| minPurchaseHours | int | Minimum hours per purchase; a positive integer |
| hourlyPrice | number | Hourly price |
| purchaseTime | int | Total purchased minutes for an hourly order |
| amount | number | Amount due |
| actualAmount | number | Paid amount snapshot; do not use alone to determine payment |
| refundAmount | number | Refund amount |
| settlementRatio | number | Settlement ratio |
| developerAmount | number | Amount due to the developer |
| developerActualAmount | number | Amount actually received by the developer |
| platformFeeRate | number | Platform fee rate |
| platformFeeAmount | number | Amount due to the platform |
| platformActualAmount | number | Amount actually received by the platform |
| containerRunFee | number | Container runtime fee |
| paymentMethod | string | Payment method |
| paymentFailureReason | string | Payment failure reason |
| stripeHostedInvoiceUrl | string | Stripe hosted invoice page URL; subscription bills obtain it from Invoice |
| status | string | Order / bill status, including pending_payment / retrying / payment_failed / paid / refunding / refunded / completed |
| isSettled | boolean | Whether settlement is complete |
| usageStartAt | long | Usage start time as a millisecond timestamp |
| usageEndAt | long | Usage end time as a millisecond timestamp |
| paymentDeadlineAt | long | Payment deadline as a millisecond timestamp |
| paymentAt | long | Successful payment time as a millisecond timestamp |
| firstDownloadAt | long | Buyer's first download time as a millisecond timestamp |
| refundDeadlineAt | long | Refund deadline as a millisecond timestamp |
| refundedAt | long | Refund time as a millisecond timestamp |
| completedAt | long | Completion time as a millisecond timestamp |
| createdAt | long | Creation time as a millisecond timestamp |

#### Successful response example

Only core fields are shown below.

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "orderId": "hou-order_123",
    "subscriptionId": null,
    "agentId": "agent_123",
    "agentVersionId": "version_123",
    "agentCardBillingId": "billing_123",
    "billingPlanCode": "A",
    "orderSource": "agent",
    "instanceId": "instance_123",
    "requestPackId": null,
    "messageCount": null,
    "hourlyPrice": 6,
    "purchaseTime": 120,
    "currency": "usd",
    "amount": 12,
    "actualAmount": 12,
    "paymentMethod": "credit",
    "status": "paid",
    "usageStartAt": 1791763200000,
    "usageEndAt": 1791770400000,
    "paymentAt": 1791763200000
  }
}
```

#### Integration rules and failure cases

- Determine the payment result using status and paymentAt.
- Download orders usually include oneTimeFee; hourly orders include hourlyPrice / minPurchaseHours / purchaseTime; subscription bills include subscriptionId.
- The payment flow writes the Stripe order's hosted invoice URL; it may be null until written.
- Missing orders or orders belonging to another user return an order-not-found business error; unknown order types return an unsupported-operation business error.
- A missing or invalid Access Token returns an authentication error.

#### Reading fields by order type

| Field | Download order | Hourly order | Subscription bill |
| --- | --- | --- | --- |
| subscriptionId | null | null | Subscription relationship ID |
| oneTimeFee | Download price | null | null |
| hourlyPrice / minPurchaseHours / purchaseTime | null | Unit price, minimum hours, and total minutes for this purchase | null |
| instanceId | Normally null | Associated instance; may not yet be linked before payment | Associated instance; may be null if not populated |
| firstDownloadAt | Time the download URL was first successfully obtained; null before download | null | Normally null |
| usageStartAt / usageEndAt | null when inapplicable | Start and end of this runtime entitlement | Returned according to actual bill data; null when inapplicable |

paymentMethod is credit or stripe. Order / bill status differs from subscription relationship status; refunding means a refund is processing and refunded means it is complete. Balance, refund, and settlement amounts use major units; settlementRatio and platformFeeRate are numeric ratios.

## A09 `POST /agent/review/agents/{agentId}/review`

Create my review

Submit a rating and optional text review for an Agent with a valid purchase. Each buyer has only one review per Agent.

#### Endpoint details

`POST /agent/review/agents/{agentId}/review`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| agentId | path string | Yes | Agent ID |
| rating | body int | Yes | Rating from 1 to 5 |
| comment | body string | No | Text review; at most 500 characters |

```json
{
  "rating": 5,
  "comment": "Easy to use and responds quickly."
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

#### Business rules

- The buyer must have a valid purchase record for the Agent.
- Each user has one review per Agent; an existing active review cannot be submitted again.
- Deleted reviews can be restored with a new rating and content; reviews marked as violating platform rules cannot be republished.
- Success returns empty business data and clears the rating statistics cache.

#### Failure cases

| code | Scenario |
| --- | --- |
| 400 | Missing rating, rating outside 1-5, or comment longer than 500 characters |
| 2004 | Agent does not exist |
| 4048 | No valid purchase of this Agent |
| 4049 | Active review already exists |
| 4050 | Previous review marked as violating rules |
| 401 / 1007 | Missing or invalid Access Token |

#### Handling submission results

Use an integer rating; an omitted or empty comment means no text review. Success returns code=0 and data=null, without a review ID. Resubmitting an existing active review fails. After a timeout, do not assume another creation is required; if resubmission returns an already-reviewed error, tell the user a review already exists.
