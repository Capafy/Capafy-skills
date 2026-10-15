# Package installation and Thin Skill state

Read before installation, replacement or Thin Skill state repair. Order downloads require [authentication](authentication.md).

Commands and script paths below are relative to the installed Skill root, not this references directory. API signatures (read only the module needed): [download](../api-docs/07_download.md), [order](../api-docs/03_order.md).

## "Install the Skill package I purchased"

**Trigger phrases**: install, download Skill, Download Agent package, install older version, update Skill

```
→ Confirm agentId (from search results, order list, or context)

⚠️ Overwrite check (must run before installation):
→ Check whether the Skill already exists in the local skills directory
   ├── Already exists → must warn the user:
   │   "A local installation of this Skill was detected. Reinstalling will overwrite the current
   │    version. Any customizations you've made will be lost. Are you sure you want to continue?"
   │   → Only proceed after user confirms
   └── Not found → continue directly

→ Existing target: only after explicit user confirmation, add `--overwrite` to
  `scripts/install_package.py --order-id <orderId>` (or `--file <archive>`).
  Without this flag the installer refuses replacement. Apply the same rule after
  a new Run Online purchase if its Thin Skill directory already exists.
→ Replacement removes local customizations and obsolete package files. It updates
  only the local entry; an old order still downloads its order-version template,
  and cloud instance upgrades depend on the platform instance mechanism.

**Selection rule**: use the known paid order when available; otherwise get the latest package by agentId. Buyer order download has no version-selection query. If a historical version is requested, explain this limitation rather than promising an unsupported download.

Download method (choose one):
→ Quick download (latest): GET /agent/agent/agents/{agentId}/package
   → Free Skills can be downloaded without a purchase
   → Paid Skills require an existing purchase record
→ Download by order:
   → Need orderId (from order list: GET /agent/orders/buyer/list)
   → scripts/install_package.py --order-id <orderId>
   → Download orders normally use paid/completed; refunding is allowed only with a prior successfully signed download for this Agent. Hosted orders require paid/completed.
→ GET /agent/skill/{agentId}/versions is owner-only Agent history, not purchased-product history. Its appVersionId cannot be sent to buyer order download.
→ Preserve skillInstall.licenseId when returned; use thinSkillTemplate.folderName as returned, not an invented capafy-agent-* directory.

Installation:
→ Install directory: the skills directory where the current user skill resides
→ Buyout archives may wrap the package as `skills/<skill-name>/SKILL.md`; `install_package.py` resolves the actual directory containing `SKILL.md` before copying it to `skills/<skill-name>/`
→ Download packages with multiple sibling Skill roots are installed together. Keep
  their directory names and shared files so relative links/commands still resolve;
  do not choose one entry, rename it, or discard the other Skills. An entry with its
  own SKILL.md remains one merged Skill even if it contains nested components.
→ Check conflicts for every Skill and shared path. If any already exists, obtain
  confirmation for the whole replacement before adding `--overwrite`; a conflict
  must not be worked around by installing only the remaining Skills.
→ Directory publication failure rolls back the entire batch. If rollback fails,
  stop and report the preserved recovery path. Dependency failures after publication
  remain visible in deps_ok/missing_deps; do not claim the package is ready.
→ Thin Skill templates still require a single root for local instance state sync.
→ Security check and confirmation before writing; only proceeds after user agrees
→ Script outputs JSON (includes installed_to, installed_skills, installed_shared,
  deps_ok, missing_deps, env_vars_needed). installed_to is a string for one Skill
  and an array for multiple Skills. installed_skills and installed_shared contain
  the path and dependency result for each Skill and shared item; shared_paths keeps
  the shared path list. Top-level dependency and environment results aggregate both.
→ Inform user in natural language: where it was installed, whether dependencies are ready,
   which dependencies are missing, and which environment variables need to be configured
```

## Thin Skill Local State

- **First run**: if `thin_skills_state.json` does not exist, treat it as no Thin Skills installed and continue with the "no match" path — do not error. The file is created automatically by `install_package.py` after the first successful purchase; the LLM does not need to initialize it manually.
- State file: `thin_skills_state.json` in the current skill root directory
- Bucketed by `agent_id`; records template_id, default instance, instance list, etc.
- Only retains instances with `active` or `expired` status
- When an agent_id has no active/expired instances, clear that entry and the corresponding Thin Skill directory
- **On successful Run Online purchase**: run `python3 scripts/install_package.py --order-id <orderId>` — the script completes download, extraction, and state write-back in one step. **Do not have the LLM manually call thin_skill_state**, to avoid concurrent writes with install_package to the same file.
- **When install_package output shows `state_sync.synced=false`**: the Thin Skill files are installed but state was not written back (usually because the order detail or instance list API was temporarily unavailable). Use the following commands to inspect routing or explicitly clean stale state; list/get/resolve do not repair missing state, and clear deletes the local entry. After the API recovers, rerun the order installation, following the replacement confirmation above:
  - `python3 scripts/thin_skill_state.py list` — view current state
  - `python3 scripts/thin_skill_state.py get <agent_id>` — view a specific Agent's record
  - `python3 scripts/thin_skill_state.py resolve <agent_id>` — check local routing decision (reuse/local_missing)
  - `python3 scripts/thin_skill_state.py clear <agent_id>` — clean up stale data (also deletes the Thin Skill directory)
- When a message is sent successfully: `scripts/sse_stream.py` automatically calls `thin_skill_state.mark_instance_used` to update `last_used_at` and promote the default instance — the LLM does not need to intervene
