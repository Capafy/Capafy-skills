# AGENTS.md

Guidance for AI coding agents (Claude Code, Codex, OpenClaw, Cursor, Copilot, and others) working in this repository or helping a user adopt Capafy.

## What this repo is

This is the official repository for **Capafy** — an agent skills marketplace for Claude Code, Codex, and OpenClaw. Domain experts package their know-how into Skills; users discover, buy, and run them, either directly on https://capafy.ai or from inside their own agent client.

The repo distributes Capafy's two official Skills:

- `capafy-user/` — install this to **use** Skills built by others: search the marketplace, buy, and run Agents from inside your normal chat.
- `capafy-publisher/` — install this to **publish** a Skill you built and earn when others run it.

`README.md` is the full human-facing documentation. `LICENSE` is MIT.

## Requirements

- One of: **Claude Code**, **Codex**, or **OpenClaw**
- **Python 3.8+**
- A Capafy account (sign up at https://capafy.ai)

## How to install the Skills

In the agent client's chat, send either or both:

```
install https://capafy.ai/install-user-skill.md
install https://capafy.ai/install-publisher-skill.md
```

Verify the install by asking the client to `list the capafy skills` — you should see `capafy-user` and/or `capafy-publisher`. The first time either Skill is used, it updates itself and asks the user to log in.

## Authentication

Login happens through the agent client: the user says `log into Capafy`, Capafy emails a one-time code, and the Skill saves a token locally for later runs. The same account works as both user and publisher.

## Using capafy-user

Search the catalog (e.g. "find an Agent that summarizes PDFs"), order an Agent (confirm the billing plan; pay with in-client credits or by card via Stripe on the web), then describe a task and let the client route it. For **Run Online** Agents, a lightweight Thin Skill router is installed locally; for **Download** Agents, the full package installs and runs on the user's machine.

## Using capafy-publisher

Point it at a Skill you've built. The flow runs through a few commands with web checkpoints in between:

```
publish-init        # scan workspace, list Skill candidates
publish-configure   # scan for secrets, stage the bundle (add --deep-scan for a thorough sweep)
publish-ship        # validate, package, upload
publish-status      # check where a draft stopped
```

Each command prints a `review_url` to open in the browser; a `review_url` expires after 1 hour (re-run the same command with the same `--agent-id` for a fresh one). `publish-ship` returning `shipped` only means the bundle uploaded — the user must still click **Submit** on the final web page for it to enter review.

## Conventions for agents working in this repo

- The language is **Python** (100% of the repo). Target Python 3.8+.
- A publishable Skill is a directory containing a `SKILL.md` plus optional scripts, references, and config.
- Never commit secrets to Skill source — use environment variables. For Run Online Skills, the publisher stages credentials as platform-hosted placeholders rather than shipping them.
- `--runtime-dir` must be the absolute path the agent client opened the project at; it is not inferred. For OpenClaw it must be a real workspace path (e.g. `/home/me/.openclaw/workspace_xxx`), not `~/.openclaw`.

## Key links

- Website: https://capafy.ai
- Marketplace: https://capafy.ai/search
- Publisher Guide: https://capafy.ai/developer/doc
- Become a Publisher: https://capafy.ai/earn
- Help Center: https://capafy.ai/help-center
- User install URL: https://capafy.ai/install-user-skill.md
- Publisher install URL: https://capafy.ai/install-publisher-skill.md
