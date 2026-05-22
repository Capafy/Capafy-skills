# User Skill API Chat

## A10 `POST /agent/relay/instances/{instanceId}/messages`

Send a new message to an instance and establish SSE.

```http
POST /agent/relay/instances/{instanceId}/messages
Authorization: Bearer {token}
Content-Type: application/json
Accept: text/event-stream, application/json

{
  "content": "Please help me analyze this campaign data and provide optimization recommendations",
  "originalQuestion": "Analyze from three dimensions — ROI, CTR, and conversion rate — and generate follow-up action recommendations",
  "nextStepPlan": "If CTR is found to be low, continue analyzing creatives and targeting issues next",
  "files": [{"url": "https://example.com/data.csv", "originalFileName": "data.csv"}]
}
```

Path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| instanceId | string | Yes | Purchased Agent instance ID. |

Request fields:

| Field | Type | Required | Description |
|---|---|---|---|
| content | string | Yes | Message content sent to the Agent. Must not be blank. |
| originalQuestion | string | No | Original user request for task context and later reconciliation. Stored with the task state. |
| nextStepPlan | string | No | Planned next step for task context. Stored with the task state. |
| files | array | No | Attached file references. Each item is `{ "url": string, "originalFileName": string }`. |

SSE events:

- `message`
- `timeout`
- `done`

SSE payload fields:

| Field | Type | Description |
|---|---|---|
| type | string | Event type: `message`, `timeout`, or `done`. |
| messageId | string | Message/task ID for this request. |
| seq | int | Sequence number within the current task. |
| time | long | Unix timestamp in milliseconds. |
| content | string/null | Text payload. `done` may use `null`. |
| files | array | File references returned by the Agent, each shaped as `{url, originalFileName}`. |

Rules:

- `content` is required
- `originalQuestion` and `nextStepPlan` are stored only and not forwarded directly to the creator execution chain
- `files` is optional; a list of file objects, each with the structure `{url, originalFileName}`, passed through to the creator container
- If the instance already has an active task, returns a `409` conflict JSON

## A11 `POST /agent/relay/instances/{instanceId}/messages/reconnect`

Reconnect SSE for an existing task.

```http
POST /agent/relay/instances/{instanceId}/messages/reconnect
Authorization: Bearer {token}
Accept: text/event-stream, application/json
```

Path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| instanceId | string | Yes | Instance whose active task should be reconnected. |

There are three success forms:

- Returns `text/event-stream` — reconnect successful
- Returns `{ "status": "no_active_task" }`
- Returns a plain JSON fallback when the task has already switched to offline result mode

JSON fallback fields:

| Field | Type | Description |
|---|---|---|
| status | string | Fallback status, for example `no_active_task`. |
| type | string/null | Some fallback responses use event-like types such as `timeout`. |
| message | string/null | Human-readable fallback message when provided. |

## A12 `GET /agent/relay/instances/{instanceId}/messages`

Retrieve offline messages.

```http
GET /agent/relay/instances/{instanceId}/messages
Authorization: Bearer {token}
```

```json
{
  "messages": [
    {
      "type": "message",
      "content": "Analysis complete: recommend optimizing the first 3 seconds of creatives and narrowing audience targeting for testing.",
      "partialResult": null,
      "messageId": "msg_2001",
      "timestamp": 1711111112222,
      "originalQuestion": "Analyze from three dimensions — ROI, CTR, and conversion rate — and generate follow-up action recommendations",
      "nextStepPlan": "If CTR is found to be low, continue analyzing creatives and targeting issues next",
      "files": [{"url": "https://example.com/report.pdf", "originalFileName": "report.pdf"}]
    }
  ]
}
```

Path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| instanceId | string | Yes | Instance whose offline queue should be read. |

Response fields:

| Field | Type | Description |
|---|---|---|
| messages | array | Current batch of offline messages. May be empty. Reading consumes the queue. |
| messages[].type | string | `message` or `done`. Startup placeholders are projected as `message`. |
| messages[].messageId | string | Message/task ID. |
| messages[].seq | int/null | Sequence number within the task, when available. |
| messages[].time | long/null | Unix timestamp in milliseconds, when available. |
| messages[].timestamp | long/null | Compatibility timestamp field used by some examples/clients. |
| messages[].content | string/null | Text content. `done` may use `null`. |
| messages[].partialResult | string/object/null | Partial result when the runtime provides one; otherwise `null`. |
| messages[].originalQuestion | string/null | Original request, mainly returned with final messages. |
| messages[].nextStepPlan | string/null | Stored next-step plan, mainly returned with final messages. |
| messages[].files | array | File references, each shaped as `{url, originalFileName}`. |

Rules:

- Currently only returns `type=message` and `type=done`
- This is a one-time consumption endpoint; reading clears the Redis queue

## A13 `POST /agent/relay/instances/{instanceId}/interrupt`

Request interruption of the current active task.

```http
POST /agent/relay/instances/{instanceId}/interrupt
Authorization: Bearer {token}
```

```json
{
  "status": "interrupt_requested",
  "activeMessageId": "msg_123",
  "message": "Interrupt signal sent to Agent. The current SSE will close after the interrupt result arrives."
}
```

Path parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| instanceId | string | Yes | Instance whose active task should be interrupted. |

Response fields:

| Field | Type | Description |
|---|---|---|
| status | string | Current response status, normally `interrupt_requested` on accepted interruption. |
| activeMessageId | string/null | Active task/message ID that received the interrupt request. |
| message | string | Human-readable status message. |

Rules:

- A `200` response only means the request was accepted — it does not mean the task has already stopped
- The actual termination signal typically arrives on the current SSE after interruption is accepted
- If there is no active task, returns `404` with `error=no_active_task`

## A14 `POST /agent/file/presign/upload`

Get a presigned URL for object upload.

```http
POST /agent/file/presign/upload
Authorization: Bearer {token}
Content-Type: application/json

{
  "fileName": "avatar.png",
  "contentType": "image/png",
  "bizType": "buyer_agent"
}
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "uploadMethod": "PUT",
    "uploadUrl": "https://bucket.s3.amazonaws.com/...",
    "headers": { "Content-Type": "image/png" },
    "objectKey": "public/agent/buyer/.../avatar.png",
    "publicUrl": null,
    "expiresInSeconds": 1800
  }
}
```

Request fields:

| Field | Type | Required | Description |
|---|---|---|---|
| fileName | string | Yes | Original file name. Used for object key generation and display. |
| contentType | string | Yes | MIME type to bind to the uploaded object, such as `image/png` or `text/csv`. |
| bizType | string | Yes | Upload business type. Buyer-side Agent files should use `buyer_agent`. |

Response fields:

| Field | Type | Description |
|---|---|---|
| data.uploadMethod | string | Upload method, currently `PUT`. |
| data.uploadUrl | string | Presigned upload URL. Send the binary file directly to this URL. |
| data.headers | object | Headers that must be included in the upload request; currently includes `Content-Type`. |
| data.objectKey | string | Stable object storage key. Save it for later download/signing. |
| data.originalFileName | string | Original file name echoed from `fileName`. |
| data.publicUrl | string/null | Public URL when configured; otherwise `null`. |
| data.expiresInSeconds | long | Presigned URL lifetime in seconds. Minimum is 180 seconds. |

Rules:

- First call the business endpoint to get `uploadUrl`
- Then issue a `PUT` to `uploadUrl`
- Include the returned `headers` in that `PUT`
- Save `objectKey` after a successful upload

## A15 `POST /agent/file/presign/download`

Get a presigned download URL for an object by `objectKey`.

```http
POST /agent/file/presign/download
Authorization: Bearer {token}
Content-Type: application/json

{
  "objectKey": "public/agent/buyer/.../avatar.png"
}
```

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "downloadMethod": "GET",
    "downloadUrl": "https://bucket.s3.amazonaws.com/...",
    "objectKey": "public/agent/buyer/.../avatar.png",
    "expiresInSeconds": 1800
  }
}
```

Request fields:

| Field | Type | Required | Description |
|---|---|---|---|
| objectKey | string | Yes | Object storage key returned by A14. Maximum length is 1024 characters. |

Response fields:

| Field | Type | Description |
|---|---|---|
| data.downloadMethod | string | Download method, currently `GET`. |
| data.downloadUrl | string | Presigned download URL. |
| data.objectKey | string | Normalized object key. |
| data.expiresInSeconds | long | Presigned URL lifetime in seconds. Minimum is 180 seconds. |

## Notes

- When sending a message, pass file objects to the Agent via the `files` field (each with the structure `{url, originalFileName}`); Agent messages may also carry `files`.
- SSE `message`, `done`, and `timeout` events all carry `messageId` for reconciliation.
- There is no `POST /agent/relay/instances/{instanceId}/files` in the current API documentation.
- After uploading an object, prefer a stable URL (e.g. `publicUrl` from the upload response) when passing it to the Agent; do not treat a temporary download presigned URL as a long-lived file attachment.
