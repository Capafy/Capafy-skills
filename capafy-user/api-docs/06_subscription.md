# User Skill API Reference

Shared authentication, units and endpoint index: [00_overview.md](00_overview.md).

## A20 `GET /agent/subscriptions/list`

List subscriptions (Agent)

View the user's subscription relationships and automatic renewal status. Use subscriptionId for cancellation or resumption and the separate bill orderId for payment queries.

#### Endpoint details

`GET /agent/subscriptions/list`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status | query string | No | active / trialing / retrying / canceled / expired; omit to return all displayable subscriptions |

No body or pagination. Status input is trimmed and lowercased. Filtering active includes active and trialing, but trial subscriptions still return trialing in the response.

#### Status meanings

| status | Description |
| --- | --- |
| active | Active paid subscription |
| trialing | Subscription in a free trial |
| retrying | Still in the payment retry period after failed renewal |
| canceled | Automatic renewal canceled; the current period remains usable |
| expired | Expired or ended subscription |

Queries correct statuses of records beyond their retry period or already ended according to service rules. With no filter, initial-payment pending and checkout_expired records are excluded.

#### Successful response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "subscriptions": [
      {
        "agentVersionId": "version_123",
        "renewalEnabled": true,
        "subscriptionId": "sub_123",
        "agentId": "agent_123",
        "agentTitle": "Office assistant",
        "developerName": "Alice",
        "agentLogoUrl": "https://example.com/logo.png",
        "status": "active",
        "cycleType": "month",
        "cyclePrice": 29,
        "currency": "usd",
        "nextBillingAt": 1794441600000,
        "firstPaymentAt": 1791763200000,
        "paymentMethod": "credit"
      }
    ]
  }
}
```

data.subscriptions is an array; [] when no records exist.

| Field | Type | Description |
| --- | --- | --- |
| agentVersionId | string | Subscription list items |
| renewalEnabled | boolean | Whether the associated Agent version allows renewal; may be null if the version is missing |
| subscriptionId | string | Subscription ID |
| agentId | string | Agent ID |
| agentTitle | string | Agent title |
| developerName | string | Developer name |
| agentLogoUrl | string | Agent Logo URL |
| status | string | active / trialing / retrying / canceled / expired |
| cycleType | string | day / week / month / quarter / year; original cycle code |
| cyclePrice | number | Price per cycle in USD major units |
| currency | string | Currency |
| nextBillingAt | long | currentPeriodEnd for active / trialing / retrying; null for other states |
| firstPaymentAt | long | Initial bill periodStart as a millisecond timestamp; null if missing |
| paymentMethod | string | Payment method |

#### Follow-up operations and failure cases

Cancel or resume subscription relationships with subscriptionId; query payment bills using orderId from the order list. Unsupported status returns 400; missing or invalid Access Tokens return authentication errors.

#### Automatic renewal and payment records

status is the subscription relationship status. nextBillingAt is the currently recorded next charge time and may be null for canceled / expired subscriptions; it is not the successful payment time. firstPaymentAt follows the initial bill's period start and may be null for missing historical data.

Filtering status=active includes trial subscriptions, but each item's actual status may still be trialing. Use that item's subscriptionId for cancellation or resumption; view payments for each period through bill IDs in the product-order list.

## A21 `POST /agent/subscriptions/{subscriptionId}/cancel`

Cancel a subscription (Agent)

Stop future automatic charges for the current subscription. Normal periods and payment retry periods take effect differently; read the returned status and effectiveAt.

#### Endpoint details

`POST /agent/subscriptions/{subscriptionId}/cancel`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| subscriptionId | path string | Yes | Subscription relationship ID owned by the user |

No body or query parameters.

#### Business rules

| Status before operation | Result | effectiveAt |
| --- | --- | --- |
| active / trialing | canceled; the current period remains usable, with no automatic renewal after it ends | End of the current period |
| retrying | expired; further payment retries stop immediately | Current time |

Credit cancellation clears local renewal tasks. Stripe cancellation synchronizes the channel status first and updates the local subscription only after successful synchronization.

#### Successful response

Cancellation during a normal period:

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "subscriptionId": "sub_123",
    "status": "canceled",
    "effectiveAt": 1794441600000
  }
}
```

Cancellation during a retry period:

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "subscriptionId": "sub_123",
    "status": "expired",
    "effectiveAt": 1791763200000
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| subscriptionId | string | Subscription ID |
| status | string | Canceling active / trialing returns canceled; canceling retrying returns expired |
| effectiveAt | long | Millisecond timestamp; period end for a normal period, current time for a retry period |

#### Failure cases

| code | Scenario |
| --- | --- |
| 4029 | Subscription missing, deleted, or unauthorized |
| 4039 | Status is not active / trialing / retrying |
| 4040 | Stripe channel status synchronization failed |
| 500 | Local status update failed |
| 401 / 1007 | Missing or invalid Access Token |

#### Available actions after cancellation

A canceled result leaves the current period valid; use resume to restore automatic renewal before it ends. An expired result stops retries immediately; resume cannot restore the current period. Reusing the instance for a purchase must meet create-order renewal conditions.

Repeated cancellation of an already canceled or expired subscription returns a disallowed-state error. effectiveAt is a millisecond timestamp; display the cancellation's effective time using its actual value.

## A22 `POST /agent/subscriptions/{subscriptionId}/resume`

Resume a subscription (Agent)

Resume a canceled subscription whose current period has not ended. Resumption retains the current period instead of immediately starting a new one.

#### Endpoint details

`POST /agent/subscriptions/{subscriptionId}/resume`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| subscriptionId | path string | Yes | Subscription relationship ID owned by the user |

No body or query parameters.

#### Business rules

Only canceled subscriptions with a period end later than the current time can resume. The Agent must be online and the associated version must allow renewal. Resumption continues the current period and restores automatic renewal; it creates no new period and makes no immediate charge in this request.

Ordinary subscriptions resume as active; subscriptions whose instance is still in a free trial resume as trialing. Credit resumption restores renewal scheduling. Stripe synchronizes automatic renewal first and updates local state only after success.

#### Successful response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "subscriptionId": "sub_123",
    "status": "active",
    "nextBillingAt": 1794441600000
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| subscriptionId | string | Subscription ID |
| status | string | active after resumption; trialing if still in a free trial |
| nextBillingAt | long | Original currentPeriodEnd as a millisecond timestamp |

#### Failure cases

| code | Scenario |
| --- | --- |
| 4029 | Subscription missing, deleted, or unauthorized |
| 4039 | Status is not canceled, current period has ended, or period end is missing |
| 2010 | Agent or associated version unavailable |
| 8017 | Renewal disabled for the associated Agent version |
| 4040 | Stripe channel synchronization failed |
| 500 | Failed to update local resumed state |
| 401 / 1007 | Missing or invalid Access Token |

To purchase using the instance of an expired subscription, use the buyer create-order endpoint with instanceId.

#### Display after resumption

Display the returned status after success rather than hardcoding active; trialing may be returned if the free trial remains valid. nextBillingAt retains the current period end. Resumption neither recalculates a new period nor indicates completion of the next charge.

A resumption failure with 8017 means renewal is disabled for the bound version. If the original period ended or the status disallows resumption, choose a new subscription or another version according to the actual state.
