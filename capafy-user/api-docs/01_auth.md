# User Skill API Reference

Shared authentication, units and endpoint index: [00_overview.md](00_overview.md).

## User authentication (Agent)

Obtain the buyer identity and Agent Access Token through an email verification code. The first login registers the user automatically; use the token for subsequent purchases, top-ups, instance operations, and account operations.

#### Request flow

Send an email verification code, then submit it with `source` set to `agent` to obtain `accessToken`. Neither endpoint requires authentication, and both return the standard JSON envelope.

## A01 `POST /auth/login`

Send a login verification code

`POST /auth/login`, with the `Content-Type: application/json` header.

```json
{
  "loginMethod": "email",
  "email": "buyer@example.com"
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| loginMethod | string | Yes | Must be `email`; cannot be empty |
| email | string | Yes | A nonempty, valid email address |

##### Successful response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "challengeId": "ch_a1B2c3D4e5F6g7H8i9J0",
    "expiresInSec": 300
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| challengeId | string | Challenge ID to include in verification |
| expiresInSec | int | Validity in seconds; currently 300 |

Failed verification retains the challenge until expiration; successful verification deletes it. Development and test environments allow the fixed verification code `666666`.

## A02 `POST /auth/login/verify`

Verify the code and log in

`POST /auth/login/verify`, with the `Content-Type: application/json` header.

```json
{
  "challengeId": "ch_a1B2c3D4e5F6g7H8i9J0",
  "code": "382916",
  "source": "agent"
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| challengeId | string | Yes | ID returned by the send-code endpoint |
| code | string | Yes | Email verification code; cannot be empty |
| source | string | Yes | Set to `agent` for Agent requests |

##### Optional request headers

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| X-Timezone | string | No | User timezone |
| X-Language-Code | string | No | Registration language for new users; defaults to `en` and is ignored for existing users |
| X-Ad-From | string | No | Advertising source |
| X-Ad-Click-Id | string | No | Advertising click ID |
| X-Ad-Click-Id-Type | string | No | Advertising click ID type |
| X-Ad-Scene | string | No | Advertising landing page URL |

##### Successful response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "userId": "user_123",
    "name": "buyer@example.com",
    "email": "buyer@example.com",
    "developerVerified": false,
    "status": "active",
    "credits": 10,
    "creditsFrozen": 0,
    "balancePending": 0,
    "balanceConfirmed": 0,
    "balancePayout": 0,
    "currency": "usd",
    "accessToken": "am_sk_xxx",
    "isRegister": true
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| userId | string | Current user ID |
| name | string | User display name |
| email | string | Login email address |
| avatarUrl | string | Avatar URL; omitted when not set |
| developerVerified | boolean | Whether developer verification is complete |
| status | string | Current user status; active after a normal successful login |
| credits | number | Credits balance in major units |
| creditsFrozen | number | Buyer's frozen Credits balance in major units |
| balancePending | number | Developer balance awaiting confirmation, in major units |
| balanceConfirmed | number | Developer confirmed balance in major units |
| balancePayout | number | Developer balance awaiting settlement, in major units |
| currency | string | Wallet currency; currently usd |
| accessToken | string | Access token for subsequent `/agent/` requests |
| isRegister | boolean | Whether this login registered a new user |

Fields with null values are omitted from response objects; for example, `avatarUrl` is omitted when no avatar is set. The first login registers the user and initializes the wallet and default Access Token. Existing users receive their current usable default Access Token; a missing token is created. The account must be `active`.

##### Failure cases

Invalid email addresses or request fields return parameter errors. A missing or expired challenge, or an incorrect code, returns an invalid-code error. Email delivery failures and unavailable accounts return the corresponding business errors. An incorrect code can be retried within the same challenge's validity period.

#### Login integration and error handling

Save challengeId after sending the code and complete verification within expiresInSec. A successfully verified challengeId cannot be reused; failed verification can be retried before expiration. Read the token only from data.accessToken in the successful verification response; do not derive it from challengeId.

| code | Description | Recommended handling |
| --- | --- | --- |
| 400 | Missing request fields or invalid email format | Correct the fields and resubmit |
| 1003 | Incorrect verification code or invalid challenge | Correct the code if unexpired; otherwise send a new code |
| 1005 | Account disabled | Display the failure reason and stop the purchase |
| 1010 | Failed to send the email verification code | Send again later |
| 1013 | Verification-code sending limit reached | Wait for the limit to clear; avoid repeated clicks |
