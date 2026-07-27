# Hermes 0.16 Publish Compatibility

## Context

Hermes 0.16 keeps the Capafy publish flow shape unchanged:

1. Confirm files.
2. Confirm hosted configuration and credentials.
3. Ship and complete the final review page.

Most 0.16 additions are runtime or gateway features. They do not change which skill files should be packaged from `.hermes/skills`.

## Publishing Policy

- Package skill source from `.hermes/skills` and the hosted runtime config files already declared by the Hermes profile.
- Keep local runtime state out of the package. This includes sessions, logs, memories, cron output, pairing approvals, and MCP OAuth token caches.
- Treat `config.yaml` and `.env` as hosted configuration surfaces. Values needed by the cloud runtime must be confirmed on the configure page, not silently bundled as local secrets.

## 0.16 Feature Impact

- Background delegation is an agent runtime behavior and does not add publish inputs.
- Dashboard/profile management still relies on `HERMES_HOME` and `active_profile`; the publisher already resolves the active Hermes home.
- Gateway relay can store `gateway.relay_secret` and `gateway.relay_delivery_key` in `config.yaml`, or `GATEWAY_RELAY_*` in `.env`.
- Dynamic webhook subscriptions store HMAC secrets in runtime state and are not skill package content. Static webhook secrets in `config.yaml` are hosted config values.
- MCP OAuth tokens live under `mcp-tokens/`; they are local auth state and are not packaged.
- Hermes cron jobs live under `cron/jobs.json`; they are runtime automations, not Capafy skill units. Cron recipes also do not change skill packaging.

## Scanner Requirement

Hermes provider fields in `.hermes/config.yaml` are owned by the Hermes runtime provider scanner, so generic structured scanning remains disabled for provider trees to avoid duplicate confirmation entries.

Non-provider secrets in the same file still need hosted configuration review. The Hermes target therefore adds a narrow config scan hint for non-provider branches, including relay and webhook secrets, while leaving provider URL proxy behavior unchanged.
