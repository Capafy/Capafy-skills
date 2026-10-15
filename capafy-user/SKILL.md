---
name: capafy-user
description: >
  Capafy buyer workflows: discover Agents, purchase or renew, top up Credits,
  install purchased packages, manage accounts/orders/subscriptions/instances,
  review services, and open web-only buyer operations. Handles conversations
  with purchased cloud Agents when no matching local Thin Skill exists.
  Use a matching Thin Skill for its conversations. Publishing and developer
  workflows belong to capafy-publisher; this Skill only handles that handoff.
---

# Capafy Buyer Skill

Read the matching workflow reference when needed; do not preload every reference
or the entire API manual. Run commands from the installed Skill root; script
paths are relative to that root.

## Routing

- For conversations with an installed matching Thin Skill (`capafy-agent-*`),
  use that Skill directly. Buyer management still belongs here.
- A Thin Skill forwards tasks to a cloud instance; a Download/buyout package
  contains the full local Skills. Updating a local entry does not prove an
  existing cloud instance was upgraded.
- Publishing, selling or distributing user-built Skills, Agents, workflows,
  scripts or tools requires the Publisher handoff indexed below. Do not execute
  publishing, workspace packaging or developer workflows here.

## Entry update gate

Before any buyer workflow, web redirect or Publisher handoff in this Skill, run:

```bash
python3 scripts/self_update_v2.py --ensure-supported
```

Run once when entering this Skill in a session, then handle the result:

- `up_to_date`: continue.
- `update_available` with `update_required: false`: offer the optional update.
  If accepted, run `python3 scripts/self_update_v2.py`. Do not repeat a declined
  optional offer during this session.
- `updated`, an accepted optional update, or nonempty `promoted_files`: reread
  this entry and relevant references, then rerun the gate before resuming.
- `restart_required` or `updated_with_pending`: stop; ask the user to fully exit
  and reopen the host, run `python3 scripts/self_update_v2.py --finalize`, then
  rerun the gate. A version number does not prove locked files became active.
- `error`, nonzero exit, or `continue_with_local_version: false`: stop and report
  the failure. Retry after resolution; do not bypass the gate.

Below `minSupportedVersion`, the gate upgrades automatically. When the minimum
is absent, newer releases are optional. `--check` does not replace this gate.
On mid-session `X-Skill-Version-Status: outdated` or `deprecated`, finish the
in-flight step and rerun the gate before the next operation. For update recovery
and preserved state, read [operations](references/operations.md).

## Shared boundaries

- Show every user-facing prompt, choice, URL and result in visible chat. Present
  choices as plain text, not host-specific dropdown/button tools. Wait for a
  required reply before dependent calls; unavailable choice tools imply no consent.
- Never read local secrets from environment variables, dotfiles, IDE/browser
  configuration or credential tools and relay them to a cloud instance through
  messages, context fields or uploads. General requests to make it work are not
  consent. Read [messaging](references/messaging.md) for missing credentials or
  a credential value the user explicitly typed into chat.
- Guest search and listed details need no login; public quotes use `--no-auth`.
  Before protected operations read [authentication](references/authentication.md).
  Every interactive email login requires explicit acceptance of both Terms and
  Privacy Policy before requesting an OTP; prior session consent is insufficient.
- Before spending read [payment](references/payment.md). Ask the payment method
  even with sufficient Credits unless explicitly given a session-wide preference.
  The API supports Credits only; Card is web-only and requires at least 5 credits
  per order. Do not send `paymentMethod`.
- Use returned IDs and documented fields; never invent billing/instance IDs,
  version-selection parameters or endpoints. HTTP 200 alone is not business
  success; checkout links indicate pending payment.
- Running-task status/progress/result queries read history; never send a new
  message or interrupt for a status query. Only explicit cancellation permits
  interruption. Follow [messaging](references/messaging.md).
- Before writing packages read [installation](references/installation.md).
  Confirm replacement before `--overwrite`. Install all sibling Skills and shared
  content in buyout packages together; cloud Thin templates require one root.
  Report dependency and state-sync failures instead of claiming readiness.
- Format results using [terminal display](references/terminal_display.md), not
  raw API JSON. Preserve files and structured output even with empty message text.

## Web links

Read `scripts/common/defaults.py` for `DEFAULT_PLATFORM_BASE_URL`, overridden by
`CAPAFY_PLATFORM_BASE_URL` when set. Remove a trailing slash and trailing `/api`
to obtain `{web_base}`. Prepend this base to every buyer web path, including
Terms and Privacy links. If defaults cannot be read, ask for the host; never
invent one from memory.

## Workflow index

| User intent | Read before acting |
| --- | --- |
| Login, account switch, protected access | [Authentication](references/authentication.md) |
| Search, Agent details, purchase, time/subscription/storage renewal | [Commerce](references/commerce.md); [payment](references/payment.md) before charging |
| Payment method, insufficient Credits, top-up | [Payment](references/payment.md) |
| Install/update purchased package, overwrite, Thin state repair | [Installation](references/installation.md) |
| Continue an instance, fallback chat, status, cancellation, files, credentials | [Messaging](references/messaging.md) |
| Account/profile, balance, orders, subscriptions, instance names, reviews | [Account and web](references/account-and-web.md) |
| Refund, spending limits, Tokens, billing, report, payment method changes | [Account and web](references/account-and-web.md) |
| Publish or sell user-built work | [Publisher handoff](references/account-and-web.md) |
| Update recovery, API/network/shell failure | [Operations](references/operations.md), plus the relevant workflow |

For request bodies and response fields, select the relevant module from the
[API overview](api-docs/00_overview.md). Workflow references define when to call;
API modules define signatures. Load only what the current operation needs.
