---
name: capafy-publisher
description: "Creator-side Capafy workflow for publishing, updating, packaging, uploading, re-shipping, or managing an Agent/Skill. Also handles creator earnings, payouts, statistics, refunds, certification/KYC, review links, Agent continuation, and publisher-account switching. Generic buyer login, balance, orders, purchases, subscriptions, and instances belong to capafy-user."
---

# capafy-publisher

Use this file for entry points and rules that the host must enforce. Read `publish-workflow.md` for the state machine and sensitive-scan details. Read `api-docs/00_overview.md` for HTTP fields and platform enumerations.

## Prerequisites

- Run scripts in this directory with `python3`.
- Python 3.8 or newer is required.
- The host must allow Python execution in this skill directory.
- Run `python3 self_update_v2.py --check` before publisher commands. If the
  installed version is below `minSupportedVersion`, V2 installs the current
  release before the command is retried.

## Read order

Read only:

- `SKILL.md`
- `publish-workflow.md`
- `api-docs/index.json`
- `api-docs/00_overview.md`

Do not read Markdown under `.temp/`, `.pytest_cache/`, `dist/`, or `docs/`.

## Public commands

```text
login-init
login-verify
login-token
publish-init
publish-submit
publish-status
publish-remote-status
publish-refresh-url
publish-list
```

Every command returns one of three JSON result shapes:

- Success: `ok: true`, `requires_action: false`.
- Expected pause: `ok: true`, `requires_action: true`, with `action_type`.
- Failure: `ok: false`, `status: error`, `requires_action: false`.

Use the JSON fields, not only the exit code, to decide what happens next.

## Login

- Enter publisher login only for creator publishing or creator-account management. Generic Capafy login belongs to `capafy-user`.
- Email login requires explicit acceptance of both the Terms of Service and Privacy Policy before `login-init`.
- Email login flow: `login-init` then `login-verify`.
- Use `login-init`'s `expires_in_sec` from the successful send time; never assume a fixed OTP lifetime. After a failed or expired verification, run `login-init` for a new challenge and email code before retrying `login-verify`.
- Direct token or account switching: `login-token --access-token <token>`.
- If the publish request itself contains an explicitly supplied token (for example `token: ...`, `token：...`, `access_token: ...`, or `access token: ...`), including a token next to a Publisher installation request, treat it as a direct developer-Skill token handoff even when it appears alongside an install request. Run `login-token` before `publish-init`; when Publisher was just installed, run it immediately after installation. A successful validation replaces the developer Skill (`capafy-publisher`) root `config.json` token. Never fall back silently to the old local token, use `capafy-user/config.json`, or echo/log the supplied token.
- Never echo a token, OTP, authorization header, or raw login response.
- `login-token` validates the token through `GET /agent/account` before saving it.
- Token priority is `CAPAFY_ACCESS_TOKEN`, then the publisher skill's local `config.json`.
- Platform base URL priority is explicit `--base-url`, then `CAPAFY_PLATFORM_BASE_URL`, then the code default.

## Main publish chain

```text
publish-init without selections
→ creator/LLM confirms a real candidate
→ publish-init with selections
→ web confirmation of selected skills/files
→ publish-submit(action=prepare)
→ handle deep scan, dispositions, or environment-name selection locally
→ publish-submit(action=continue_upload)
→ upload the package and submit packageUrl + requiredCredentials once
→ final web review and configuration confirmation
→ publish-remote-status
```

Web pages serve two purposes:

1. Confirm files and selected skills after `publish-init`.
2. Review the uploaded package, confirm Run Online credentials when required, and submit the version for review after `continue_upload`.

When a command returns `review_url`, paste it verbatim, explain its purpose in one sentence, and pause. Refresh expired links with `publish-refresh-url`; do not rerun a publish step only to get a new link.

## Non-negotiable host rules

- MUST decide **new Agent** versus **version update** before submitting `publish-init` selections.
- MUST run Phase A (`publish-init` without selections) before creating the selections file.
- MUST use only candidate paths returned by Phase A; never guess or recover a local path from platform history.
- For an update, MUST keep the original `agent_id` and reconcile `workflowInfo.selection_groups` first.
- When `review_url` is returned, MUST paste it verbatim and STOP until the creator completes that web page.
- `requires_action: true` is an expected pause, not a command failure.
- MUST use `publish-remote-status` for platform review state; `publish-status` is local-only.
- NEVER display tokens, secrets, `generic.value`, or raw platform responses in chat or normal CLI output.

## Creator-facing language

Do not expose internal field names as if the creator already knows them. Translate them:

| Internal term | Creator-facing wording |
|---|---|
| `--runtime-dir` | project root or current workspace |
| `--skill-dir` | skill source directory |
| `--env` | target runtime |
| `agent_id` | Agent ID |
| `agent_type: run_online` | Run Online mode |
| `agent_type: download` | Download mode |
| `selection_groups` | skills/files selected for this release |
| `.temp` or manifest | local draft |
| `--reset-local-state` | discard the local draft and start over |
| `--deep-scan` | use the LLM to inspect every staged file for missed sensitive values |
| `--dispositions-file` | choices for replacing or excluding sensitive Download values |
| `--environment-selection-file` | optional local environment-variable name selection |

## publish-init rules

- `--env` and `--runtime-dir` are always required.
- `--runtime-dir` is the current project/workspace root, not the publisher directory and not the skill directory.
- Use `--skill-dir` only for one explicit skill directory containing `SKILL.md`.
- Support one selected skill or multiple selected skills in the same release. A creator-merged skill with one entry `SKILL.md` is one selection; preserve its internal component directories and files.
- Preserve `./` and `../` references; they are not creator-local absolute paths. Packaging validates explicit relative Markdown link destinations against the final ZIP layout. Commands, code examples, and configuration paths may use a runtime working directory; do not resolve them relative to the document or rewrite the creator's source to satisfy this check.
- Run discovery before submitting selections. Never invent a candidate path.
- Submit selections with `--selections-file`.
- `skills[]` must contain at least one real candidate.
- Use one Agent ID source. If both the CLI and selections contain it, they must match.
- Reuse the same runtime and explicit skill paths between discovery and submission.
- Before updating an existing Agent, read the latest platform selection and ask whether to keep the current skill or switch.
- Historical platform paths are logical paths, not proof of the current local filesystem location.
- Use `--reset-local-state` only when the creator explicitly abandons the active local draft.

Runtime path notes and copy-pastable examples live in `publish-workflow.md`.

## Deep scan

Run Online and Download both support deep scan.

Deep scan means the host LLM reads every file under the returned `staging_path` and looks for sensitive literals that the regular rule scan missed. `scan_files` lists the complete staging file set and marks which files can produce package findings.

Rules:

- Ask the creator before spending the extra time and tokens.
- Do not inspect host environment-variable values.
- Do not recreate items already found by the rule scan.
- Do not create `url_proxy` entries. Only report missed generic sensitive values.
- Findings must use a concrete staged file as `source`.
- Pass findings through `--deep-scan-findings-file`; never hand-edit reviewed-scan output.
- If nothing is found, rerun `publish-submit --action prepare` without `--deep-scan`.
- `needs_deep_scan` is an expected pause and exits successfully in both modes.

## Mode-specific publish-submit inputs

- `--dispositions-file` is Download-only. Run Online rejects it.
- `--environment-selection-file` is Run Online-only. Download rejects it.
- `--deep-scan` and `--deep-scan-findings-file` are separate steps and cannot be used together.
- `--deep-scan` and `--environment-selection-file` cannot be used together. Complete deep scan first, then submit findings and any environment-name selection on the next `publish-submit --action prepare` run.
- Normal Run Online preparation records environment-variable names only. It reads values only when the creator explicitly selects names for inclusion in the final merged submission.
- When the creator explicitly asks to upload local values for candidate environment variables, treat that request as authorization to edit only the generated selection file's `selected` array and rerun `publish-submit --action prepare` with `--environment-selection-file`. If a selected value is missing locally, stop before upload; otherwise the final review page remains the human confirmation boundary.
- Read only the exact selected environment-variable names. Never enumerate the host environment or display, log, or persist the selected values.

## Status and recovery

- `publish-status` shows only the local draft summary.
- `publish-remote-status --agent-id <id>` shows the latest platform version and confirmed selection.
- `publish-list` returns the creator's minimal Agent list for choosing an Agent ID.
- Resume `publish-submit` failures from the matching local draft. Do not create a new Agent to recover from a later-step failure.
- A rejected version must be rebuilt through the same Agent ID.
- `--reset-local-state` changes local files only; it does not cancel anything on the platform.

## Safety boundaries

- Never upload login state, private keys, OAuth caches, credentials stores, or unselected host environment-variable values. Selected host environment-variable values may be uploaded only through the explicit Run Online `--environment-selection-file` flow above.
- Never expose raw platform responses, signed upload URLs, presign headers, tokens, OTPs, or internal absolute paths in normal CLI output.
- Do not edit the creator's source files during packaging. Sensitive replacement happens only in staging.
- Do not bypass creator confirmation pages.

See `publish-workflow.md` for exact re-entry branches, staging rules, reviewed-scan structure, and runtime-specific examples.
