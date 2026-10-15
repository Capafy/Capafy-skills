# User Skill API Reference

Shared authentication, units and endpoint index: [00_overview.md](00_overview.md).

## A25 `GET /agent/agent/agents/{agentId}/package`

Download a Skill package

Obtain the installation package URL for a product's currently published version. Free packages still require login; paid packages also require a valid purchase record.

#### Endpoint details

`GET /agent/agent/agents/{agentId}/package`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| agentId | path string | Yes | Actual ID of the target download-type Agent |

No body or query parameters.

#### Permission rules

- Agent main status must be online; both main and version types must be download.
- The card must be the latest published version, have passed review, and have a bound installation package.
- The version must have a billing plan and the package must have packageUrl.
- The package is free if any plan's relevant amount is non-null and <=0: oneTimeFee for download, hourlyPrice for hourly, cyclePrice for subscription.
- Non-free packages require a valid purchase record for that agentId owned by the current user.

#### Successful response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "skillInstall": {
      "url": "https://example.com/signed-package-url",
      "licenseId": null
    },
    "thinSkillTemplate": null
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| skillInstall | object | Skill installation information |
| skillInstall.url | string | Installation package URL; GET directly |
| skillInstall.licenseId | null | Always null in this product-based download endpoint |
| thinSkillTemplate | null | Always null in this endpoint |

The endpoint first attempts to sign a storage download URL. If signing fails and the original packageUrl is HTTP/HTTPS, it returns that original URL. Presigned links follow the expires configuration; request another after expiration.

#### Failure cases

| code | Scenario |
| --- | --- |
| 400 | Empty Agent ID |
| 2004 | Agent does not exist |
| 2010 | Agent unpublished, not download-type, no downloadable version, no billing plan, or no package URL |
| 4047 | Non-free package not yet purchased |
| 401 / 1007 | Missing or invalid Access Token |

#### Download delivery

On success, read data.skillInstall.url and download directly. licenseId is null in this product-based endpoint; use the purchased-order download endpoint when an order-associated License is needed. thinSkillTemplate is null; cloud-hosted templates are not provided here.

Free packages require no product order but still need a valid Access Token. Paid packages return 4047 when purchase validation fails. Call again for a fresh URL after expiration.

## A23 `GET /agent/orders/buyer/{orderId}/download`

Get order download information

Deliver downloads according to a purchased order: download products provide Skill installation information, while cloud-hosted products provide Thin Skill template installation information.

#### Endpoint details

`GET /agent/orders/buyer/{orderId}/download`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| orderId | path string | Yes | Buyer order or subscription bill ID: buy- / hou- / cre- / str- |

No body or query parameters. Installation information is returned according to order type.

#### Response fields

| Field | Type | Description |
| --- | --- | --- |
| skillInstall | object | Skill installation information; returned only for download orders |
| thinSkillTemplate | object | Thin Skill template installation information |

##### skillInstall

| Field | Type | Description |
| --- | --- | --- |
| url | string | Temporary download URL signed according to configuration; GET directly and call this endpoint again after expiration |
| licenseId | string | Order-associated License ID; null if not enabled or bound |

##### thinSkillTemplate

| Field | Type | Description |
| --- | --- | --- |
| thinSkillTemplateId | string | Template ID |
| folderName | string | Local installation directory name |
| objectKey | string | S3 object path |
| downloadUrl | string | Template download URL |
| sha256 | string | Package artifact SHA-256 |

#### Successful response

Download order:

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "skillInstall": {
      "url": "https://example.com/signed-package-url",
      "licenseId": "license_123"
    },
    "thinSkillTemplate": null
  }
}
```

Hosted order:

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "skillInstall": null,
    "thinSkillTemplate": {
      "thinSkillTemplateId": "template_123",
      "folderName": "My_Agent",
      "objectKey": "thin-skill/templates/template_123/My_Agent.zip",
      "downloadUrl": "https://example.com/signed-template-url",
      "sha256": "abc123"
    }
  }
}
```

#### Download rules

- The order must belong to the current user. Download orders allow downloads in paid / completed. In refunding, repeat downloads are also allowed if this user previously obtained a download URL successfully for the Agent.
- Download orders default to the latest published, review-approved version with a bound package. Eligible published packages remain accessible after the Agent is delisted.
- Hosted hourly orders and Credit / Stripe subscription bills require paid / completed and return the Thin Skill template for the order's version.
- Successfully generating a download-type URL records download activity and writes firstDownloadAt on the first issuance.
- The storage service signs the returned links; validity depends on deployment configuration. Save licenseId if present and download using url / downloadUrl.

#### Failure cases

| code | Scenario |
| --- | --- |
| 4003 | Order missing or not owned by the user |
| 4047 | Order status disallows downloading |
| 2014 | No downloadable Skill version |
| 2024 | Package missing or has no packageUrl |
| 4018 | Free trial, daily-free, and request-pack orders do not support this download operation |
| 4019 | Unsupported or unrecognized order type |
| 401 / 1007 | Missing or invalid Access Token |

Storage signing or Thin Skill template query failures return the corresponding business errors.

#### Using installation information

Read either skillInstall or thinSkillTemplate according to order type. For downloads, use url and retain a nonempty licenseId for the corresponding installation authorization. For hosted products, download the template through downloadUrl and use folderName as the local directory name; sha256 verifies the downloaded artifact.

This endpoint has no query parameter for selecting a historical version. Downloads default to the latest eligible published package; repeat downloads during refunding follow this chapter's download rules. Save the order ID and installation information, and request a fresh temporary URL after expiration.

## A24 `GET /agent/skill/{agentId}/versions`

List Skill version history

Query version history for Agents owned by the current account. Ordinary buyers cannot read another developer's version history solely through a purchase record; the returned list is not a list of versions downloadable by buyers.

#### Endpoint details

`GET /agent/skill/{agentId}/versions`

Requires Access Token authentication; only the current user's data is accessible.


#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| agentId | path string | Yes | Agent ID owned by the current user |

No body, query parameters, or pagination.

#### Actual permissions and query scope

This endpoint validates product ownership using Agent ID and the signed-in user; the current user must own the Agent. A purchase record alone does not allow ordinary buyers to query someone else's Agent versions.

Returns all nondeleted version cards for the Agent in descending versionNo and createdAt order. No additional filtering by type, publication status, review result, or bound package is applied, so the response cannot directly serve as a buyer-downloadable version list.

#### Successful response

```json
{
  "code": 0,
  "msg": "ok",
  "data": [
    {
      "appVersionId": "version_123",
      "agentId": "agent_123",
      "agentType": "download",
      "name": "Demo Skill",
      "desc": "Productivity tool",
      "versionNo": 3,
      "versionName": "v1.0.2",
      "title": "Demo Skill",
      "shortDescription": "Version notes",
      "createdAt": 1791763200000,
      "updatedAt": 1791763200000
    }
  ]
}
```

| Field | Type | Description |
| --- | --- | --- |
| appVersionId | string | Card agentVersionId, exposed as appVersionId |
| agentId | string | Agent ID |
| agentType | string | Product type; the current service does not require download |
| name | string | Agent name |
| desc | string | Agent short description |
| versionNo | int | Version number |
| versionName | string | Version name |
| title | string | Version title |
| shortDescription | string | Version short description |
| createdAt | long | Creation time as a millisecond timestamp |
| updatedAt | long | Update time as a millisecond timestamp |

The buyer order download endpoint has no version-selection parameter. appVersionId returned here is not a request parameter for Agent buyer order downloads.

#### Failure cases

A missing Agent or one not owned by the user returns AGENT_NOT_FOUND(2004); no cards returns data=[]. Missing or invalid Access Tokens return authentication errors.

#### Buyer integration limits

This endpoint does not query versions of all purchased products. Having only a purchase record without owning the Agent returns 2004. Changing userId cannot request someone else's versions because identity comes from the Access Token.

appVersionId identifies a historical card version but is not a request parameter for Agent order downloads. The list may include unpublished versions; an appVersionId alone does not guarantee download availability.
