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

## ZIP installation completion

After successfully installing this skill (`capafy-user`) from a ZIP, show this standalone line before continuing with login or buyer workflows:

```text
✅ Capafy user skill installed successfully! Version <version>
```

Replace `<version>` with `version` from the installed skill's `api-docs/index.json`. For version `0.4.9`, the exact message is:

```text
✅ Capafy user skill installed successfully! Version 0.4.9
```

Show the message only after installation succeeds. If installation fails or the installed version cannot be read, report the failure instead of claiming success or guessing a version. This message applies to installing `capafy-user` itself, not purchased Agent packages or Thin Skills.

Immediately below the success line, display the installed skill's `assets/icon.png` on its own line, before any login or buyer workflow instructions. In hosts that render local Markdown images, use `![Capafy](<absolute-path-to-installed-skill/assets/icon.png>)` outside a code block, with blank lines around it. Replace the placeholder with the actual absolute path inside the installed `capafy-user` directory; do not use the source repository or the original attachment path. Keep angle brackets around the path so spaces are supported.

If the host cannot render local images, use its supported image-display mechanism when available. If the image is missing or cannot be displayed, retain the installation success text and briefly state that the icon could not be displayed; this does not turn a successful installation into a failure. Do not claim that an image was displayed when rendering is unverified.

## Upgrade completion

After successfully upgrading this skill (`capafy-user`), either through self-update or by replacing an older installation with a ZIP, show this standalone line before resuming buyer workflows:

```text
✅ Capafy user skill upgraded successfully! Version <version>
```

Read `<version>` from the upgraded skill's `api-docs/index.json`. For a ZIP upgrade, use this message instead of the installation message. This message does not apply to purchased Agent packages or Thin Skills.

For self-update, show success only when the updater reports `updated` with no pending files, or when pending-file finalization promotes files and leaves none pending. For `updated_with_pending`, `restart_required`, or remaining pending files, follow the restart and finalization steps in the entry update gate below before showing success. A version number alone does not prove all files were replaced. After showing success, still reread this entry and relevant references and rerun the gate before resuming.

An available update or an already-current installation is not a completed upgrade. Report update failures or an unreadable installed version instead of showing success.

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
