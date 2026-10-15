# Update recovery, tools and errors

Read on updater, API, network or shell failures. The entry update gate in [SKILL.md](../SKILL.md#entry-update-gate) is mandatory before every workflow session.

Commands and script paths below are relative to the installed Skill root, not this references directory. Use [API overview](../api-docs/00_overview.md) to select only the signature module needed for a call.

## Available Tools

| Tool | Purpose |
|------|---------|
| `scripts/capafy_http.py` | General-purpose HTTP client, auto-injects token |
| `scripts/sse_stream.py` | Relay SSE conversation |
| `scripts/message_history.py` | Stream current-round V2 history pages; preserve pagination metadata and fail on incomplete reads |
| `scripts/install_package.py` | Download and Thin Skill package download, installation, dependency report and Thin state sync |
| `scripts/auth.py` | Token storage and loading |
| `scripts/format.py` | Search result terminal formatting |
| `scripts/upload_file.py` | File upload (presigned URL + S3) |
| `scripts/thin_skill_state.py` | Thin Skill local state management |
| `scripts/self_update_v2.py` | Skill version gate and self-update |

> **Windows / PowerShell JSON-body invocation**: when calling `scripts/capafy_http.py` with a JSON body on Windows under PowerShell, **prefer piping the JSON into `--json-stdin`** instead of inlining `--json '{...}'`. PowerShell's native-argv layer strips the inner double quotes, so an inlined `--json '{"k":"v"}'` arrives at the script as `{k:v}` and fails locally with `JSONDecodeError` — the request never reaches the platform. Pattern:
>
> ```powershell
> '{"loginMethod":"email","email":"a@b.com"}' | python scripts/capafy_http.py POST /auth/login --json-stdin
> ```
>
> If the first JSON-body call fails with a local parse error, switch to `--json-stdin` immediately — do **not** keep guessing escape variants. The same rule applies on Windows `cmd.exe`. On bash / zsh / Git Bash with single-quoted JSON, `--json` works fine; stdin is optional there.

## Version Self-Update (Mid-Session Fallback)

The pre-run gate in ../SKILL.md is the primary gate; this section covers a version signal received mid-session.

- On `X-Skill-Version-Status: outdated` or `deprecated`, finish the in-flight step, then run `python3 scripts/self_update_v2.py --ensure-supported` before the next operation.
- Handle the result using the entry gate in ../SKILL.md: required upgrades run automatically; errors or locked files block continuation. After an update, re-read SKILL.md and the relevant references and rerun the gate before resuming.
- If the current version is supported and the user declines the optional update, do not repeat the optional offer in the same session. A later minimum-version change still requires the gate.

## Error Handling Guidelines

| Error Scenario | Handling |
|---------------|---------|
| 401 / 1007 | Token expired; guide user to re-authenticate |
| 409 on sending a message | Instance already has a task running. Status query → message_history.py; explicit cancel → POST /interrupt and wait for termination before resending; unclear → ask the user (see messaging.md) |
| 409 instance_busy on interrupt | Instance process lock could not be acquired. Interruption was not accepted; report it and retry later if needed |
| Insufficient Credits | Follow [payment](payment.md): below 5 credits offer top-up only; at or above 5 credits offer top-up or Card. Card targets: new order → `/agent/{agentId}`, renewal → `/my-agents`. |
| No search results | Suggest user rephrase their description and search again |
| Search API business error | Report the returned code and message; only a successful empty `data.list` means no results |
| SSE disconnected | Reconnect via `/messages/reconnect`; returns SSE or JSON `no_active_task`. SSE may later emit `timeout`; retrieve offline messages when needed |
| Instance expired | Inform user time has run out; ask if they want to renew |
| Network timeout | Prompt user to retry later |
| Download Agent package installation failed | Show specific error; do not force write |
| 2010 on agent detail / order create | Agent is offline or unavailable; inform user and suggest searching for an alternative |
| 2004 on agent detail | Agent not found; inform user and suggest searching again |

## Updater storage and inspection

The updater replaces files individually and stages locked files as `<file>.new`. It preserves `config.json`, `thin_skills_state.json`, `skills/` and `.cache/`; its lock, version state and pending-file list live under `.temp/`. `--check` reports eligibility without installing and does not replace `--ensure-supported`.
