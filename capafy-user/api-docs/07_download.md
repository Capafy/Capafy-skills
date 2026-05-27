# User Skill API Download

## A23 `GET /agent/orders/buyer/{orderId}/download`

Get download information for a specified order. Both Download Agent orders and Run Online orders use this endpoint. Run Online orders download the Thin Skill.

```http
GET /agent/orders/buyer/{orderId}/download
Authorization: Bearer {token}
```

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| orderId | string | Yes | Order ID; supports `buy-`, `hou-`, `cre-`, `str-` prefixes |

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| appVersionId | string | No | Specific historical Skill version ID to download; Download Agent orders only |

Compatibility note: current backend reference sections disagree on this parameter. The version-list section documents `appVersionId`, while the order-download section says the endpoint currently has no query parameters. Confirm backend support before relying on historical-version download in new integrations.

### Download Agent Order Response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "skillInstall": {
      "url": "https://s3.amazonaws.com/bucket/xxx?X-Amz-Signature=..."
    },
    "thinSkillTemplate": null
  }
}
```

### Run Online Order Response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "skillInstall": null,
    "thinSkillTemplate": {
      "thinSkillTemplateId": "tst_019d3c7f-58cc-7437-a567-6e02b2c3d479",
      "folderName": "capafy-agent-agent_123",
      "objectKey": "thin-skill/templates/tst_xxx/capafy-agent-agent_123.zip",
      "downloadUrl": "https://example.com/presigned-download-url",
      "sha256": "abc123"
    }
  }
}
```

Key points:

- Download Agent orders return `skillInstall.url` (presigned; valid for 60 minutes)
- Run Online orders return `thinSkillTemplate` (includes template ID, folder name, download URL, SHA-256)
- Only orders with status `paid` / `completed` are allowed to download
- Re-call this endpoint to get a new link after the link expires

Response fields:

| Field | Type | Description |
|---|---|---|
| data.skillInstall | object/null | Download Agent install information. `null` for Run Online orders. |
| data.skillInstall.url | string | Temporary presigned package download URL. Use it with HTTP GET before it expires. |
| data.thinSkillTemplate | object/null | Thin Skill template metadata. Present for Run Online orders. |
| data.thinSkillTemplate.thinSkillTemplateId | string | Thin Skill template ID. |
| data.thinSkillTemplate.folderName | string | Suggested local folder name, commonly `capafy-agent-{agentId}`. |
| data.thinSkillTemplate.objectKey | string | Object storage key for the Thin Skill template archive. |
| data.thinSkillTemplate.downloadUrl | string | Temporary presigned template download URL. |
| data.thinSkillTemplate.sha256 | string/null | SHA-256 checksum when available. |

### Error Codes

| Scenario | Error Code | Description |
|----------|------------|-------------|
| Unsupported orderId type | 4019 | This order type does not support download |
| orderId not found or does not belong to current buyer | 4003 | Query failed |
| Order not paid or status not downloadable | 4047 | Only `paid` / `completed` allowed |
| Specified historical version is invalid | 2014 | Only relevant when backend support for `appVersionId` is enabled |
| Install package does not exist | 2024 | No install package bound or packageUrl is empty |

## A24 `GET /agent/skill/{agentId}/versions`

Query the version history of a specified Skill. Returns only officially published versions with an install package, sorted by version number in descending order.

```http
GET /agent/skill/{agentId}/versions
Authorization: Bearer {token}
```

Path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| agentId | string | Yes | Download Agent ID. Run Online Agents are not valid here. |

```json
{
  "code": 0,
  "msg": "ok",
  "data": [
    {
      "appVersionId": "0195c4f8-0a1b-7d1c-a51a-4d7a2c9e1001",
      "agentId": "agent_123",
      "agentType": "download",
      "name": "capafy SQL Helper",
      "desc": "Helps you analyze SQL, generate queries, and explain execution plans",
      "versionNo": 3,
      "versionName": "v1.3.0",
      "title": "SQL Helper Pro",
      "shortDescription": "Added explain analysis and index recommendations",
      "createdAt": 1775801989000,
      "updatedAt": 1775802989000
    }
  ]
}
```

Key points:

- Only applicable to Download Agents (`agentType=download`); not applicable to Run Online Agents
- Not paginated; returns all officially published versions at once
- Use `appVersionId` with A23 only after confirming the backend supports the query parameter
- Does not return drafts, under-review, or review-failed versions
- Returns `2014` if `agentId` does not exist or is not a Skill

Response fields:

| Field | Type | Description |
|---|---|---|
| data[] | array | Historical published Skill versions, sorted by `versionNo` descending. |
| data[].appVersionId | string | Historical version ID, corresponding to backend `agent_version_id`. |
| data[].agentId | string | Agent ID. |
| data[].agentType | string | Always `download` for this endpoint. |
| data[].name | string | Agent main-table name. |
| data[].desc | string/null | Agent main-table description. |
| data[].versionNo | int | Version number. |
| data[].versionName | string/null | Version label. |
| data[].title | string | Version title. |
| data[].shortDescription | string/null | Version short description. |
| data[].createdAt | long | Creation time in Unix milliseconds. |
| data[].updatedAt | long | Last update time in Unix milliseconds. |

## A25 `GET /agent/agent/agents/{agentId}/package`

Get the download URL for the currently listed Skill version by agentId. Only supports Download Agents (`agentType=download`); does not support Run Online Agents.

```http
GET /agent/agent/agents/{agentId}/package
Authorization: Bearer {token}
```

Path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| agentId | string | Yes | Download Agent ID. |

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "skillInstall": {
      "url": "https://example-bucket.s3.amazonaws.com/agent/download-package/demo.tar.gz?X-Amz-Signature=..."
    },
    "thinSkillTemplate": null
  }
}
```

Key points:

- Only supports `agentType=download`; returns `2010` for Run Online Agents
- Free Skills (all billing plan amounts ≤ 0) can be downloaded without a purchase
- Paid Skills require the current buyer to have an existing purchase record; returns `4047` otherwise
- The returned URL is a presigned download URL with an expiry; use it promptly
- Difference from A23: A23 downloads by orderId; this endpoint downloads by agentId and always returns the latest listed version

Response fields:

| Field | Type | Description |
|---|---|---|
| data.skillInstall | object | Latest listed Skill install package metadata. |
| data.skillInstall.url | string | Temporary package download URL, usually presigned. |
| data.thinSkillTemplate | null | Always `null` for this endpoint because it only supports Download Agents. |

### Error Codes

| Scenario | Error Code | Description |
|----------|------------|-------------|
| Agent not found | 2004 | AGENT_NOT_FOUND |
| Agent not online or not a Skill | 2010 | AGENT_NOT_AVAILABLE |
| No downloadable package | 2010 | Current version has no install package bound |
| Paid Skill not purchased | 4047 | ORDER_DOWNLOAD_NOT_ALLOWED |

## Runtime Note

- `scripts/install_package.py --order-id <orderId>` calls A23 to download and install
- `thin_skill_template_id` is read from `data.thinSkillTemplate.thinSkillTemplateId` in the response JSON
