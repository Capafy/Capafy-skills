# Publish Workflow Guide

This document defines command order, path and selection inputs, safe re-entry, and deep-scan handoff. Follow each command's JSON payload; `developer_next_steps` takes precedence when present.

## Login

Before email OTP login, derive the web base from the platform base URL, show the Terms of Service and Privacy Policy links, and obtain explicit consent to both. Then run:

```bash
python3 packager.py login-init --email <email>
python3 packager.py login-verify --challenge-id <id> --code <otp>
```

For a supplied token or account switch:

```bash
python3 packager.py login-token --access-token '<token>'
```

`login-token` validates through `GET /agent/account` before changing local fallback login state. Never echo the token or raw login response. Authentication priority is `CAPAFY_ACCESS_TOKEN`, then this skill's `config.json`; an existing environment token therefore continues to take precedence.

If a publishing request includes a token in natural-language form (`token:`, `token：`, `access_token:`, `access_token：`, `access token:`, or `access token：`), including a token next to a Publisher installation request, treat that value as the supplied developer-Skill token. After installation completes, run `login-token` with the captured value before `publish-init`. A successful validation replaces the developer Skill (`capafy-publisher`) root `config.json`; a failed validation leaves the existing file unchanged. Do not read or modify `capafy-user/config.json`, and do not echo or log the token.

`publish-init` verifies platform login before candidate discovery or submission. An absent or expired token returns `platform_login_required` or `platform_login_invalid` and stops the publish step.

## Publish flow

### Main chain

```text
publish-init without selections
→ host and creator confirm real candidates
publish-init with --selections-file
→ web confirmation of selected skills/files
publish-submit(action=prepare)
→ optional deep scan, Download dispositions, or Run Online environment-name selection
→ no upload and no platform credential write
→ if source files change, rerun `publish-submit(action=prepare)` to rebuild
publish-submit(action=continue_upload)
→ validate, package, upload, and call `/uploadPackageCredentials` once
→ final web review/configuration confirmation and submit for review
publish-remote-status
```

Expected pauses such as candidate selection and `needs_deep_scan` return exit code `0` with `ok: true` and `requires_action: true`. True failures return exit code `1` with `ok: false`. Always branch on the JSON envelope.

### Non-negotiable execution rules

1. MUST decide whether this is a new Agent or a version update before submitting selections.
2. MUST run Phase A without selections first. Only Phase A candidates may appear in the selections file.
3. For a version update, MUST read `workflowInfo.selection_groups`, confirm the current skill with the creator, and retain the original `agent_id`.
4. MUST reuse the same `--env`, `--runtime-dir`, and `--skill-dir` values for discovery and submission.
5. Only `publish-init`, `publish-submit(action=continue_upload)`, refresh, and certification flows may return `review_url`. Paste it verbatim and STOP until the creator completes the page.
6. Treat `requires_action: true` as a pause, not an error. Use `publish-remote-status` for platform state.
7. NEVER show tokens, secrets, `generic.value`, raw responses, signed URLs, or presign headers in chat or ordinary CLI output.

### Primary commands

```bash
python3 packager.py publish-init --env <env_id> --runtime-dir <absolute_path>
python3 packager.py publish-init --env <env_id> --runtime-dir <absolute_path> --selections-file .temp/confirmed-selections.json
python3 packager.py publish-submit --agent-id <agent_id> --action prepare
python3 packager.py publish-submit --agent-id <agent_id> --action continue_upload
python3 packager.py publish-remote-status --agent-id <agent_id>
```

Optional `publish-submit --action prepare` branches:

```bash
python3 packager.py publish-submit --agent-id <agent_id> --action prepare --deep-scan
python3 packager.py publish-submit --agent-id <agent_id> --action prepare --deep-scan-findings-file <findings.json>
python3 packager.py publish-submit --agent-id <agent_id> --action prepare --dispositions-file <dispositions.json>
python3 packager.py publish-submit --agent-id <agent_id> --action prepare --environment-selection-file <selection.json>
```

Auxiliary commands:

```bash
python3 packager.py publish-status
python3 packager.py publish-list
python3 packager.py publish-refresh-url --agent-id <agent_id> [--step init|publish]
```

### Runtime and path rules

| `--env` | `--runtime-dir` |
|---|---|
| `claude-sdk` | Project root of the current Claude Code session |
| `codex` | Project root of the current Codex session |
| `hermes` | Project/workspace root of the current Hermes session |
| `openclaw` | Current OpenClaw workspace, such as `~/.openclaw/workspace`; not the user home, `~/.openclaw`, or a skill directory |

Claude Code is the local workspace being scanned. Its runtime identifier is `claude-sdk` in `--env`, `env_id`, `target_id`, and `agentRuntime`.

- `--env` and `--runtime-dir` are required on every `publish-init` call. The target runtime need not match the host running the publisher.
- A `metadata.openclaw` skill requires `--env openclaw`.
- `--runtime-dir` describes the active project/workspace. Do not derive it from the source skill path.
- `--skill-dir` is optional and must point to one explicit skill root containing `SKILL.md`, never its parent `skills` directory.
- Reuse the same `--env`, `--runtime-dir`, and explicit `--skill-dir` between candidate discovery and submission.
- Windows and WSL paths must be absolute and accessible to the system running the publisher; paths are not converted automatically.
- If the current OpenClaw workspace is unknown, ask the creator. Do not substitute the skill directory.

### `publish-init` inputs

| Parameter | Use |
|---|---|
| `--brief` | Compact Phase A output in large workspaces; may be combined with `--title` and `--description` for sorting |
| `--skill-dir` | Restrict discovery to one explicitly chosen local skill root |
| `--selections-file` | Recommended way to submit a UTF-8 confirmed selections JSON file |
| `--agent-id` | Existing Agent ID; if selections also contain `agent_id`, both values must match |
| `--reset-local-state` | Abandon an active local draft only after explicit creator confirmation |

Phase A is mandatory. Run `publish-init` without selections and use only returned candidates. Do not guess a path, infer it from history, or treat an Agent Card name mismatch as an empty workspace. If `skills: []`, stop and confirm the actual project root or skill source directory.

The selection branch is exact:

1. `publish-init` without selections → receive candidates (`requires_action: true`).
2. Creator chooses at least one real candidate → write `.temp/confirmed-selections.json`.
3. `publish-init` with `--selections-file` → receive the first `review_url`.
4. Paste the URL and stop for web confirmation.

For an existing Agent:

1. Obtain the Agent ID from the creator or `publish-list`.
2. Read the latest version and its `workflowInfo.selection_groups`.
3. Tell the creator which skill is currently selected and ask whether to keep it or switch.
4. Treat historical skill paths as platform logical paths, not current local paths.
5. Run Phase A against the current filesystem before submitting the update.

Confirmed selections use this shape:

```json
{
  "agent_id": "agt_xxx",
  "title": "Skill Security Review",
  "description": "Review third-party skills for security risks.",
  "skills": [
    {
      "path": ".agents/skills/skill-vetter",
      "name": "skill-vetter",
      "purpose": "Review skill source code for credential leakage and unsafe behavior."
    }
  ]
}
```

Omit `agent_id` only for a new Agent. Every `skills[].path` and `name` must come from Phase A; `skills` must be non-empty. Do not wrap inputs in `selection_groups` or add the retired `workflow_intent` structure.

Use these two unambiguous variants:

- New Agent: `{ "title": "...", "description": "...", "skills": [...] }` — no `agent_id`.
- Version update: `{ "agent_id": "agt_existing", "title": "...", "description": "...", "skills": [...] }` — the ID must be the existing Agent being updated.

### Web confirmation points

| Source | Creator action |
|---|---|
| `publish-init` | Confirm the files and skills to upload |
| `publish-submit(action=prepare)` | Complete local security preparation only; this step never writes package or credential state to the platform |
| `publish-submit(action=continue_upload)` | Validate, package, upload, call the merged package-and-credentials API, and pause for final review/configuration confirmation |

When `review_url` is returned, paste it verbatim, explain its purpose, and pause. After the creator finishes, read the latest platform version before reporting state or continuing. Refresh expired links with `publish-refresh-url`; do not rerun a publish step merely to obtain a new URL.

## Safe re-entry

| Situation | Correct action |
|---|---|
| Skill/file confirmation page completed; security preparation has not run | Ask whether to perform deep scan in either mode. Use `publish-submit --action prepare --deep-scan` only after explicit agreement |
| `skills_empty_after_platform_confirmation` | Have the creator select at least one skill on the first page, or rerun init with the correct project/workspace and skill source directories |
| `needs_deep_scan` | Treat as an expected pause; inspect the returned staging boundary and submit findings, or rerun `publish-submit --action prepare` without `--deep-scan` when nothing is found |
| Download returns `needs_creator_disposition` | Write the creator's choices to a dispositions JSON file and rerun with `--dispositions-file`; never pass inline JSON |
| Run Online creator explicitly wants local environment values uploaded | Edit only the generated name-selection file and rerun with `--environment-selection-file`; otherwise use the existing web path |
| `existing_local_publish_state` | Resume the local draft. Do not reset it automatically |
| `publish-submit` fails | Inspect `publish-status`, preserve the same Agent ID, and retry the failed action; do not create a new Agent |
| `persist_package_uploaded_state_failed` | The merged remote package submission succeeded. Provide the final review URL, then check `publish-remote-status`; do not rerun upload if remote state confirms success |
| Creator returns from a web page saying done | Read the latest platform version before claiming confirmation, submission, review, or approval |
| Platform mode differs from the local manifest | Web mode changed; rerun `publish-submit --action prepare` so staging and package are rebuilt for the new mode |
| Creator asks for review or listing status | Use `publish-remote-status`, not local `publish-status` |
| `review_url` expired | Use `publish-refresh-url --step <init|publish>` |
| `status: 0`, `auditStatus: 0` | Report “draft / review not started”; never report submitted, under review, or approved |
| Runtime or skill set changes | Reconfirm the current local paths and rerun Phase A; retain the original Agent ID when updating the same Agent |
| Rejected version is being revised | Rerun init → `publish-submit(prepare)` → `publish-submit(continue_upload)` with the original Agent ID so a new version is created under the same Agent |
| Creator explicitly abandons the Agent and starts over | Confirm once more, then use `--reset-local-state` and omit the old Agent ID |

`publish-status` is local-only. `--reset-local-state` changes local files only and does not cancel platform state. Preserve staging and bundle data while remote package submission state is uncertain.

## Sensitive deep scan

Both Run Online and Download support the same deep-scan pause. `publish-submit --action prepare --deep-scan` returns `staging_path`, the complete `scan_files` list, `scan_files_summary`, and safe `credential_hints`; it does not upload or call the final package-submit API.

Deep-scan decision order:

1. After the skill/file web confirmation, ask the creator whether to spend the extra scan time and tokens.
2. If refused, run ordinary `publish-submit --action prepare`.
3. If accepted, run `publish-submit --action prepare --deep-scan` and inspect every listed staged file.
4. If nothing is missed, rerun `publish-submit --action prepare` without `--deep-scan`.
5. If a miss is found, submit the findings file; do not hand-edit reviewed-scan output.
6. If deep scan was selected, complete this sequence before adding a Run Online environment-selection file. Never combine `--deep-scan` with `--environment-selection-file`.

The host reads every listed staged file, but findings may come only from entries with `reviewable: true`. Look only for real sensitive literals missed by the rule scan, including unusual field names, nested or concatenated tokens, mixed-language configuration, and sensitive values embedded in prose or comments.

Do not:

- inspect host environment-variable values;
- report examples, placeholders, test stubs, or runtime-irrelevant text;
- recreate findings already covered by the rule scan;
- discover or construct `url_proxy` entries;
- edit `.temp/reviewed-scan.json` or supply internal review/digest fields.

### Findings file contract

The findings file must be a JSON object with only a top-level `generic` array:

```json
{
  "generic": [
    {
      "value": "missed-sensitive-value",
      "source": "relative/path/in/staging.yaml"
    }
  ]
}
```

Each item requires:

- `value`: the exact sensitive literal found in the staged file;
- `source`: a concrete staging-relative file that will enter the final package.

`field` and `value_type` may be included when useful. Do not use directories, escaped paths, external scan-only sources, internal manifests, missing files, or existing archive artifacts as sources. The program validates findings, filters anything outside the package boundary, fills internal metadata, and replaces retained values only in staging.

Submit findings with:

```bash
python3 packager.py publish-submit --agent-id <agent_id> --action prepare --deep-scan-findings-file <findings.json>
```

If no missed value exists, rerun `publish-submit --action prepare` without `--deep-scan`. `--deep-scan` cannot be combined with `--deep-scan-findings-file` or `--environment-selection-file`; finish the scan pause first.

### Staging and environment rules

- High-risk credential files, login state, and system directories never enter staging.
- Allowed files remain in staging; sensitive literals are replaced with `PLATFORM_MANAGED_*` placeholders without modifying the creator's source files.
- Keep a runtime-required `.env` or a `.env` inside a selected skill when it belongs in the package, but strip sensitive values by semantics. Exclude authentication state, private keys, and runtime-irrelevant development configuration.
- Codex, Claude Code, Hermes, and OpenClaw do not package global agent configuration. Local runtime configuration is read only for safe provider metadata needed by the publish flow.
- The `claude-sdk` runtime reserves `ANTHROPIC_BASE_URL` and `ANTHROPIC_API_KEY` for `url_proxy`; Codex reserves `OPENAI_BASE_URL` and `OPENAI_API_KEY` for `url_proxy`. These names must never be offered or uploaded as ordinary Run Online environment variables.
- Run Online environment discovery records names only. Show `environment_variable_hint` names and conflicts to the creator; selected values are included only in the final merged submission, while unselected credential values are completed on the final review page.

### Secret display boundary

- Never print secrets or `generic.value` in chat, normal CLI output, logs, or local previews.
- If a creator-facing full value must be shown, use only the platform's controlled web confirmation page.
- Provider API-key values are not persisted in reviewed-scan data; the creator confirms or enters them on the final review page.
- Do not display internal placeholders or template variables as creator-facing values.

The web confirmation page is the only valid confirmation boundary. Chat confirmation, local previews, scripted form submission, and reverse-engineered endpoints are not substitutes.
