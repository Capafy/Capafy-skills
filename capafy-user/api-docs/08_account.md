# User Skill API Account

## A26 `GET /agent/account`

View the current account's aggregate information. Also the preferred token verification endpoint for the User Skill.

```http
GET /agent/account
Authorization: Bearer {token}
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "email": "buyer@example.com",
    "role": "consumer",
    "credit": {
      "balance": 120.50,
      "currency": "usd"
    },
    "autoConsume": {
      "monthlyLimit": 500.00,
      "perOrderLimit": 100.00,
      "monthlyUsed": 35.20,
      "currency": "usd"
    },
    "developerVerified": false
  }
}
```

Response fields:

| Field | Type | Description |
|---|---|---|
| data.email | string | Current account email. |
| data.role | string/null | Account role, such as `consumer`. |
| data.credit | object | Buyer Credits balance object. |
| data.credit.balance | number | Available Credits balance. |
| data.credit.currency | string | Credits currency, currently usually `usd`. |
| data.autoConsume | object/null | Auto-consumption safety settings and usage. |
| data.autoConsume.monthlyLimit | number/null | Monthly auto-consumption limit. |
| data.autoConsume.perOrderLimit | number/null | Per-order auto-consumption limit. |
| data.autoConsume.monthlyUsed | number/null | Current monthly used amount. |
| data.autoConsume.currency | string/null | Currency for auto-consumption amounts. |
| data.developerVerified | boolean | Whether this account has completed developer verification. |

## A27 `GET /agent/account/profile`

View the current user's Profile.

```http
GET /agent/account/profile
Authorization: Bearer {token}
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "userId": "019d3c7f-fe51-7c57-aa2e-8e1055bb36a5",
    "profile": "I am a long-time follower of AI Agents and automation workflows, with a preference for productivity tools."
  }
}
```

Response fields:

| Field | Type | Description |
|---|---|---|
| data.userId | string | Current user ID. |
| data.profile | string/null | Current profile text. `null` means the user has not saved a profile yet. |

## A28 `PUT /agent/account/profile`

Update the current user's Profile.

```http
PUT /agent/account/profile
Authorization: Bearer {token}
Content-Type: application/json

{
  "profile": "Enter new personal description here"
}
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": null
}
```

Request fields:

| Field | Type | Required | Description |
|---|---|---|---|
| profile | string | Yes | New profile text. Use an empty string to clear the profile. |

Key points:

- `profile` can be an empty string to clear the profile
- There is no `GET /user-skill/version` in the current public API documentation
