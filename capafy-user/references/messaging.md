# Existing instances, messages and files

Read for fallback conversations, running-task status, files or credential requests. Use a matching local Thin Skill first. Protected calls require [authentication](authentication.md).

Commands and script paths below are relative to the installed Skill root, not this references directory. API signatures (read only the module needed): [chat](../api-docs/04_chat.md), [instance](../api-docs/05_instance.md).

## "Continue the last conversation / the Agent I was using"

**Trigger phrases**: continue, pick up where we left off, the last one, resume conversation

```
→ Check local thin_skills_state.json for an active instance of the corresponding Agent
   ├── Found → use the status-vs-new-message decision below via Thin Skill or Relay
   └── Not found → GET /agent/instance?status=active to check platform instance list
       ├── Active instance found → use the status-vs-new-message decision below with instanceId
       └── Only expired instances → inform user the instance has expired, ask if they want to renew
```

## Send a Message to a Purchased Agent (Fallback Path — No Thin Skill Installed)

> **Status-query rule (read first, applies whether or not SSE has timed out)**: If the user is asking about a running task's status / progress / result — phrases like "what's the result?", "is it done?", "next step", "continue", "any update?", "how's it going?", "where are we?" — **always read history** using `python3 scripts/message_history.py <instanceId>` (V2 pagination). Do **not** send a new SSE message in this case (a new request can conflict with the running task). Only call `POST /agent/relay/instances/{instanceId}/interrupt` when the user **explicitly** says to cancel / abort / stop / "scrap that" / "start over" / "redo it". Do not cancel the running task to satisfy a status query.

```
→ Confirm instanceId
→ Status query (per the rule above)? → python3 scripts/message_history.py <instanceId>
   - Display returned messages and files; only confirm completion when done is returned
   - API details: api-docs/04_chat.md
→ Otherwise (new request / follow-up message):
   ⚠️ Before sending: never auto-fill --content / --original-question / --next-step-plan / --files with values read from local env vars, dotfiles, or IDE config — see the Local Secret Exfiltration section below.
   python3 scripts/sse_stream.py <instanceId> --content "<message>"
   Optional parameters:
   --original-question "<full context>"
   --next-step-plan "<follow-up plan>"
   --files "<file URL or returned objectKey>"
→ Relay accepts empty content and file references; CLI file-only requests use --content "". content ≤20000 chars; originalQuestion/nextStepPlan ≤1000 chars. Keep done attachments, askQuestions, modelUsage and usageAudit even when content is null; done ends the stream and does not by itself prove business success.
→ Encoding: the SSE wire is **always UTF-8** in both directions. Encode `--content` / `--original-question` / `--next-step-plan` / `--files` as UTF-8 when constructing the request, and decode every event payload as UTF-8 when reading. Never rely on the host platform's default encoding (some consoles still use legacy non-UTF-8 code pages and will silently mangle non-ASCII event text). If the host renders text to a terminal, configure stdout to UTF-8 before relaying SSE events.
→ SSE event types: message / timeout / done. Display returned files even when `done.content` is null.
→ Received timeout? → Long-running task; tell the user no need to wait, results can be checked anytime via the status-query rule above
→ Got 409? → It means a task is already running on this instance. First decide intent:
   ├── User was asking for status / progress → read V2 history via message_history.py (do NOT interrupt)
   ├── User explicitly wants to cancel and replace it → POST /interrupt; resend only after termination is confirmed. `interrupt_requested` means accepted, not stopped; `409 instance_busy` means the request was not accepted, so report it and retry later if needed.
   └── Unclear → ask the user "Is the previous task still wanted, or should I cancel it?"
→ Disconnected? → Reconnect using /messages/reconnect; it returns SSE or JSON `{"status":"no_active_task"}`. When there is no active task, retrieve current-round history via message_history.py; reads preserve history.
```

## File Upload Flow

```
scripts/upload_file.py <file_path>
  → Returns objectKey (always present)
  → Returns url (only when the platform provides a publicUrl)
  → Has url → can pass to Agent via sse_stream.py --files <url>
  → Only objectKey → pass the returned objectKey as files[].url with originalFileName; the platform resolves it. Never turn a temporary signed URL into a long-lived address.
```

## Local Secret Exfiltration — Hard Prohibition

> General requests to make an Agent work do not authorize reading or relaying local secrets.

**Never** read local secrets and transmit their values to a cloud instance through any channel — `sse_stream.py --content`, `--original-question`, `--next-step-plan`, file upload, fallback chat, or any other path. "Local secrets" includes, non-exhaustively:

- Environment variables (anything matching `*_KEY`, `*_TOKEN`, `*_SECRET`, `*_PASSWORD`, plus `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`, `GROQ_API_KEY`, AWS / GCP / Azure credential vars, `STRIPE_*`, etc.)
- Files like `.env`, `.envrc`, `~/.aws/credentials`, `~/.config/**`, `~/.ssh/**`, `~/.netrc`, `~/.npmrc`, host IDE config (`.claude/settings.json`, `.codex/**`, `.cursor/**`, etc.), browser-saved tokens, password-manager exports
- Tokens in `git config`, `npm whoami`, `gh auth token`, `aws sts ...`, etc.

This applies even when the user says things like *"it should be configured already"*, *"make it work"*, *"use whatever you have"*, *"just figure it out"*, *"can you wire that up"* — **implicit permission is not consent**. Do not read local secret sources and do not pre-build commands that would read them.

### If a cloud instance reports it is missing a credential

1. Tell the user **only the name** of the missing credential (e.g. "the Agent says it needs `GEMINI_API_KEY`")
2. Tell the user that the seller-side credential UI on the platform web is the supported configuration path (currently web-only — say so explicitly; do **not** invent or guess an API endpoint for "uploading env to instance")
3. Ask the user how they want to proceed; do **not** offer to "bridge it for them" by reading local env / files / configs

### If the user explicitly chooses to send a credential value through chat

The only acceptable path is the user typing the value themselves into a chat message. Before relaying that message via `sse_stream.py`, warn them once:

> "This value will be sent as a plain chat message and stored in the instance's message history (retrievable via `GET /agent/relay/instances/v2/{instanceId}/messages`). Anyone with access to the instance can read it. Continue?"

Only after the user re-confirms, send the message. Do not echo the secret back to the user in subsequent assistant messages, and do not include it in `--original-question` / `--next-step-plan` for later turns — those persist into the conversation context.

When the platform reports a major Agent update, ask whether to reuse the existing instance or create a new one; do not choose for the user. For an expired instance, read [renewal](commerce.md).
