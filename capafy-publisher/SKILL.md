---
name: capafy-publisher
description: "Publish, update, or re-ship an Agent/Skill on the Capafy platform. Triggers include publish, list, upload, ship, package, Capafy, agent_id, review_url, log in, switch account, earnings / payout, statistics, refund, certification / KYC, relist, delist, delete-draft. Covers the full publish-init / publish-configure / publish-ship chain plus login, earnings queries, refund handling, and KYC certification. Supports Claude Code, Codex, and OpenClaw hosts."
---
# capafy-publisher

This file keeps only the run entries and the rules the host LLM must follow. Publishing is driven by the CLI's JSON output; internal details such as target, mode, scan, stage, package, and validate are handled by the code.

## Run Prerequisites

- Run scripts in this directory with `python3`.
- Python >= 3.8; Python 3.11+ uses the stdlib `tomllib`, 3.8-3.10 uses the built-in TOML fallback shipped with this skill.
- The host must allow `python3` execution inside this skill's directory. Claude Code needs `Bash(python3:*)` allowed in its permission settings.

## Self-Update

Run this before each use:

```bash
python3 self_update.py --check
```

Handle the response:

- `up_to_date`: continue.
- `update_available`: tell the creator and ask; on agreement run `python3 self_update.py`, then restart from the beginning after the update finishes.
- `check_failed`: continue using the current version; if a later platform response header carries `X-Skill-Version-Status: outdated|deprecated`, remind the creator at the next human-confirmation point.

`self_update.py` downloads a zip per the install manifest; if the manifest carries `sha256` / `sha256Hex` / `sha256_hex` it verifies the digest. When the update bundle does not carry `requirements.txt`, dependency installation is skipped. The Windows install mode first copies the updater into the system temp directory and lets an external runner replace the live skill directory, so the running script does not lock its own directory.

## Read Order

Runtime reads only:

- `SKILL.md`
- `publish-workflow.md`
- `api-docs/index.json`
- `api-docs/00_overview.md`

**Do not** read Markdown under `.temp/`, `.pytest_cache/`, `dist/`, or `docs/`.

## Public Commands

```text
login-init
login-verify
login-token
publish-init
publish-configure
publish-ship
publish-status
```

`publish-status` only reads the local `.temp/` working state and does **not** reflect platform review / listing status; route review questions through Core Iron Rule #3.

Login:

- Not logged in: `login-init` → `login-verify`
- Before email-OTP login the host must complete the compliance-consent gate: take the current platform `base_url`, strip the trailing `/api` to get `web_base`, show the creator `web_base/terms-of-service` and `web_base/privacy-policy`, and require explicit consent to both the terms of service and the privacy policy. Vague replies (e.g. "ok", "go", "continue", "next") do not count as explicit consent; do not run `login-init` until explicit consent is given. This rule applies only to email-OTP login; `CAPAFY_ACCESS_TOKEN`, the local `config.json`, and `login-token` use the post-issuance auth path and do not re-prompt for consent.
- When the creator pastes a token directly, or asks to switch the platform account / user: `login-token --access-token <token>` is the only entry. It must first call `GET /agent/account` with that token to validate against the platform; only when the HTTP call succeeds and the account response is valid is the token written to the local `config.json` (the file under the capafy-publisher root) as the new local fallback account. This does not touch the user skill's account file — the user skill has its own swap logic.
- When `login-token` validation fails, halt and report; do not write or overwrite the local `config.json` (under the capafy-publisher root), and do not echo back the token the creator pasted.
- Token priority: `CAPAFY_ACCESS_TOKEN` → local `config.json` (under the capafy-publisher root). If `CAPAFY_ACCESS_TOKEN` is set in the current process, it still overrides whatever `login-token` wrote locally; to let the new local account take effect, remove or replace that environment variable.
- `base_url` only reads the explicit argument, `CAPAFY_PLATFORM_BASE_URL`, and the code default; it is not read from the local `config.json`.
- `publish-init` first validates the platform login state; when not logged in or the token is invalid it returns a structured login error and does not enter candidate discovery.

## Publish Main Chain

```text
publish-init → web confirmation → publish-configure → handle per JSON output → publish-ship → web confirmation
```

The three web confirmation pages are: after `publish-init`, **confirm the file contents to upload**; after `publish-configure`, **confirm the keys / environment variables etc. to be hosted**; after `publish-ship`, **final confirmation and submit for review**.

What comes next after `publish-configure` / `publish-ship` is decided entirely by the structured payload: `status`, `review_url`, `developer_next_steps`, `blocking_category`, `failed_step`, and similar fields take precedence over this document.

## Core Iron Rules

**Always talk to the creator in plain language**: CLI parameters, JSON fields, and internal state names exist only between you (the host LLM) and the code; **do not** speak them directly to the creator. Translate quoted phrases for the creator using this table:

| Program field / parameter | What to say to the creator |
|---|---|
| `--skill-dir` | "skill directory" / "skill source directory" |
| `--runtime-dir` | "project root" / "workspace path" |
| `--env` | "target runtime environment" |
| `--selections-file` | "selections file" |
| `--reset-local-state` | "discard the local draft and start over" |
| `--deep-scan` | "deep scan" |
| `--dispositions-file` | "dispositions file" |
| `agent_id` | "Agent ID" |
| `agent_version_id` | "Version ID" |
| `agentType` / `agent_type` | "publishing mode" |
| `agentType: run_online` / `agent_type: run_online` | "Run Online mode" |
| `agentType: download` / `agent_type: download` | "Download mode" |
| `selections` / `selection_groups` / `workflowInfo.selection_groups` | "the skill selection for this release" |
| `Phase A` / `discover_units` | "local scan" |
| `manifest` / `.temp/` working state | "local draft" |
| `review_url` | Paste the link verbatim plus a one-line note about what the page is for; differentiate by source: `publish-init` = "confirm the file contents to upload", `publish-configure` = "confirm the keys / environment variables etc. to be hosted", `publish-ship` = "final confirmation and submit for review" |
| `publish-init` / `publish-configure` / `publish-ship` | "publish step one / configure / submit for review", or just speak the command name |

Translate fields not in this table by the same principle; when uncertain, prefer plain language describing what it does instead of inventing new terminology.

No matter which step of the main chain you are on, or which error has interrupted you, the rules below do not change:

1. **Anything that needs creator action: send a visible message first, then pause.** When the CLI JSON returns a `review_url`, paste it to the creator verbatim (all of them if multiple) along with a note about what the page is for; questions to the creator (deep-scan consent / `agent_id` confirmation / skill reselection / whether to abandon the agent, etc.) follow the same rule — send a top-level chat message, do not silently wait inside a thinking / processing block. **`review_url` is valid for one hour and then expires**: if some time later the creator says "continue publishing / try again" or anything that requires opening a web page, do not re-paste an old `review_url` from earlier in the session — rerun the corresponding CLI (`publish-init` / `publish-configure` / `publish-ship`) to get a fresh one and paste that.
   - `review_url` returned by `publish-init`: the creator should **confirm the file contents to upload**.
   - `review_url` returned by `publish-configure`: the creator should **confirm the keys / environment variables etc. to be hosted** (filled in on the web page; do not let the creator send secrets in chat).
   - `review_url` returned by `publish-ship`: the creator should **make the final confirmation and submit for review**. `status: shipped` only means the package has been uploaded to the platform and the final-page URL has been issued; **the actual "submit for review" action must be performed by the creator on the final page**. Until the creator explicitly tells you the final page has been clicked through, never say "submitted / under review / approved" or anything else carrying "submitted for review / review process started" semantics.
2. **After a web page, you must reconcile with the platform.** When the creator returns from a web page with a signal like "confirm / done / fixed / price set", first call `capafy_platform.api.get_latest_version_raw(agent_id)` and read the returned `agentType` / status / `agentVersionId` before answering — do not infer from the local manifest. When you need to check whether the confirmation page already has selected skills, do not look at the raw response's top-level `selectionGroups`; that field may be empty. Look only at `workflowInfo.selection_groups`, or the `selection_groups` exposed by `packaging._shared.platform.get_latest_version()` in code. After the web confirmation page, **the platform is the source of truth**.
3. **Review status comes from the platform only.** Questions like "how far has the review gone / did it pass / is it listed?" must call `get_latest_version_raw(agent_id)`. `publish-status` only reads the local `.temp/`; `publish-ship`'s `status: shipped` only means the package has been uploaded — **it does not mean submitted for review, under review, or approved**. The full chain is: `shipped` → the creator clicks submit on the final page → `get_latest_version_raw` actually reads back "under review" → only then does the platform progress to "approved / rejected". Until every link has been satisfied, do not say "submitted / under review / approved" in chat. **`status` and `auditStatus` are both states of the latest version, not aggregates across the whole agent history; do not mix them up**: `status` is the **agent lifecycle state** of the latest version overall (draft → review → listed → delisted, the main axis); `auditStatus` is only the **review sub-state** during the "under review" segment of `status` (automated / manual / passed / failed). **Real meaning of the two `0` values**: `status: 0` = **draft (not submitted)**, `auditStatus: 0` = **review not started**; when you see these two `0`s you must report "draft / review not started" and **never** misread them as "submitted / under review / approved". Full enums (`status` 0=draft / 1=under review / 2=review failed / 3=review passed pending listing / 4=listed / 5=expired / 6=delisted; `auditStatus` 0=not started / 1=auto review in progress / 2=manual review in progress / 3=review failed / 4=review passed) are in `api-docs/00_overview.md`.
4. **`agentType` mismatch = local state invalidated.** When the platform `agentType` differs from the local manifest's `agent_type` (typical: the creator toggled `run_online` ↔ `download` on the web page), the platform has already rolled the version back to draft and cleared the confirmed skill selection. Return to `publish-configure --agent-id <agent_id>` so the code re-stages / re-scans / re-packages under the new `agentType`; do not report "submitted for review" based on the stale manifest.
5. **Source of `agent_id`.** It must come from explicit creator confirmation or from `capafy_platform.api.list_agents_raw()`. Do not invent it from `.temp/` manifest, the previous session, or anywhere else.
6. **Blocks do not justify a new agent.** Once an `agent_id` has been obtained, any block defaults to resume (`publish-status` → `publish-configure` / `publish-ship` / wait for the creator to finish the `review_url`); do not return to `publish-init` and rebuild. `--reset-local-state` only clears local staging — it does **not** tell the platform to abandon the agent; use it only when the creator explicitly says "scrap this and ship a new one", and recap that decision in chat before running. **Resubmitting a rejected version is also a block, not an agent swap**: when the creator wants to "fix the rejected version / resubmit for review", rerun the main chain `publish-init` → `publish-configure` (re-scan + re-package) → `publish-ship` (re-upload) — **the selections payload of `publish-init` must carry the original `agent_id` at the top level**, so the code goes through `create_version_from_draft` to create a new version on the same Agent; **omitting `agent_id` makes the code go through `create_agent_from_draft` and create a brand-new Agent**, which is wrong and leaves an orphan listing on the platform. In chat with the creator, frame it as "running the scan / package / submit-for-review flow again on the same Agent"; **never** say things like "running the whole pipeline again / the previous flow has ended / generated a new draft version" that imply an agent swap.
7. **No making things up — and also no filtering out candidates.** Before constructing `--selections`, you must have already run `publish-init` (without `--selections`) in this session with the same `--env` / `--runtime-dir` / `--skill-dir` and obtained candidates, or you must have passed `--skill-dir` to lock down a single skill. `skills[].path / .name` etc. must correspond one-to-one to Phase A candidates; the moment you catch yourself thinking "I remember / should be / usually there is...", stop and rescan. **The converse is equally forbidden**: do not filter Phase A candidates yourself by exact match against the Agent Card's `Name` / `Description` — the code-level `discover_units` does not filter by agent name, and "no candidate exactly matches the Agent Card name" does **not** equal "no files / no skill in the workspace". In that case, you must read all candidates verbatim to the creator and ask in plain language per the translation table, e.g.: "I scanned N skills locally, but none of them exactly matches your Agent Card name `<name>` — do you want to publish one of them? Or switch the skill directory? Or update the Agent Card name?" Never reply with "not found / no files / no skill".
8. **For continued publishing, reconcile history first.** Before updating an existing Agent (selections carries `agent_id`), you must call `get_latest_version_raw(agent_id)`, read the previous version's skill `name` / `description` / `purpose` from `workflowInfo.selection_groups`, and match them against local Phase A candidates by `name` (first priority) then `description` (second priority); ask the creator about anything that does not match — do not copy from last time or guess. **Do not treat historical paths as local paths**: `workflowInfo.selection_groups.skills[].path` is the **logical path** the platform saved for the previous version (relative to that run's `--runtime-dir`), **not the current file location on this machine**. Whether the creator picks "reuse" or "switch", you must first confirm the **current package directory on this machine** (project root + skill directory) with the creator in plain language per the field table, and run Phase A with those confirmed real paths — do not pass the historical `path` directly as `--skill-dir` / `--runtime-dir`.
9. **Only one publish main chain at a time; no parallel / auto-batch.** At any moment only one publish main chain (`publish-init → publish-configure → publish-ship`) can be in progress; while the current chain has not finished, you may not start another main chain in parallel or nested to publish a different Agent, and you may not auto-loop through a directory running init→ship on every skill in turn.
   - **Allowed**: bundling multiple skills inside a single Agent's `skills[]` and shipping them together — this is the normal one-Agent-many-skills usage, not batch.
   - **Allowed**: after a `publish-ship` has finished, if the creator wants to publish another Agent in the same session, you may start a new publish main chain in sequence, starting normally from `publish-init`; confirm each step of each chain — do not auto-chain multiple together.
   - **Not allowed**: treating multiple skills as separate Agents and having the publisher "batch publish" them at once — you may not run through N publish main chains for the creator in a single prompt.
   - **Does not affect version updates**: a version update on the same `agent_id` is itself one publish main chain — proceed normally.
   - **Triggers and handling**:
     a. If the creator opens with "ship these skills for me / publish all skills in this directory / do them one by one", pause first and confirm intent in plain language per the table — is this one Agent containing multiple skills (a bundle), or multiple independent Agents? If bundle, proceed normally to `publish-init`; if independent Agents, tell the creator explicitly that they will be processed **one chain at a time, sequentially** (no auto-loop), and have the creator pick which one to publish **this time** — the others will be handled as separate chains afterward.
     b. After a `publish-ship` has finished and the creator wants to publish another Agent, start a new publish main chain to handle it — there is no need to open a new session; but still run only this one chain — do not roll later ones into it "for convenience".

## publish-init

Before running, confirm with the creator whether this is a **brand-new publish** or a **continue / version update**:

- Brand-new publish: when the creator has not said what to publish, ask about scope first; when they have given only the runtime / project root and no skill, run Phase A directly and read the candidates to the creator for selection.
- Continue / version update: obtain `agent_id` per Core Iron Rule #5, and reconcile historical selections per Core Iron Rule #8.

Once an `agent_id` has been obtained in this session, any block defaults to resume — do not rebuild the agent:

- Any error from `publish-configure` / `publish-ship`: first read the payload's `developer_next_steps` / `failed_step` / `blocking_category`, then decide whether to retry the same step, run the supplementary sensitive-info scan, or wait for the creator to finish the `review_url` web confirmation. **Do not** rerun `publish-init` to recreate just because something failed.
- If `publish-configure` reads the platform back and finds the first page (the file-contents confirmation) had `skills[]` empty after confirmation, the creator removed all skills on the web page. Halt; have the creator return to the first page and pick at least one skill, or rerun the publish first step with the correct project root / skill directory. Do not continue to configure / ship.
- Web confirmation page will not open / is stuck / the creator is offline: pause and wait for the creator. Do not rerun `publish-init`.
- Seeing the `existing_local_publish_state` blocking error: this is a guard, not an error. The first choice is `publish-status` to inspect local state, then `publish-configure` / `publish-ship` to continue — **not** straight to `--reset-local-state`.
- `publish-init --reset-local-state` only clears local `.temp/` staging; it does **not** tell the platform "abandon the previous agent". Unless the creator explicitly says "I want to ship a new agent, not the old one", do not use `--reset-local-state`, and certainly do not use it to "fix" upload errors.
- When the creator explicitly wants to switch runtime / switch skill set and `publish-init` needs to be rerun, the selections **must carry the original `agent_id`**, going through the "continue / version update" branch; only when the creator explicitly wants a brand-new agent may `agent_id` be omitted, and the decision to abandon the old agent must be recapped to the creator in chat before running.

`publish-init` must be given an explicit target runtime environment and the project root of the creator's current host session:

```bash
python3 packager.py publish-init --env <env_id> --runtime-dir <absolute_path>
```

- `--env <env_id>`: target runtime; values are `claude_code` / `codex` / `openclaw`. If the object being published is a `metadata.openclaw` skill, you must use `openclaw`.
- `--runtime-dir <absolute_path>`: the project root / workspace root the host session has open; do not derive this value from the source path of the skill being published, a parent `skills` directory, or the publisher skill root.
- `--skill-dir <single_skill_dir>`: optional; pass it only when the creator explicitly specifies a single local skill source directory. It must point at a single skill root containing `SKILL.md`; it cannot be a parent `skills` directory, and it does not replace `--runtime-dir`.
- Claude Code / Codex: pass the project root opened when starting `claude` / `codex`, i.e. the current session working directory.
- OpenClaw: pass the current OpenClaw workspace directory, e.g. `/home/admin_wsl/.openclaw/workspace_xxx`; do not pass a regular project root, user home, `~/.openclaw`, `~/.openclaw/skills`, or a single skill directory.
- On Windows native, `C:\Users\me\project` is fine; on WSL / Linux, pass a path the current system can actually access, e.g. `/mnt/c/Users/me/project` — do not expect the publisher to auto-translate Windows paths.
- dot-agent targets do not auto-detect the host environment and do not check whether `runtime_dir` is reasonable; OpenClaw targets validate that it must be a real workspace.

Example: when Codex is currently running at `/home/admin_wsl/sunnet/project/agent_store` and the skill being published lives at `/home/admin_wsl/.agents/skills/skill-vetter`, pass:

```bash
python3 packager.py publish-init --env codex --runtime-dir /home/admin_wsl/sunnet/project/agent_store --skill-dir /home/admin_wsl/.agents/skills/skill-vetter
```

### publish-init copy-pastable examples

Prefer `--selections-file`; do not stuff multi-line JSON into a shell string. The first run must be Phase A without `--selections`, to obtain real candidates:

```bash
python3 packager.py publish-init --env codex --runtime-dir /home/admin_wsl/sunnet/project/agent_store --skill-dir /home/admin_wsl/.agents/skills/skill-vetter
```

Then write `.temp/confirmed-selections.json` based on the Phase A candidates. `skills[].path` / `name` must be verbatim from the candidates; `purpose` is the use-description the creator has confirmed:

```json
{
  "title": "Skill Security Review",
  "description": "Automatically reviews third-party skill source for security issues; flags red-flag patterns and permission boundaries",
  "skills": [
    {
      "path": ".agents/skills/skill-vetter",
      "name": "skill-vetter",
      "purpose": "Reviews skill source for credential leaks, network exfiltration, permission overreach, and other security risks"
    }
  ],
  "plugins": [],
  "crons": []
}
```

When submitting the first-page draft, you must reuse the same `--env` / `--runtime-dir` / `--skill-dir`:

```bash
python3 packager.py publish-init --env codex --runtime-dir /home/admin_wsl/sunnet/project/agent_store --skill-dir /home/admin_wsl/.agents/skills/skill-vetter --selections-file .temp/confirmed-selections.json
```

When updating an existing Agent, the request body simply adds `agent_id` at the top level; `agent_id` must come from explicit creator confirmation or `list_agents_raw()`:

```json
{
  "agent_id": "agt_xxx",
  "title": "Skill Security Review",
  "description": "Automatically reviews third-party skill source for security issues; flags red-flag patterns and permission boundaries",
  "skills": [
    {
      "path": ".agents/skills/skill-vetter",
      "name": "skill-vetter",
      "purpose": "Reviews skill source for credential leaks, network exfiltration, permission overreach, and other security risks"
    }
  ],
  "plugins": [],
  "crons": []
}
```

When `publish-init` is run without `--selections`, it returns the top-level `skills` / `plugins` / `crons` candidate arrays directly; when `--skill-dir` is given, the candidates only include that explicit skill. Candidate entries do not carry a `selection` field — they only count as "selected" once they appear in the `--selections` of the second submission. The host LLM combines candidates with user context to produce `title`, `description`, and a per-unit `purpose`, confirms with the creator, then submits.

When updating an existing Agent, do not just ask "do you want to pick a new skill?". First ask the creator whether to switch the skill directory, then split the choice into two options:

1. Use the historical selection and flow. Continue with the historical selection returned by the platform; `workflowInfo.selection_groups` only represents the skill selection already confirmed by the previous version — it is not a fresh discovery result.
2. Use new skills and a new flow. Return to Phase A, rescan for candidates, reconfirm `skills[]` against the new skill directory, then submit.

Explain both options clearly first, then let the creator choose. If the creator says "just changing the old skill's contents", the default is to continue with the current skill — do not reselect. Settle this judgment inside `publish-init`; do not defer it to `publish-configure`.

**Whether option 1 or option 2, you must first confirm the current package directory on this machine** (project root + skill directory) with the creator in plain language per the field table, and pass those confirmed real paths as `--runtime-dir` / `--skill-dir` to Phase A — see Core Iron Rule #8 "Do not treat historical paths as local paths". `workflowInfo.selection_groups.skills[].path` is the **platform logical path** of the previous version (relative to that run's `--runtime-dir`); it does not represent the actual current file location on this machine, and the creator may have moved or renamed files since. Passing the historical `path` directly as `--skill-dir` / `--runtime-dir` will cause staging / bundle to write to the wrong path, and the validator will report cycles downstream.

- Continue with the current skill: this run is just updating the contents of the same skill — reuse the existing `skills[]` and continue directly to the downstream draft / scan / submit.
- Switch to a different skill: this run is changing the publish target — return to Phase A, rescan, then reconfirm `skills[]`.

If Phase A returns an empty `skills[]`, or none of the candidates match the creator's intent, **do not enter the next step** and do not submit an empty `skills`. Read the candidates to the creator and have them confirm the actual project root / skill directory in plain language per the table, or confirm whether to publish one of the other discovered skills this time. `publish-init --selections` requires at least one selected skill; without a skill there is no way to request creating a platform draft.

Two hard rules — break either and stop right away to rerun Phase A or ask the creator:

- **Phase A is mandatory**: before constructing `--selections`, you must have already executed `publish-init` (without `--selections`) in this session with the same `--env` / `--runtime-dir` / `--skill-dir` and obtained a candidate JSON; or you must have passed `--skill-dir` to lock down a single skill. If neither is satisfied, you may not construct selections from memory, previous sessions, or guesses.
- **No making things up**: every `skills[].path`, `skills[].name`, `plugins[].path`, and `crons[].id` in `--selections` must correspond item-by-item to a Phase A candidate (or to the explicit skill from `--skill-dir`). Any path / name / description / purpose of unknown origin must go back to Phase A for a rescan, or be asked to the creator first. The moment you find yourself thinking "I remember there is...", "there should be...", "there is usually one...", stop.

`--selections` must not be wrapped in `selection_groups`, and must not carry `workflow_intent` / step index structures; when updating an existing Agent, add `agent_id` at the top level (source per Core Iron Rule #5).

## Sensitive Information Deep Scan

**Consent step before the first entry to `publish-configure` (Run Online mode only)**: after the creator completes the first page (confirm the file contents to upload), reconcile per Core Iron Rule #2 with `get_latest_version_raw(agent_id)`; if the platform `agentType` is `run_online`, before running `publish-configure` you must first ask the creator in plain language whether to run a deep scan, e.g.: "This release uses Run Online mode; do you want to run a deep scan? I'll re-read the packaged content to look for generic-secret / sensitive-value risks the rules did not catch — it costs more time and tokens. Skipping means only the regular rule scan runs."

Send this question as a visible chat message and then pause, per Core Iron Rule #1.

- Creator agrees: run `publish-configure --agent-id <agent_id> --deep-scan`; once `needs_deep_scan` comes back, produce a findings JSON object per the "Sensitive Deep Scan" section of `publish-workflow.md` (top level has only `generic` / `env_var` arrays), then submit via `publish-configure --agent-id <agent_id> --deep-scan-findings-file <path>`.
- Creator declines or chooses the fast path: run `publish-configure --agent-id <agent_id>` without `--deep-scan` — the code runs only the regular rule scan.
- Download mode (`agentType: download`) does not need this consent step; the platform does not host runtime keys, so go straight to the regular `publish-configure`.

Hard rules (details about sources, fields, and submission live in `publish-workflow.md`'s "Sensitive Deep Scan" section):

- Misses cannot be resolved by hand-patching buckets, nor by having the host LLM proactively collect new variables from the host environment.
- Generic secrets go into `generic` (each item has `value` + staging-relative `source`); environment variables go into `env_var` (each item has `value` + `field`); `url_proxy` can still only be produced by the rule scan, runtime contract, or source config.
- Do not edit `.temp/reviewed-scan.json` directly, and do not use already-generated buckets as review input.
- When `--deep-scan-findings-file` validation fails, fix the findings' `value` / `source` / `field` and rerun — do not change the scan rules at this step.
- Once you have confirmed there are no misses, rerun `publish-configure` without `--deep-scan` to continue with the platform configuration.
- **Host-required config files must not be excluded wholesale**: files already recognized as host-required runtime config such as `.claude/settings.json` / `.claude/settings.local.json` only go through `strip` (their keys have already been replaced by the code with `PLATFORM_MANAGED_*` placeholders). When the deep scan flags secrets in such files, do not suggest excluding the file outright — the file shell is required for running Claude Code in the cloud; the local `permissions` cache in `.claude/settings.local.json` is removed by the main flow. See the rule about not excluding host-required config files wholesale in `publish-workflow.md`.

## Other Requests

- `relist` / `delist` / `delete-draft`: the current shipped runtime does not have these APIs. Tell the creator explicitly that they are not supported, and do not work around them.
- Earnings, payout, statistics, refunds, KYC: read `api-docs/00_overview.md`.
- Local-only packaging self-check: there is no standalone local pre-flight entry; go through the formal main chain and handle failures per the JSON payload.

## Safety Boundaries

- `cwd` may be the publisher skill's own directory; do not default to treating it as the workspace to publish.
- When the creator says "workflow / project / workspace" and the input source is unclear, confirm with the creator first; when only a skill directory is given, treat it as `--skill-dir` and separately confirm the real `--runtime-dir`.
- Do not modify the working-state files under `.temp/` yourself. When you need to switch `runtime_dir` / switch selections, handle it per Core Iron Rule #6: by default rerun `publish-init` carrying the original `agent_id` (the continue / version-update branch), and **do not** proactively suggest `--reset-local-state`; only use reset when the creator explicitly says "scrap this agent and ship a new one", and recap that decision in chat first.
