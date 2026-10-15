# User Skill API Reference

Shared authentication, units and endpoint index: [00_overview.md](00_overview.md).

## A10 `POST /agent/relay/instances/{instanceId}/messages`

Send a message and open an SSE stream (Agent)

Start a task on an available instance owned by the user and receive live messages. Prepare instanceId and any text or file attachments before sending.

#### Endpoint details

`POST /agent/relay/instances/{instanceId}/messages`

Requires Access Token authentication; only the current user's data is accessible.

Success returns SSE or raw JSON, without the standard JSON envelope. Parameter errors, business errors, or authentication failures may return `{code,msg,data}`; callers must check both HTTP status and Content-Type.

Use Content-Type: application/json; Accept: text/event-stream is optional.

#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| instanceId | path string | Yes | ID of an instance owned by the user that permits messages |
| content | body string | No | Message content; at most 20000 characters; may be empty |
| originalQuestion | body string | No | Original question; at most 1000 characters |
| nextStepPlan | body string | No | Next-step plan; at most 1000 characters |
| files | body array | No | File objects, each containing url and originalFileName |

```json
{
  "content": "Please analyze this report",
  "originalQuestion": "Evaluate performance and make recommendations",
  "nextStepPlan": "Optimize the next campaign",
  "files": [
    {
      "url": "agent/buyer/user_123/2026/10/12/report.csv",
      "originalFileName": "report.csv"
    }
  ]
}
```

files[].url accepts an HTTP URL or storage objectKey; the platform converts it to an accessible file URL as needed. File entries must be JSON objects.

#### Successful response: SSE

HTTP 200, Content-Type: text/event-stream. Event names are message / timeout / done, matching the JSON type.

| Field | Type | Description |
| --- | --- | --- |
| type | string | Message type: message / timeout / done. |
| messageId | string | Message ID assigned by the platform. |
| seq | int | Sequence number within the turn; startup and reconnection notices are usually 0 |
| time | long | Message timestamp in milliseconds. |
| content | string | Nonempty content has a `Capafy` prefix followed by a fullwidth colon (`U+FF1A`); content may be null, and done content follows the actual upstream response |
| incremental | boolean | Whether this is an incremental fragment; nullable; render incrementally when true |
| files | array | File list; currently used mainly for attachments delivered with done. |
| askQuestions | array | Structured questions returned only with done; null for other messages |
| originalQuestion | string | Original question added for done when it matches the current turn |
| nextStepPlan | string | Next-step plan added for done when it matches the current turn |
| modelUsage | object | Usage object keyed by model code; null if not reported |
| usageAudit | object | Usage audit object; null if not reported |

##### files[]

| Field | Type | Description |
| --- | --- | --- |
| url | string | File download URL. |
| originalFileName | string | Original filename. |

##### askQuestions[]

The structured-question protocol specifies 1-4 questions, each with 2-4 options.

| Field | Type | Description |
| --- | --- | --- |
| id | string | Question identifier. |
| header | string | Short label used as the button group title and when filling in answers. |
| question | string | Complete question text. |
| options | array | Available options; the protocol specifies 2-4. |
| multiSelect | boolean | Whether multiple selections are allowed; defaults to false. |
| allowOther | boolean | Whether the user may supply a custom answer outside the options; defaults to false. |

##### askQuestions[].options[]

| Field | Type | Description |
| --- | --- | --- |
| label | string | Button display text. |
| description | string | Additional option description. |

##### modelUsage[modelCode]

| Field | Type | Description |
| --- | --- | --- |
| inputTokens | long | Input token count. |
| outputTokens | long | Output token count. |
| cacheReadInputTokens | long | Cache read token count. |
| cacheCreationInputTokens | long | Cache creation token count. |
| webSearchRequests | long | Web search request count. |
| costUSD | number | Cost of this model call in USD. |
| contextWindow | long | Model context window size. |
| maxOutputTokens | long | Model maximum output token count. |

##### usageAudit

| Field | Type | Description |
| --- | --- | --- |
| requestId | string | Upstream request ID. |
| provider | string | Usage provider. |
| modelRequested | string | Model name specified in the request. |
| modelActual | string | Model actually used for execution. |
| inputUncached | long | Uncached input token count. |
| cacheRead | long | Cache read token count. |
| cacheWrite | long | Cache write token count. |
| output | long | Output token count. |
| reasoningOutput | long | Reasoning output token count. |
| total | long | Total token count. |
| scope | string | Usage scope: request / turn / session. |
| usageStatus | string | Usage reporting status: reported / partial / unknown. |
| status | string | Task status: completed / failed / aborted. |
| rawSource | string | Raw usage source. |

##### Message example

message:

```json
{
  "type": "message",
  "messageId": "msg_123",
  "seq": 1,
  "time": 1791763200000,
  "content": "Capafy：Analyzing data.",
  "incremental": false,
  "files": [],
  "askQuestions": null,
  "originalQuestion": null,
  "nextStepPlan": null,
  "modelUsage": null,
  "usageAudit": null
}
```

done:

```json
{
  "type": "done",
  "messageId": "msg_123",
  "seq": 2,
  "time": 1791763200000,
  "content": null,
  "incremental": false,
  "files": [
    {
      "url": "https://example.com/report.pdf",
      "originalFileName": "report.pdf"
    }
  ],
  "askQuestions": null,
  "originalQuestion": "Please analyze the report",
  "nextStepPlan": "Recommend next steps",
  "modelUsage": null,
  "usageAudit": null
}
```

Complete SSE fragment, showing only key fields:

```text
event: message
data: {"type":"message","messageId":"msg_123","seq":0,"time":1791763200000,"content":"Capafy：Received your message...","files":[]}

event: message
data: {"type":"message","messageId":"msg_123","seq":0,"time":1791763201000,"content":"Capafy：Starting...","files":[]}

event: done
data: {"type":"done","messageId":"msg_123","seq":2,"time":1791763210000,"content":null,"files":[]}
```

Startup notices map to message; other internal process messages are filtered. Content already includes the platform prefix, so clients need not add it again. done can return content, files, structured questions, and usage information; finish handling the turn after reading them.

Long tasks may emit timeout and close the current SSE connection while execution continues. Obtain results afterward through reconnection or offline reads.

#### Failure response

HTTP 409:

```json
{
  "error": "message_in_progress",
  "message": "There is an active task in progress. Sending a new message will interrupt the previous execution. If you need to interrupt the current task, please call the interrupt endpoint first.",
  "activeMessageId": "msg_123",
  "interruptUrl": "/agent/relay/instances/instance_123/interrupt"
}
```

Contention for the same instance's flow lock can also return this structure; activeMessageId may be null. To stop the current task, call interruptUrl; do not immediately send a second message concurrently.

| HTTP status | Scenario |
| --- | --- |
| 400 | Field length exceeded, invalid JSON or file item, or message blocked by high-risk checks |
| 404 | Instance missing or unauthorized |
| 409 | Current task is running or message orchestration lock is busy |
| 410 | idle / purged instances cannot receive messages, or the current task has expired |
| 429 | Instance message quota exhausted for the current cycle |

Handle authentication errors according to the authentication layer's response. An accepted message creates a new activeMessageId turn. Use reconnection after disconnection; offline reads query only the current turn.

#### SSE client handling

This endpoint uses POST. Browser EventSource cannot directly send its JSON body; use a streaming client supporting POST or an equivalent client. Parse event and data according to SSE, separating events with blank lines. Do not assume each network read contains exactly one complete JSON object.

With incremental=true, append content fragments in order for the same messageId; treat nonincremental messages independently. Multiple platform startup notices may have seq=0, so do not deduplicate by seq alone. done delivers the turn's result; content may be empty, but files, askQuestions, and usage fields must still be read.

After timeout, the server may close the connection while the task continues. Retain instanceId and messageId and use reconnection or offline reads to obtain later results. Network disconnection does not interrupt a task; call interrupt if the user wants execution stopped.

## A11 `POST /agent/relay/instances/{instanceId}/messages/reconnect`

Reconnect relay SSE messages (Agent)

Reconnect to the current task still running after a network interruption. Reconnection retains the original turn and does not resubmit the buyer message.

#### Endpoint details

`POST /agent/relay/instances/{instanceId}/messages/reconnect`

Requires Access Token authentication; only the current user's data is accessible.

Success returns SSE or raw JSON, without the standard JSON envelope. Parameter errors, business errors, or authentication failures may return `{code,msg,data}`; callers must check both HTTP status and Content-Type.

#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| instanceId | path string | Yes | Target instance ID |

No body or query parameters. Accept: text/event-stream, application/json is optional.

#### Response modes

| HTTP status | Content-Type | Description |
| --- | --- | --- |
| 200 | text/event-stream | Current user's task is still running; establish a new SSE stream |
| 200 | application/json | No running task or no permission for the instance |
| 409 | application/json | Instance flow lock is busy |
| 410 | application/json | Current task has expired |

##### Successful reconnection

Immediately push a message notice, then continue streaming messages for the same turn.

```json
{
  "type": "message",
  "messageId": "msg_123",
  "seq": 0,
  "time": 1791763200000,
  "content": "Capafy：Reconnected.",
  "incremental": null,
  "files": [],
  "askQuestions": null,
  "originalQuestion": null,
  "nextStepPlan": null,
  "modelUsage": null,
  "usageAudit": null
}
```

Continue receiving message / timeout / done. Reconnection creates no task and sends no new buyer message. Messages may continue arriving, but replay of all previously received messages is not guaranteed; use offline reads for the complete current turn.

##### SSE message fields

| Field | Type | Description |
| --- | --- | --- |
| type | string | Message type: message / timeout / done. |
| messageId | string | Message ID assigned by the platform. |
| seq | int | Sequence number within the turn; startup and reconnection notices are usually 0 |
| time | long | Message timestamp in milliseconds. |
| content | string | Nonempty content has a `Capafy` prefix followed by a fullwidth colon (`U+FF1A`); content may be null, and done content follows the actual upstream response |
| incremental | boolean | Whether this is an incremental fragment; nullable; render incrementally when true |
| files | array | File list; currently used mainly for attachments delivered with done. |
| askQuestions | array | Structured questions returned only with done; null for other messages |
| originalQuestion | string | Original question added for done when it matches the current turn |
| nextStepPlan | string | Next-step plan added for done when it matches the current turn |
| modelUsage | object | Usage object keyed by model code; null if not reported |
| usageAudit | object | Usage audit object; null if not reported |

##### files[]

| Field | Type | Description |
| --- | --- | --- |
| url | string | File download URL. |
| originalFileName | string | Original filename. |

##### askQuestions[]

The structured-question protocol specifies 1-4 questions, each with 2-4 options.

| Field | Type | Description |
| --- | --- | --- |
| id | string | Question identifier. |
| header | string | Short label used as the button group title and when filling in answers. |
| question | string | Complete question text. |
| options | array | Available options; the protocol specifies 2-4. |
| multiSelect | boolean | Whether multiple selections are allowed; defaults to false. |
| allowOther | boolean | Whether the user may supply a custom answer outside the options; defaults to false. |

##### askQuestions[].options[]

| Field | Type | Description |
| --- | --- | --- |
| label | string | Button display text. |
| description | string | Additional option description. |

##### modelUsage[modelCode]

| Field | Type | Description |
| --- | --- | --- |
| inputTokens | long | Input token count. |
| outputTokens | long | Output token count. |
| cacheReadInputTokens | long | Cache read token count. |
| cacheCreationInputTokens | long | Cache creation token count. |
| webSearchRequests | long | Web search request count. |
| costUSD | number | Cost of this model call in USD. |
| contextWindow | long | Model context window size. |
| maxOutputTokens | long | Model maximum output token count. |

##### usageAudit

| Field | Type | Description |
| --- | --- | --- |
| requestId | string | Upstream request ID. |
| provider | string | Usage provider. |
| modelRequested | string | Model name specified in the request. |
| modelActual | string | Model actually used for execution. |
| inputUncached | long | Uncached input token count. |
| cacheRead | long | Cache read token count. |
| cacheWrite | long | Cache write token count. |
| output | long | Output token count. |
| reasoningOutput | long | Reasoning output token count. |
| total | long | Total token count. |
| scope | string | Usage scope: request / turn / session. |
| usageStatus | string | Usage reporting status: reported / partial / unknown. |
| status | string | Task status: completed / failed / aborted. |
| rawSource | string | Raw usage source. |

##### No running task

```json
{
  "status": "no_active_task"
}
```

##### Instance busy

```json
{
  "error": "instance_busy",
  "message": "The instance is busy. Please try again shortly."
}
```

#### Client handling

Check both HTTP status and Content-Type. Retry instance_busy later; query offline results for no_active_task; 410 means the task expired. Do not reset the original turn's client state on reconnection.

#### Handling reconnection states

Successfully reconnected messages belong to the original activeMessageId; continue displaying that turn's execution state. no_active_task cannot distinguish a task that never ran from one that completed. If a task was previously started, read offline messages to check for done. HTTP 410 means the task expired; repeated reconnection cannot reactivate it.

A new SSE stream for the same instance takes over the original connection. Avoid maintaining multiple streams for one instance; after reconnection, use the message fields below to handle live results.

## A12 `GET /agent/relay/instances/v2/{instanceId}/messages`

Fetch offline messages (Agent)

#### Endpoint details

`GET /agent/relay/instances/v2/{instanceId}/messages`

Requires Access Token authentication; only the current user's data is accessible. Success and conflict return raw JSON, without the standard envelope. Parameter errors, business errors, or authentication failures may return `{code,msg,data}`; check both HTTP status and Content-Type.

The turn is determined by the instance's current activeMessageId; clients do not supply a turn ID. Reading saved history neither consumes nor deletes it.

#### Paginated read parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| instanceId | path string | Yes | Instance ID |
| size | query int | No | Maximum records scanned per page; default 100, maximum 200; values below 1 are treated as 1 |
| cursor | query string | No | Omit on the first request; reuse the previous page's nextCursor unchanged afterward |

The cursor binds the instance, current turn, first query's time upper bound, and last record position. It cannot be reused across instances or turns.

#### Successful paginated response

```json
{
  "messages": [
    {
      "type": "done",
      "messageId": "msg_123",
      "seq": 2,
      "time": 1791763200000,
      "content": null,
      "incremental": false,
      "files": [
        {
          "url": "https://example.com/report.pdf",
          "originalFileName": "report.pdf"
        }
      ],
      "askQuestions": null,
      "originalQuestion": "Please analyze the report",
      "nextStepPlan": "Recommend next steps",
      "modelUsage": null,
      "usageAudit": null
    }
  ],
  "activeMessageId": "msg_123",
  "size": 1,
  "hasMore": false,
  "nextCursor": null,
  "snapshotAt": 1791763220000
}
```

| Field | Type | Description |
| --- | --- | --- |
| messages | array | Visible, reduced Agent messages on the current page. |
| activeMessageId | string | Current task turn; null if no task exists or access is denied. |
| size | int | Number of visible messages returned; may be less than the number of history records scanned. |
| hasMore | boolean | Whether more history exists within the current time upper bound; an empty messages array does not indicate completion. |
| nextCursor | string | Next-page cursor; null when there is no next page. |
| snapshotAt | long | Message creation time upper bound for this pagination session, in milliseconds; null when there is no current task. |

No task or no instance permission returns:

```json
{
  "messages": [],
  "activeMessageId": null,
  "size": 0,
  "hasMore": false,
  "nextCursor": null,
  "snapshotAt": null
}
```

#### Message view

Paginated reads use the message structure below. Visible types are message / done; startup, container startup, and reconnection notices map to message. Ordinary internal process, buyer_message, and timeout events are excluded from offline lists.

Nonempty content has a `Capafy` prefix followed by a fullwidth colon (`U+FF1A`). done returns the actual content, files, structured questions, modelUsage, and usageAudit, adding originalQuestion / nextStepPlan when it matches the current turn.

##### messages[] fields

| Field | Type | Description |
| --- | --- | --- |
| type | string | Message type: message / done; timeout does not appear in offline responses |
| messageId | string | Message ID assigned by the platform. |
| seq | int | Sequence number within the turn; startup and reconnection notices are usually 0 |
| time | long | Message timestamp in milliseconds. |
| content | string | Nonempty content has a `Capafy` prefix followed by a fullwidth colon (`U+FF1A`); content may be null, and done content follows the actual upstream response |
| incremental | boolean | Whether this is an incremental fragment; nullable; render incrementally when true |
| files | array | File list; currently used mainly for attachments delivered with done. |
| askQuestions | array | Structured questions returned only with done; null for other messages |
| originalQuestion | string | Original question added for done when it matches the current turn |
| nextStepPlan | string | Next-step plan added for done when it matches the current turn |
| modelUsage | object | Usage object keyed by model code; null if not reported |
| usageAudit | object | Usage audit object; null if not reported |

##### files[]

| Field | Type | Description |
| --- | --- | --- |
| url | string | File download URL. |
| originalFileName | string | Original filename. |

##### askQuestions[]

The structured-question protocol specifies 1-4 questions, each with 2-4 options.

| Field | Type | Description |
| --- | --- | --- |
| id | string | Question identifier. |
| header | string | Short label used as the button group title and when filling in answers. |
| question | string | Complete question text. |
| options | array | Available options; the protocol specifies 2-4. |
| multiSelect | boolean | Whether multiple selections are allowed; defaults to false. |
| allowOther | boolean | Whether the user may supply a custom answer outside the options; defaults to false. |

##### askQuestions[].options[]

| Field | Type | Description |
| --- | --- | --- |
| label | string | Button display text. |
| description | string | Additional option description. |

##### modelUsage[modelCode]

| Field | Type | Description |
| --- | --- | --- |
| inputTokens | long | Input token count. |
| outputTokens | long | Output token count. |
| cacheReadInputTokens | long | Cache read token count. |
| cacheCreationInputTokens | long | Cache creation token count. |
| webSearchRequests | long | Web search request count. |
| costUSD | number | Cost of this model call in USD. |
| contextWindow | long | Model context window size. |
| maxOutputTokens | long | Model maximum output token count. |

##### usageAudit

| Field | Type | Description |
| --- | --- | --- |
| requestId | string | Upstream request ID. |
| provider | string | Usage provider. |
| modelRequested | string | Model name specified in the request. |
| modelActual | string | Model actually used for execution. |
| inputUncached | long | Uncached input token count. |
| cacheRead | long | Cache read token count. |
| cacheWrite | long | Cache write token count. |
| output | long | Output token count. |
| reasoningOutput | long | Reasoning output token count. |
| total | long | Total token count. |
| scope | string | Usage scope: request / turn / session. |
| usageStatus | string | Usage reporting status: reported / partial / unknown. |
| status | string | Task status: completed / failed / aborted. |
| rawSource | string | Raw usage source. |

#### Pagination rules

1. Read in ascending message creation time and server record order. The first request fixes snapshotAt; later pages retain createdAt <= snapshotAt.
2. size counts visible messages and may be smaller than the scanned record count. Filtered internal events can yield messages=[] with hasMore=true; continue using nextCursor.
3. Total raw UTF-8 content per page is limited to 1 MiB, which may end a page early. This budget is not a limit on the final JSON size.
4. hasMore=false only means this time range has been read; the task may still be running. To read new messages, restart without cursor and deduplicate locally.
5. Unread count is cleared when the final page actually returns done and there are no new messages beyond the time upper bound; otherwise it is retained.
6. snapshotAt is a time upper bound; it does not guarantee a transactionally consistent snapshot during concurrent backfills, updates, or deletions.

#### Failure cases

| HTTP status | Scenario |
| --- | --- |
| 400 | Noninteger or overflowing size, invalid cursor, or cursor mismatch with the current instance and turn |
| 409 | Instance lock contention returns instance_busy; changed paginated records return code=400 with a refresh-and-retry message |
| 413 | One content body exceeds 1 MiB; business code 8019; reducing size cannot resolve this |
| 500 | Unexpected internal error |

Authentication failures use the authentication layer's response. Clear the cursor and reread if the turn or history changes. Stop automatic retries on 413 and display the server error.

#### Reading remaining pages

Omit cursor on the first request and read messages. When hasMore=true, URL-encode nextCursor unchanged as a query parameter and continue. hasMore=false ends the current time range. Clear cursor and restart when the turn changes or the server reports a cursor mismatch.

Messages added after the first read are outside the original snapshotAt range; reread without cursor to obtain them. Retain messageId and ordering information to handle repeated messages. Platform notices may have multiple seq=0 entries; do not treat them all as the same message.

HTTP 409 instance_busy can be retried later; a 409 caused by changed history requires clearing the cursor and rereading. HTTP 413 / code=8019 means one content body is too large; display the error and stop automatic history reads.

## A13 `POST /agent/relay/instances/{instanceId}/interrupt`

Interrupt a running task (Agent)

Request that the instance's current running task stop. Success only means the interrupt command was accepted; subsequent results determine when the task actually ends.

#### Endpoint details

`POST /agent/relay/instances/{instanceId}/interrupt`

Requires Access Token authentication; only the current user's data is accessible.

Success and conflict return raw JSON without the standard envelope. Parameter errors, business errors, or authentication failures may return `{code,msg,data}`; check both HTTP status and Content-Type.

#### Request parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| instanceId | path string | Yes | ID of the instance to interrupt |

No body or query parameters.

#### Successful response

HTTP 200, raw JSON:

```json
{
  "status": "interrupt_requested",
  "activeMessageId": "msg_123",
  "message": "An interrupt signal has been sent to the Agent."
}
```

| Field | Type | Description |
| --- | --- | --- |
| status | string | Always interrupt_requested |
| activeMessageId | string | Message ID of the current running turn |
| message | string | Interrupt acceptance message |

200 only means the interrupt command was delivered. The task's final state still arrives through the current SSE stream or offline endpoint. Repeated interrupt requests for the same running task are allowed.

#### Failure response

HTTP 404 for no task, an ended task, another user's task, or no instance access:

```json
{
  "error": "no_active_task",
  "message": "There is no active task currently."
}
```

HTTP 409 when the instance flow lock is busy:

```json
{
  "error": "instance_busy",
  "message": "The instance is busy. Please try again shortly."
}
```

After interrupt acceptance, continue reading the existing SSE stream and wait for done. Retry later if the instance is busy. Handle authentication failures according to the authentication layer's response.

#### Finishing after interruption

After interrupt_requested, display a stopping state and keep reading the current SSE stream or offline results. Do not treat interrupt acceptance as done or immediately submit a second turn. For no_active_task, stop waiting and read existing offline results.

## Presigned file upload and download (Agent)

Request temporary upload or download URLs for chat attachments. Uploading requires a presign request followed by sending the file bytes; downloading uses GET after obtaining the URL.

#### Endpoint details

| Method | Path | Purpose |
| --- | --- | --- |
| POST | /agent/file/presign/upload | Request an upload signature, then PUT the file |
| POST | /agent/file/presign/download | Request a download signature, then GET the file |

Requires Access Token authentication; only the current user's data is accessible.


## A14 `POST /agent/file/presign/upload`

Upload presign request

Use Content-Type: application/json.

```json
{
  "fileName": "report.csv",
  "contentType": "text/csv",
  "bizType": "buyer_agent"
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| fileName | string | Yes | Original filename; nonempty, at most 255 characters |
| contentType | string | Yes | MIME type; nonempty, at most 100 characters |
| bizType | string | Required for buyer use | Set to buyer_agent; format ^[a-z0-9][a-z0-9_-]{0,31}$ |
| objectKey | string | No | Upload target, at most 1024 characters; a nonempty value signs that key directly and can overwrite an existing object |
| agentVersionId | string | Conditionally required | Optional for buyer_agent; other bizType values require an existing version and draft upload permission validation |

Without objectKey, buyer uploads generate:

```text
agent/buyer/{userId}/{yyyy}/{MM}/{dd}/{randomId}{extension}
```

Blocked extensions, case-insensitive: exe, msi, dmg, app, bat, cmd, com, scr, dll, so, dylib, iso, img.

#### Successful upload response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "uploadMethod": "PUT",
    "uploadUrl": "https://example.com/signed-upload-url",
    "headers": {
      "Content-Type": "text/csv"
    },
    "objectKey": "agent/buyer/user_123/2026/10/12/random.csv",
    "originalFileName": "report.csv",
    "publicUrl": null,
    "expiresInSeconds": 1800
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| uploadMethod | string | Upload HTTP method; always PUT |
| uploadUrl | string | Presigned upload URL; PUT the file directly to S3 using this URL |
| headers | object | Required upload headers, including Content-Type |
| objectKey | string | S3 object key for subsequent downloads or business references |
| originalFileName | string | Original filename |
| publicUrl | string | Populated only for a public/ prefix with a configured public domain; buyer_agent generates agent/buyer keys and returns null |
| expiresInSeconds | long | Actual validity in seconds: max(180, configured signature minutes * 60) |

Use uploadMethod=PUT, include the returned headers, and send the file bytes to uploadUrl. After success, save objectKey and originalFileName; put them in files[].url and files[].originalFileName when sending a message.

## A15 `POST /agent/file/presign/download`

Download presign request

```json
{
  "objectKey": "agent/buyer/user_123/2026/10/12/random.csv",
  "originName": "report.csv"
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| objectKey | string | Yes | At most 1024 characters; accepts a storage key or an HTTP/HTTPS URL resolvable to an object in the current storage |
| originName | string | No | At most 255 characters; sets the download filename through the attachment response header |

The generic download endpoint validates target format without an additional ownership check. Targets containing agent/run-online-package or agent/download-package return FORBIDDEN(403); use the purchased-order or published-package download endpoint for installation packages.

#### Successful download response

```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "downloadMethod": "GET",
    "downloadUrl": "https://example.com/signed-download-url",
    "objectKey": "agent/buyer/user_123/2026/10/12/random.csv",
    "expiresInSeconds": 1800
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| downloadMethod | string | Download HTTP method; always GET |
| downloadUrl | string | Presigned download URL; GET the file directly using this URL |
| objectKey | string | S3 object key |
| expiresInSeconds | long | Actual validity in seconds: max(180, configured signature minutes * 60) |

Download URLs may be signed by S3 or CloudFront. With originName, an S3 URL includes the download filename response header. GET downloadUrl directly.

#### Failure cases

Missing required parameters, invalid lengths or bizType format, and blocked extensions return 400. Restricted package directories return 403. Disabled storage, incomplete configuration, or signing failures return the corresponding storage business errors. Both business endpoints require a valid Access Token.

#### Uploading files and delivering messages

1. Request uploadUrl and save the returned headers, objectKey, and originalFileName.
2. PUT the file bytes with the returned headers, without a JSON wrapper.
3. After uploading, put objectKey in the send-message request's files[].url and originalFileName in files[].originalFileName.
4. To download or provide file access, request downloadUrl and GET it directly; request another URL after expiration.

Example: replace the variable with the actual signed URL before uploading or downloading. The upload must use the same MIME type specified in the presign request.

```bash
export BUYER_UPLOAD_URL='https://example.com/signed-upload-url'
curl --request PUT "${BUYER_UPLOAD_URL}" \
  -H 'Content-Type: text/csv' \
  --data-binary '@./report.csv'

export BUYER_DOWNLOAD_URL='https://example.com/signed-download-url'
curl --output report.csv "${BUYER_DOWNLOAD_URL}"
```

An object-storage signed URL is a file access credential. Requests to it use its signature and required upload headers; do not send the platform Agent Access Token. Save objectKey to request fresh URLs later; temporary downloadUrl values are not permanent file addresses.
