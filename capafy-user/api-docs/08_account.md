# User Skill API Reference

Shared authentication, units and endpoint index: [00_overview.md](00_overview.md).

## A26 `GET /agent/account`

Get account aggregate information (Agent)

Read the current account's Credit balance, spending limits, and developer verification status to check funds before purchase and refresh the balance after top-up.

#### Endpoint details

`GET /agent/account`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

No body or query parameters. Confirm the Credit balance before purchase and refresh it after a top-up is credited.

#### Successful response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "email": "buyer@example.com",
    "role": "consumer",
    "credit": {
      "balance": 120.5,
      "currency": "usd"
    },
    "autoConsume": {
      "monthlyLimit": 500,
      "perOrderLimit": 100,
      "monthlyUsed": 35.2,
      "currency": "usd"
    },
    "developerVerified": false
  }
}
```

##### data

| Field | Type | Description |
| --- | --- | --- |
| email | string | User email. |
| role | string | User role. |
| credit | object | Credit balance information. |
| autoConsume | object | Automatic spending limit information. |
| developerVerified | boolean | Whether developer verification is complete. |

##### credit

| Field | Type | Description |
| --- | --- | --- |
| balance | number | Wallet Credits balance in major units |
| currency | string | Always usd |

##### autoConsume

| Field | Type | Description |
| --- | --- | --- |
| monthlyLimit | number/null | Monthly spending limit in USD major units; null means unlimited |
| perOrderLimit | number/null | Per-order limit in USD major units; null means unlimited |
| monthlyUsed | number | Amount spent this month in major units |
| currency | string | Always usd |

role is always consumer; developerVerified reflects the current user's verification flag. monthlyUsed is the current month's spending statistic and may have about 60 seconds of cache delay.

#### Failure cases

A missing or invalid Access Token returns an authentication error; a missing user or wallet problem returns the corresponding business error.

#### Balance and spending limits

Read credit.balance before purchasing and again after a paid top-up to refresh the display. null autoConsume.monthlyLimit or perOrderLimit means the corresponding limit is unset, rather than a zero balance. monthlyUsed is the current month's spending statistic and may briefly lag recent transactions due to caching; it cannot alone determine whether an order was paid.

role is always consumer; developerVerified is a separate developer verification flag. Even when true, this endpoint still queries the current account's buyer balance and spending limits.

## User Profile (Agent)

Query or update the current user's personal description. The signed-in session determines the user; other user IDs are not accepted.

#### Endpoint details

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /agent/account/profile | Query the current user's personal description |
| PUT | /agent/account/profile | Update the current user's personal description |

Requires Access Token authentication; only the current user's data is accessible.


## A27 `GET /agent/account/profile`

Query Profile

`GET /agent/account/profile`, without body or query parameters.

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "userId": "user_123",
    "profile": "I am interested in AI and automation tools."
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| userId | string | Current user ID |
| profile | string/null | Personal description; null before it is saved |

## A28 `PUT /agent/account/profile`

Update Profile

`PUT /agent/account/profile`, with Content-Type: application/json.

```json
{
  "profile": "New personal description"
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| profile | string | No | Replaces the personal description; an empty string clears it, omission sets null; no text length limit currently applies |

Successful response:

```json
{
  "code": 0,
  "msg": "ok",
  "data": null
}
```

Both queries and updates require the current user to exist. Updating replaces that user's personal description or saves a new description if none exists.

#### Failure cases

A missing user returns the corresponding user business error; invalid JSON returns a parameter error; a missing or invalid Access Token returns an authentication error.

#### Clearing the personal description

An empty profile string in PUT clears the description; omission or explicit null updates it to null. A null profile in GET means it is unset or was set to null; do not display it as the string "null".

Successful updates return code=0 and data=null, without a new Profile object. Use the submitted text for display or GET again to confirm. Neither queries nor updates accept cross-user operation parameters.
