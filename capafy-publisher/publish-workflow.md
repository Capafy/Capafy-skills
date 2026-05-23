# Publish Workflow Guide

This document only describes public entry points, web confirmation points, safe re-entry, and sensitive scan rules. The publish flow is driven by the JSON payload returned by each command; internal target / mode / scan / stage / package / validate logic is not written up as host-side operational steps.

## Publish Flow

### Login

Before email OTP login, the host must first complete the compliance consent gate: take the current platform `base_url`, strip a trailing `/api` to derive `web_base`, present `web_base/terms-of-service` and `web_base/privacy-policy` to the creator, and require explicit consent to the Terms of Service and Privacy Policy. Vague replies (such as "ok", "go", "continue", "next") do not count as explicit consent; `login-init` must not be run before explicit consent.

```bash
python3 packager.py login-init --email <email>
python3 packager.py login-verify --challenge-id <id> --code <otp>
```

If the creator directly provides a token, or asks to switch platform account / user:

```bash
python3 packager.py login-token --access-token '<token>'
```

Behavioral contract of `login-token`:

- First call `GET /agent/account` with the supplied token; this is the platform token validation and user info readback endpoint.
- If `/agent/account` returns 401, network failure, non-JSON, a business error code, or a non-object response, the command fails and stops.
- On validation failure, do not create, write, or overwrite the local `config.json`.
- Only after validation passes is the token and available account info written to the local `config.json` (the file under the capafy-publisher root) and adopted as the new local fallback account. The user skill's account file is not touched here; the user skill has its own switching logic.
- The command's JSON output must not contain the raw token, and error output must not echo the token either.

`publish-*` commands do not accept the token as a parameter; the read order is `CAPAFY_ACCESS_TOKEN` → local `config.json` (the file under the capafy-publisher root). So if a token already exists in the environment variable, it still takes precedence; `login-token` is responsible for refreshing the local fallback login state / local account. To switch to the new account written by `login-token`, the current process must not keep the old `CAPAFY_ACCESS_TOKEN`. `publish-init` first verifies platform login state; if not logged in or the token has expired, it returns `platform_login_required` / `platform_login_invalid` and does not continue candidate discovery.

The compliance consent gate only applies to interactive email OTP login. `CAPAFY_ACCESS_TOKEN`, the local `config.json`, or `login-token` use the authentication path after the token has already been issued, and do not repeat the consent prompt.

### Main chain

```bash
python3 self_update.py --check
python3 packager.py publish-init --env <env_id> --runtime-dir <absolute_path>
python3 packager.py publish-init --env <env_id> --runtime-dir <absolute_path> --skill-dir <single_skill_dir>
python3 packager.py publish-init --env <env_id> --runtime-dir <absolute_path> --agent-id <agent_id> --selections-file .temp/confirmed-selections.json
python3 packager.py publish-init --env <env_id> --runtime-dir <absolute_path> --selections-file .temp/confirmed-selections.json
python3 packager.py publish-configure --agent-id <agent_id>
python3 packager.py publish-configure --agent-id <agent_id> --dispositions-file <dispositions.json>
python3 packager.py publish-configure --agent-id <agent_id> --deep-scan
python3 packager.py publish-configure --agent-id <agent_id> --deep-scan-findings-file <findings.json>
python3 packager.py publish-ship --agent-id <agent_id>
```

The three web confirmation pages are: after `publish-init` **confirm the file content to be uploaded**, after `publish-configure` **confirm the secrets / environment variables etc. to be hosted**, after `publish-ship` **final confirmation and submit for review**.

Parameter boundaries:

- `--env` and `--runtime-dir` are required for `publish-init`; `--env` is the target runtime and is not necessarily the same as the host currently running publisher.
- If the subject being published is a `metadata.openclaw` skill, `--env` must be `openclaw`; do not change it to a dot-agent env just because the command is being run inside Claude Code / Codex.
- `--runtime-dir` is the project root / workspace root opened in the host session; it is not the publisher skill root, nor the source directory of the skill being published.
- When specifying a single local skill source directory, use a separate `--skill-dir <single_skill_dir>`; do not stuff it into `--runtime-dir`.
- `--skill-dir` must be a single skill root directory containing `SKILL.md`; the parent `skills` directory is not allowed.
- Do not reverse-derive `--runtime-dir` from the path of the skill being published. The selected skill's logical path goes into `--selections.skills[].path`, the real source directory is preserved via `--skill-dir`, and `--runtime-dir` only describes where this runtime session is working.
- Claude Code: pass the project root directory opened when `claude` was launched.
- Codex: pass the project root directory of the current Codex session.
- OpenClaw: pass the current OpenClaw workspace directory, e.g. `/home/admin_wsl/.openclaw/workspace_xxx`; do not pass a regular project root, user home, `~/.openclaw`, `~/.openclaw/skills`, or `~/.openclaw/skills/<skill>`.
- If only an OpenClaw skill source directory is known but the current OpenClaw workspace is not, stop and ask the creator; do not treat the skill directory or its parent `skills` directory as the project root. Once the workspace is known, both `--runtime-dir <workspace>` and `--skill-dir <single_skill_dir>` can be passed together.
- Even if this round selects a global skill, e.g. `/home/admin_wsl/.agents/skills/skill-vetter`, as long as Codex is currently running in `/home/admin_wsl/sunnet/project/agent_store`, you should pass `--runtime-dir /home/admin_wsl/sunnet/project/agent_store --skill-dir /home/admin_wsl/.agents/skills/skill-vetter`.
- Windows / WSL paths must be absolute paths accessible by the current system; publisher does not convert them automatically. See the `publish-init` section in SKILL.md for concrete examples.
- The dot-agent target does not probe the host and does not decide for you whether `runtime_dir` is reasonable; the OpenClaw target validates that it must be a legal workspace.
- When `publish-init` is run without `--selections`, it returns top-level `skills` / `plugins` / `crons` candidate arrays; if `--skill-dir` is passed, the candidates only return this explicit skill. Candidate entries do not carry a `selection` field — only appearing in the second submission's `--selections` indicates they have been selected. This step must run first so the host has real candidates to work with; constructing `--selections` without running Phase A and without `--skill-dir` is incorrect usage.
- The host LLM generates `--selections` from the candidates and user context: top-level `title`, `description`, `skills`, `plugins`, `crons`; when updating an existing Agent, an additional top-level `agent_id` may be included; if the host already has a definite `agent_id`, it can also be passed directly via `publish-init --agent-id <agent_id>` — both forms are semantically equivalent and must stay consistent. `title` / `description` are jointly determined by the creator's intent and the candidate info; do not default to blindly copying the candidate's name.
- When updating an existing Agent, first read back the `workflowInfo.selection_groups` from the latest version, recite the currently selected skill verbatim to the creator, and then ask a direct two-way choice: keep using the current skill, or switch to a different skill. The former means only updating the content of the same skill — continue using the existing `skills[]`; the latter goes back to Phase A to rescan candidates. Do not just ask "do you want to pick a new skill".
- Each `skills[].path` / `plugins[].path` / `crons[].id` in `--selections` must correspond to a Phase A candidate or the explicit `--skill-dir` skill; entries without correspondence must be removed, or you must first go back and ask the creator. Inventing path / name / description / purpose from impression, memory, or historical sessions is prohibited.
- `skills[]` must not be empty. When Phase A returns `skills: []`, stop and use plain language to confirm with the creator — per the field translation table in SKILL.md — the actual project root / the directory the skill lives in; do not submit empty selections, and do not continue creating a platform draft.
- Do not filter Phase A candidates by the Agent Card's `Name` / `Description` yourself: at the code level `discover_units` does not filter by agent name, and "there is no candidate that exactly matches the Agent Card name" does not mean "the workspace has no files". When candidates are non-empty but none match exactly, recite the candidates verbatim to the creator and have them pick / change the skill directory / change the Agent Card name; do not report "not found / no files / no skill" — see Core Iron Rule #7 in SKILL.md.
- When talking to the creator, translate CLI parameters / JSON fields / internal state names into plain language per the field translation table at the start of SKILL.md's "Core Iron Rule"; do not throw fields like `--skill-dir` / `--runtime-dir` / `agentType` / `selection_groups` at the creator.
- Before running `publish-init`, first confirm with the creator whether this is a brand-new publish vs continuing / version update; `agent_id` must be explicitly identified by the creator or come from `capafy_platform.api.list_agents_raw()` output.
- Before updating an existing Agent (selections carrying `agent_id`), you must call `get_latest_version_raw(agent_id)` to reconcile the historical skill selection; read the selected content only from `workflowInfo.selection_groups`, not the raw top-level `selectionGroups`.
- Each selected runtime unit should carry a `purpose` describing the unit's responsibility in the workflow; do not restore the `workflow_intent` / `selection_groups` / step index structure.
- By default `publish-configure` only runs the rule scan and continues; when the creator must choose how to handle sensitive items in buyout mode, generate a dispositions JSON file from the command payload and pass it via `--dispositions-file <dispositions.json>`; do not pass inline JSON. Only with an explicit `--deep-scan` will it, after the rule scan, return `needs_deep_scan` to the host LLM for a supplementary scan.
- For every step, look at the JSON payload first; `developer_next_steps` takes precedence over this document.
- When you encounter `review_url`, the first action is to paste it verbatim to the creator and then pause — see Core Iron Rule #1; after the creator returns from the web with a completion signal, then call `get_latest_version_raw` to reconcile, and confirmed skill selection is read from `workflowInfo.selection_groups` — see Core Iron Rule #2.


### publish-init parameter quick reference

| Parameter | Required | When to use | Correct value |
|---|---|---|---|
| `--env` | Yes | Every `publish-init` | Target runtime: `claude_code` / `codex` / `openclaw` |
| `--runtime-dir` | Yes | Every `publish-init` | Project root / workspace root opened in the current host session; must be a path accessible on the current system |
| `--skill-dir` | No | When the creator explicitly designates a single local skill source directory | Single skill root directory containing `SKILL.md` |
| `--selections` | No | Submit confirmed selections; not recommended to use directly with multi-line JSON | JSON object string |
| `--selections-file` | No | Submit confirmed selections; the recommended approach | Path to a UTF-8 JSON file |
| `--reset-local-state` | No | When the creator explicitly abandons the current local publish scene | Takes no value; do not use to handle configure / ship errors |

`--selections` and `--selections-file` are mutually exclusive. On submission, the same `--env` / `--runtime-dir` / `--skill-dir` from Phase A must be reused.

### publish-init request examples

The examples below use the Codex current project root `/home/admin_wsl/sunnet/project/agent_store` and explicitly publish the global skill `/home/admin_wsl/.agents/skills/skill-vetter`. Other paths must not be copied verbatim; replace them with the actual paths on the local machine.

1. Phase A candidate discovery, no platform draft is created:

```bash
python3 packager.py publish-init --env codex --runtime-dir /home/admin_wsl/sunnet/project/agent_store --skill-dir /home/admin_wsl/.agents/skills/skill-vetter
```

Expected response shape:

```json
{
  "skills": [
    {
      "path": ".agents/skills/skill-vetter",
      "name": "skill-vetter",
      "unit_type": "skill"
    }
  ],
  "plugins": [],
  "crons": []
}
```

2. Write `.temp/confirmed-selections.json`. `path` and `name` must come from Phase A candidates; `purpose` must be the workflow responsibility confirmed by the creator:

```json
{
  "title": "Skill Security Review",
  "description": "Automatically review the code security of third-party skills, detecting red-flag patterns and permission boundaries",
  "skills": [
    {
      "path": ".agents/skills/skill-vetter",
      "name": "skill-vetter",
      "purpose": "Review skill source code, detecting credential leakage, network exfiltration, permission escalation and other security risks"
    }
  ],
  "plugins": [],
  "crons": []
}
```

3. Submit to create a new Agent:

```bash
python3 packager.py publish-init --env codex --runtime-dir /home/admin_wsl/sunnet/project/agent_store --skill-dir /home/admin_wsl/.agents/skills/skill-vetter --selections-file .temp/confirmed-selections.json
```

4. When updating an existing Agent, add `agent_id` to the top level of `.temp/confirmed-selections.json`:

```json
{
  "agent_id": "agt_xxx",
  "title": "Skill Security Review",
  "description": "Automatically review the code security of third-party skills, detecting red-flag patterns and permission boundaries",
  "skills": [
    {
      "path": ".agents/skills/skill-vetter",
      "name": "skill-vetter",
      "purpose": "Review skill source code, detecting credential leakage, network exfiltration, permission escalation and other security risks"
    }
  ],
  "plugins": [],
  "crons": []
}
```

5. Submit the updated version; the command still reuses the same set of local parameters:

```bash
python3 packager.py publish-init --env codex --runtime-dir /home/admin_wsl/sunnet/project/agent_store --skill-dir /home/admin_wsl/.agents/skills/skill-vetter --selections-file .temp/confirmed-selections.json
```

Common wrong examples:

| Wrong input | Reason |
|---|---|
| `publish-init --env codex --selections-file .temp/confirmed-selections.json` | Missing required `--runtime-dir` |
| `--runtime-dir /home/admin_wsl/.agents/skills/skill-vetter` | Treats the skill source directory as the project root |
| `--skill-dir /home/admin_wsl/.agents/skills` | `--skill-dir` can only be a single skill root directory, not the parent `skills` directory |
| `{"selection_groups": {"skills": [...]}}` | `publish-init` only accepts top-level `skills` / `plugins` / `crons` |
| `{"workflow_intent": "...", "skills": [...]}` | `workflow_intent` has been retired and is not an init input |
| `{"skills": [{"path": "guessed path"}], "plugins": [], "crons": []}` | `path` must correspond to a Phase A candidate |
| `{"skills": [], "plugins": [], "crons": []}` | No selected skill; must go back to Phase A or ask the creator to confirm |

Web confirmation points:

| Source | Meaning |
|---|---|
| `publish-init` | Confirm the file content to be uploaded |
| `publish-configure` | Confirm the secrets / environment variables etc. to be hosted; returned only when needed |
| `publish-ship` | Final confirmation and submit for review |

### Worked Example

| Step | Action | Expected output |
|---|---|---|
| 1 | `python3 self_update.py --check` | `up_to_date` / `update_available` / `check_failed` |
| 2 | Log in or refresh token | Token written into `config.json`, `publish-init` login-state verification passes |
| 3 | Confirm with the creator brand-new publish vs continuing / version update; for continuing publish, first ask whether to switch the skill directory, then branch by option | Creator intent (+ `agent_id`, only for continuing publish) |
| 4 | (Only for continuing publish) Call `capafy_platform.api.get_latest_version_raw(agent_id)` to pull historical selections (from `workflowInfo.selection_groups`; only represents historical selection). The historical `skills[].path` is the **platform logical path** of the previous version, **do not treat it as the current local path** — confirm with the creator the current local package directory via the field translation table in plain language before running step 5 (Core Iron Rule #8) | Historical skill `name` / `description` / `purpose` + the local package directory confirmed by the creator |
| 5 | `publish-init --env <env_id> --runtime-dir <absolute_path> [--skill-dir <single>]` (Phase A must run first) | Top-level `skills` / `plugins` / `crons` candidate JSON |
| 6 | Candidates + creator intent (+ historical selections, only for continuing publish) → assemble confirmed selections (continuing publish carries `agent_id` at the top) | Confirmed selections JSON |
| 7 | `publish-init --env <env_id> --runtime-dir <absolute_path> [--skill-dir <single>] --selections-file .temp/confirmed-selections.json` | `submitted` + `agent_id` / new `agent_version_id` + `review_url` |
| 8 | Paste `review_url` verbatim to the creator, wait for the creator to complete the first page (confirm the file content to be uploaded, Core Iron Rule #1) | First page confirmation complete |
| 8.5 | Call `get_latest_version_raw(agent_id)` to reconcile (Core Iron Rule #2); when skill selection needs to be confirmed look at `workflowInfo.selection_groups`, the raw top-level `selectionGroups` is not the basis for confirmation; if `agentType=run_online`, ask the creator in plain language whether to run the deep scan | Creator explicitly agrees / refuses the deep scan; download mode skips this step |
| 9 | `publish-configure --agent-id <agent_id>` (add `--deep-scan` when the creator agrees) | `ready_for_ship` / `review_url` / `needs_creator_disposition` / other handleable states; when `review_url` is returned, paste it verbatim per Iron Rule #1 |
| 10 | `publish-ship --agent-id <agent_id>` | `shipped` + final `review_url` (**only indicates the package has been uploaded**, not submitted for review) |
| 11 | Paste the final `review_url` to the creator, let them open the **final confirmation and submit-for-review** page; until the creator explicitly tells you the final page has been clicked through, **do not** say "submitted / under review / approved". After the creator comes back, call `get_latest_version_raw` to reconcile per Core Iron Rule #2; only when the platform genuinely shows "under review" may you report it that way | Creator completes submission, platform reconciliation shows under review |

The difference between continuing / version update and first-time publish is only in steps 3 / 4 / 6 / 7: step 3 needs to obtain `agent_id` and first confirm whether to switch the skill directory; step 4 makes one extra call to `get_latest_version_raw` to pull history; if following the historical flow, step 6 selections carry `agent_id` at the top and step 7 returns a new `agent_version_id`. If switching to a new skill and new flow, go back to Phase A to rescan candidates and then go through the new selections. The remaining steps are exactly the same.

`--skill-dir` must pass the same value in both step 5 / step 7; `--runtime-dir` still passes the current host project root / OpenClaw workspace.

Never construct `--selections` directly without having run Phase A and without having reconciled historical platform selections. `agent_id` must come from the creator's explicit identification or `list_agents_raw()` output; do not grab it casually from a local `.temp/` manifest or a previous session. Also, do not bypass `publish-init`'s web confirmation by going through the platform back office.

If the creator explicitly designates a particular local skill source directory, both the Phase A step above and the subsequent submission step with `--selections` carry the same `--skill-dir <single_skill_dir>` (corresponding to steps 4 / 6 for first-time publish, and steps 5 / 7 for continuing publish). `--runtime-dir` still passes the current host project root / OpenClaw workspace and does not change with the skill source directory.

### Re-entry and cleanup

| Situation | Correct action |
|---|---|
| Any step returns `review_url` (include all of them if a single response carries multiple) | **First action**: paste verbatim to the creator and explain what this page is for; only then pause. After the creator finishes, call `get_latest_version_raw` to reconcile (Core Iron Rule #1 + #2). Of these, `publish-init` is confirming the file content to be uploaded, `publish-configure` is confirming the secrets / environment variables etc. to be hosted (filled in on the webpage, do not have the creator send them in chat), and `publish-ship` is the final confirmation and submit for review |
| The creator has completed the first page (confirm the file content to be uploaded), `agentType` is `run_online`, about to run `publish-configure` for the first time | Per Core Iron Rule #1, send "do you want the deep scan" as a top-level chat message and wait. Agreed: add `--deep-scan`; refused: regular configure. Download mode skips this step |
| `publish-configure` returns `skills_empty_after_platform_confirmation` | After the first page (confirm the file content to be uploaded) was confirmed there was no selected skill; have the creator go back to the first page and select at least one skill, or rerun init with the correct `runtime_dir` / `skill_dir` |
| `publish-configure --deep-scan` returns `needs_deep_scan` | Per `staging_path`, do a supplementary scan for missed sensitive info; after no remaining misses, rerun configure without `--deep-scan` |
| `publish-configure` / `publish-ship` fails, local working state missing / stale | Default to resume: check local state with `publish-status`, then retry with `publish-configure --agent-id <agent_id>` / `publish-ship --agent-id <agent_id>`. **Do not** go back to `publish-init` to create a new agent (Core Iron Rule #6) |
| Seeing the `existing_local_publish_state` blocking error | This is a protection: default to resume, do not unconditionally `--reset-local-state` |
| The creator comes back from the web saying confirm / confirmed / submitted / done / pricing set | First call `get_latest_version_raw(agent_id)` to reconcile `agentType` / status / `agentVersionId`, then answer; do not infer "submitted for review" from the local manifest (Core Iron Rule #2) |
| The platform's `agentType` does not match the local manifest's `agent_type` | The creator changed the publishing mode on the web: local stage / staging / bundle are all invalidated; go back to `publish-configure --agent-id <agent_id>` to let the code rerun under the new `agentType` (Core Iron Rule #4) |
| The creator asks about review / publish / approval status | Call `capafy_platform.api.get_latest_version_raw(agent_id)` to see the platform's return; do not just run `publish-status` and answer |
| After some time the creator comes back saying "continue publishing / one more time" and similar things that need web confirmation | `review_url` is valid for 1 hour; per Core Iron Rule #1 rerun the corresponding CLI to obtain a **new** one and paste it; do not recite old, possibly-expired links from the session |
| Interpretation of `status` / `auditStatus` returned by the platform | Both are the state of the **latest version**. `status` is the overall version lifecycle (draft → review → listed → offline), `auditStatus` is the sub-state of the segment where `status` is in review. `status: 0` = **draft (not submitted)**, `auditStatus: 0` = **review not started**; seeing these two `0`s you must report "draft / review not started"; **never** misread it as "submitted / under review / approved". The complete enumeration is in `api-docs/00_overview.md` (Core Iron Rule #3) |
| The creator explicitly switches runtime / skill set and needs to rerun `publish-init` | First ask whether to switch the skill directory; first confirm the current local package directory with the creator per the field translation table (do not directly treat the historical `workflowInfo.selection_groups.skills[].path` as the local path — Core Iron Rule #8). If following the historical flow, selections must carry the original `agent_id`; if switching to a new skill / new flow, go back to Phase A to rescan candidates |
| The creator explicitly says "void this agent and publish a new one" | Recite to confirm once more in chat, then use `publish-init --reset-local-state` and omit `agent_id`; this is the only situation where `agent_id` is omitted (Core Iron Rule #6) |
| The creator wants to "modify the rejected version / resubmit for review" | Rerun the whole main chain `publish-init` → `publish-configure` (re-scan + re-package) → `publish-ship` (re-upload). **The selections of `publish-init` must carry the original `agent_id` at the top**, so the code goes through `create_version_from_draft` to create a new version on the same Agent; missing `agent_id` will create a brand-new Agent out of thin air. Phrasing: go through scan / packaging / submit-for-review on the same Agent; **forbidden** to say "rerun the whole pipeline / last flow ended / generated a new draft version" (Core Iron Rule #6) |

`publish-status` only looks at the local `.temp` working state; it **does not** reflect platform review / publish status. `--reset-local-state` only cleans local staging; it **does not** notify the platform to void the agent. See Core Iron Rule #3 / #6.

## Sensitive Deep Scan

By default `publish-configure` automatically rebuilds staging, scans for sensitive items, and continues the subsequent configuration flow. When `--deep-scan` is explicitly passed, after the rule scan finishes it stops, returns `needs_deep_scan`, `staging_path`, and `reviewed_scan_path`, and does not submit the platform configuration.

`reviewed-scan.json` is still generated by code. The host LLM does not hand-write this file, nor does it need to supply `_review`, digest, or bucket fields.

The host LLM only intervenes when supplementary scanning is required for sensitive info missed by the rule scan. The plaintext `generic` items hit by the rule scan have already been rewritten to platform-hosted placeholders before deep scan; `url_proxy` / `env_var` / `excludes` have also been generated by the regular pipeline. Deep scan is not a second review of `url_proxy` / `generic` / `env_var` / `excludes` already hit by the rule scan, nor is it patching `reviewed-scan.json`.

Deep scan only looks at risks of generic secrets / sensitive values that rules/regex find hard to cover:

- Real credentials, private tokens, or sensitive configuration values described in natural-language explanations, prompts, READMEs, or comments.
- Non-standard field names, mixed-language fields, nested configurations, concatenated tokens.
- New providers, new auth formats, or platform-private configurations not covered by the rule scan.
- Configuration material outside the scan context but that will enter the runtime package.

Rules:

- Deep scan only reports "risks the rule scan did not catch"; do not re-classify already-hit buckets.
- Do not actively discover new `url_proxy`; have the host LLM output a JSON object whose top level only has the two arrays `generic` and `env_var`: `{"generic": [], "env_var": []}`. The `generic` array holds file findings; the `env_var` array holds environment variable findings.
- Example values, placeholders, test stubs, documentation snippets, and runtime-irrelevant text are not treated as missed risks.
- When a miss is found, give the specific file, field or snippet, reason, and recommendation; have the host LLM output a minimal findings JSON object: `generic` items should include `value` + `source`, `env_var` items need non-empty `value` + `field` (env var name). `generic.source` must be the specific file relative path in the final zip file list within staging — directories are not allowed, but `#json:/...`, `#toml:...`, or `line N` location details are allowed; `env_var` items keep only `value` + `field`. Then rerun `publish-configure --deep-scan-findings-file <path>` and hand it to the program for validation, field completion, placeholder rewriting, and regenerating reviewed-scan.
- The program first filters deep-scan `generic` findings to the staging sources within the final package boundary; only items retained after filtering are written to `reviewed-scan.json`, and the original value is replaced with a platform-hosted placeholder in the staging file. Replacement only happens in staging, and is not written back to the creator's original source.
- If a `generic` finding is missing `source`, its `source` points to a directory, `_scan_only/`, an internal manifest, a missing file, an escaped path, an already-excluded file, an existing `.zip` / `.tar.gz` archive artifact, or any other material that will not enter the final package, the program only filters that item and the flow continues. Do not hand-write reviewed-scan to retain such items; if you really need to publish that configuration, first have the corresponding file enter the staging/package boundary.
- After confirming no remaining misses, rerun `publish-configure` without `--deep-scan` to continue platform configuration or the buyout gate.
- Do not directly edit `.temp/reviewed-scan.json`.
- Credential files matched by filename/path go directly into `excludes`; values matched by provider key regex go into `generic`.
- Misses found by deep scan cannot be resolved by manually patching buckets, and the host LLM should not actively collect new variables from the host environment. Generic secrets and environment variables must be expressed separately: file sources go into `generic`, environment variable sources go into `env_var`, and `url_proxy` can still only be generated by the rule scan, runtime contract, or source configuration; if `--deep-scan-findings-file` validation fails, fix the finding's `value` / `source` or `field` and rerun, instead of changing scan rules at this step.

### Generated Payload

`reviewed-scan.json` is an internally generated artifact; the top level only keeps `url_proxy`, `generic`, `env_var`, `excludes`, and `_review`.

| Field | Description |
|---|---|
| `_review.reviewer` | Generator identifier, currently `rules_scan` |
| `_review.status` | Fixed `reviewed` |
| `_review.raw_scan_digest` | Raw scan digest |
| `_review.staging_digest` | Staging digest |
| `_review.scan_only_digest` | `_scan_only/` review material digest |
| `_review.env_id` | Current env |
| `_review.distribution_mode` | `cloud_hosted` / `buyout` |

Digest / context must align with the current input; on mismatch, `publish-configure` regenerates them and does not reuse the old reviewed payload.

### `url_proxy[]`

For a pair of LLM provider endpoint + API key:

| Field | Description |
|---|---|
| `api_key.value` | Original key value |
| `api_key.placeholder` | Platform-hosted placeholder |
| `api_key.field` | Original field name or path |
| `api_key.source` | Source file |
| `url.value` | Original endpoint value |
| `url.placeholder` | Platform-hosted placeholder |
| `url.field` | Original field name or path |
| `url.source` | Source file |
| `use` | Purpose description |

Under `cloud_hosted`, the LLM provider endpoint + API key supplied by the creator must be grouped into `url_proxy`. If deep scan discovers a provider key/url pair not hit by the rules, the scan rules or source configuration should be corrected and `publish-configure` rerun.

### `generic[]`

For standalone credentials or configuration values:

| Field | Description |
|---|---|
| `value` | Original value |
| `placeholder` | Platform-hosted placeholder |
| `field` | Original field name or path |
| `source` | Specific file relative path within staging in the final zip file list |
| `source_detail` | Location within the source file, e.g. `json:/token` or `line 3` |
| `occurrence_index` | Occurrence sequence number for the same source field |
| `use` | Purpose description |

`generic.source` is part of the deliverable boundary: the program uses the same final zip file list from the package stage to validate the source, and only accepts specific files in the list, not directories. Empty source, `process.env`, `_scan_only/`, `agent.stage_manifest.internal.json`, download package's `agent.bundle_context.json`, non-existent files, escaped paths, existing archive artifacts, and files pointed to by `excludes` will not enter `generic[]`. These cases only filter the corresponding single item and do not block configure. `source` still writes the staging relative path; for example, even if the final zip path for `workspace/config.json` in staging is `config.json`, `generic.source` still writes `workspace/config.json`.

### `env_var[]`

For environment variable references:

| Field | Description |
|---|---|
| `field` | Variable name |
| `value` | Current value; may be `null` when unknown |
| `use` | Purpose description |

### `excludes[]` / `strip[]`

`excludes` is for files or values that should not be uploaded to the cloud with the package, e.g. login credential files, authentication state files, high-risk files that the creator confirms to exclude wholesale.

`strip` is for values that should only be removed in plaintext from staging but not uploaded to the platform.

Each item must at minimum state source and reason:

| Field | Description |
|---|---|
| `source` | Source file or path |
| `use` | Reason for excluding or stripping |

### `.env` rules

Do not default to excluding the whole file just because the filename matches `.env`. The basis is content and use:

| Situation | Handling |
|---|---|
| Runtime-required `.env` | Keep in the package, values classified by semantics; Claude Code's `url_proxy` only recognizes `.claude/settings*`, login state, and explicit `process.env` references |
| `.env` inside a selected skill's root directory | Keep in the package, values classified by semantics and stripped; do not treat it as a Claude Code provider source |
| Login credential / authentication state files | `excludes` |
| High-risk files that the creator confirms to exclude wholesale | `excludes` |
| Runtime-irrelevant local development configuration | `excludes` |

Retaining `.env` in the package: keep the file shell, and have subsequent strip replace plaintext values with `PLATFORM_MANAGED_*` placeholders.

**Host-required config files must not be excluded wholesale**: `.claude/settings.json` / `.claude/settings.local.json` (required by the Claude Code host) and any other host configuration files already identified by `url_proxy` / `generic` / `env_var` as runtime-required **can only go through the `strip` path** (keep the file shell + replace values with placeholders). Such files **must not go into `excludes`** — excluding them wholesale would cause the cloud host to fail to start. The local `permissions` cache in `.claude/settings.local.json` is not part of the cloud runtime configuration; the main flow deletes this top-level block before packaging.

On the second page (confirm the secrets / environment variables etc. to be hosted) credential confirmation page, the host LLM **must not** suggest to the creator anything like "find an entry to exclude `.claude/settings.local.json` wholesale". Correct phrasing: tell the creator the keys have been automatically replaced with `PLATFORM_MANAGED_*` placeholders and uploaded with the package; the file shell is preserved because it is required for cloud Claude Code to run; the local permissions allowlist is removed by the main flow and the user does not need to manually exclude it. The second confirmation page is only for the secrets / environment variables list anyway, and does not provide a file-level wholesale exclusion entry.

### Creator confirmation display

- `url_proxy.api_key.value` is only displayed masked; the paired `url.value` may be displayed in full.
- `generic.value` may be displayed in full.
- Do not display `PLATFORM_MANAGED_*`, template variables, or internal fields verbatim to the creator.
- Entries already in `excludes` are displayed as a read-only summary with reason and source path.
- For `.env` files retained in the package, display the values that will be hosted or stripped within them.

### Web confirmation boundary

The reviewed payload is not the final confirmation. The runtime confirmation entry can only be the web confirmation page returned by the platform:

- After obtaining the web confirmation entry, the host must pause.
- Chat confirmation, script submission, reverse-engineering the web endpoint, or local preview must not be treated as equivalent substitutes.
- After the creator completes the web confirmation, continue based on the platform's readback result.

Before entering `publish-ship`, you must use the platform's web-confirmed `url_proxy` selection to continue; do not manually modify the local state.
