<div align="center">


# Capafy

**The marketplace where your Skills earn for you — and where you use other Skills built by real industry experts.**

💻 [Website](https://capafy.ai) · 🚀 [Quickstart](#quickstart) · 📤 [Publish & Earn](#publish--earn) · 📥 [Use a Skill](#use-a-skill) · ❓ [FAQ](#faq--troubleshooting)

![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-launch-brightgreen)
![Agent client](https://img.shields.io/badge/agent%20client-Claude%20Code%20%7C%20Codex%20%7C%20OpenClaw-blue)

<img width="1672" height="941" alt="hero" src="https://github.com/user-attachments/assets/b17f6d96-5c30-4dcc-b652-2e145ecedd19" />


</div>

---

## What is Capafy

**Capafy is a marketplace for Skill-based Agents.** On Capafy, a Skill runs as an Agent — it puts the Skill's ability to work as a service. The user uses what the Skill *does* — make a viral video, screen a resume, write a cold email — without ever holding the Skill itself.

If you've built a Skill in Claude Code, Codex, or OpenClaw — a tool that solves one specific problem — you can publish it on Capafy and earn every time someone runs it. Your Skill runs online and stays closed-source: users can run it directly and receive the output, without dealing with the files, code, or internal logic.

You can reach Capafy two ways: through the website, or from inside your agent client (Claude Code, Codex, or OpenClaw). Either way, you can publish your Skills, and browse, buy, and run Skills built by others.

---

## The two Skills in this repo

Capafy works through two Skills you install into your agent client. Install the one that fits what you're here to do — or both.

- 📤 **Capafy-Publisher** — for publishing. Point it at a Skill you've built; it packages it, helps you set a price, takes it through review, and lists it on Capafy.
- 📥 **Capafy-User** — for using. It searches Capafy for Skills built by others, and lets you buy and run the ones you need — right inside your normal chat.

---

## Why Capafy

**Generic AI can do anything — but it stops at average.**
It can make videos, write resumes, build decks, draft emails, analyze contracts, and plan campaigns. But the video that actually goes viral, the deck that closes the room, the resume that gets the callback — those take real industry know-how.

**Know-how makes Skills worth paying for — but not protected enough to publish.**
People build Skills like this every day in Claude Code, Codex, or OpenClaw. But in today's open-source Skill ecosystems, anything you publish can be forked or copied, leaving creators with no reliable way to get paid or protect their proprietary know-how and IP. So the best Skills usually stay private.

**Capafy fixes this: a Skill can run closed-source, online.**
The people who built the Skills can finally share them without giving them away, earn from every run — and users can access expert-level Skills.

---

## Publish & Earn

If you work in Claude Code, Codex, or OpenClaw, you've probably built a Skill or two — something that handles one specific job far better than a generic assistant does. Right now, it only works for you.

**On Capafy, you publish it once — and from then on, every person who runs it pays you.** While you sleep, while you're at your day job, while you're building the next one — the Skill you made keeps working for you.

**Your know-how stays yours.** Your Skill runs closed-source online — anyone who uses it gets the output, never the files, the code, or the logic inside. You're sharing what your Skill *does*, not giving away how it works.

**To publish:** point `capafy-publisher` at your workspace. It finds publishable Skills — each one a directory with a `SKILL.md`, scripts, references, and config — and shows them to you. You pick what to publish, set your price, and choose how users can run it.

**Two ways to get paid:**
- **Run Online** — your Skill runs on Capafy's infrastructure. Users pay per hour, or per subscription cycle.
- **Download** — users pay once and run it on their own machine. Note: in this mode the user gets the actual Skill files — your code, your prompts, your logic, your know-how are all visible to them. Choose Download only for Skills whose value doesn't depend on staying closed.

Hosting, credential safety, user instances, payments — Capafy handles all of it.

---

## Use a Skill

A generic AI assistant gives you the average output — it's built for everyone, so it's sharpened for no one in particular.

The Skills on Capafy are built by real industry experts — across every field and industry. For example:

- a creator behind **100M+ views** publishes the Skill they use to make videos go viral
- a recruiter who has screened **thousands of resumes** publishes the Skill they use to spot what lands the callback
- a salesperson who has closed **thousands of deals** publishes the Skill they use to write cold emails that actually get replies

— and the same goes for designers, lawyers, analysts, marketers, engineers, and every other kind of expert.

Pick any Skill on Capafy that fits your task. **Two ways to use it:**
- **Run it directly on Capafy** — one click, no install needed.
- **Connect your own agent** — agent-to-agent — and let it reach any expert Skill on the marketplace through it.

---

## Sale Modes

| Mode | User Pays | Where It Runs | Source Code |
|------|-----------|--------------|-------------|
| **Run Online — Subscription** | Per cycle (monthly / yearly) | On Capafy's infrastructure | Stays closed |
| **Run Online — Hourly** | Per hour of usage | On Capafy's infrastructure | Stays closed |
| **Download** | One-time fee | On the user's machine | User gets the files |
| **Free** | — | Mirrors whichever paid form it's set as | Same as that form |

Both modes use the same publishing flow. You pick the mode during review, right after `publish-init`.

---

## Quickstart

### What you need

- One of: **Claude Code**, **Codex**, or **OpenClaw**
- **Python 3.8+**
- A Capafy account — sign up at <https://capafy.ai>

### Install

In your agent client's chat, send:

```
install https://capafy.ai/install-publisher-skill.md
install https://capafy.ai/install-user-skill.md
```

Install the Publisher Skill to publish, the User Skill to use others' Skills, or both.

### Verify

Ask your agent client to "list the capafy skills" — you should see `capafy-publisher` and/or `capafy-user`. The first time you use either one, it updates itself and asks you to log in.

---

## Using Capafy-Publisher

Four commands, three web checkpoints. The publisher prints the URL to open, what each page does, and waits for you to come back.

```text
   ┌──────────────────────────────────────┐
   │  install + log in                     │
   └──────────────────┬───────────────────┘
                      ▼
   ┌──────────────────────────────────────┐
   │  publish-init                         │
   │  scan workspace → list Skill          │
   │  candidates                           │
   └──────────────────┬───────────────────┘
                      ▼
   ╔══════════════════════════════════════╗
   ║  Web Checkpoint 1                    ║
   ║  confirm files · pick mode           ║
   ╚══════════════════╤═══════════════════╝
                      ▼
   ┌──────────────────────────────────────┐
   │  publish-configure                    │
   │  scan secrets · stage bundle          │
   │  (--deep-scan optional)               │
   └──────────────────┬───────────────────┘
            ┌─────────┴─────────┐
            ▼                   ▼
   ┌────────────────┐   ┌────────────────┐
   │  Run Online    │   │  Download      │
   │  needs Web 2   │   │  skips Web 2   │
   └────────┬───────┘   └────────┬───────┘
            ▼                    │
   ╔══════════════════╗          │
   ║ Web Checkpoint 2 ║          │
   ║ map credentials  ║          │
   ╚════════╤═════════╝          │
            ▼                    │
            └──────────┬─────────┘
                       ▼
   ┌──────────────────────────────────────┐
   │  publish-ship                         │
   │  validate · package · upload          │
   └──────────────────┬───────────────────┘
                      ▼
   ╔══════════════════════════════════════╗
   ║  Web Checkpoint 3                    ║
   ║  final audit · click Submit          ║
   ╚══════════════════╤═══════════════════╝
                      ▼
                  ✓ Listed
```

**Step 1 — Log in.** Just say "log into Capafy". The skill emails you a code and saves the token locally.

**Step 2 — Describe what to publish.** Say something like *"publish the research-agent skill in this project as a Run Online Agent"*. The publisher scans your workspace, lists candidate Skills, and asks you to confirm title, description, and purpose for each.

**Step 3 — Pick the mode on the web.** The skill prints a `review_url`. Open it, confirm the file list, pick **Run Online** or **Download**, then come back. Each `review_url` expires in 1 hour — if it lapses, re-run the command and the skill issues a fresh URL pointing at the same draft.

**Step 4 — Credentials & ship.** The skill scans for credential information and stages them as platform-hosted placeholders, then prints another `review_url` for credential mapping. Run `publish-ship` and click submit on the final web page. Done.

> Run Online publishers can opt into **deep scan** (`--deep-scan`) for a slower but more thorough credential sweep. Recommended for the first version of any Agent that handles user data.

---

## Using Capafy-User

```text
   ┌──────────────────────────────────────┐
   │  install + log in                     │
   └──────────────────┬───────────────────┘
                      ▼
   ┌──────────────────────────────────────┐
   │  search the catalog                   │
   │  "find an Agent that does X"          │
   └──────────────────┬───────────────────┘
                      ▼
   ┌──────────────────────────────────────┐
   │  order                                │
   │  confirm billing plan + cost          │
   └──────────────────┬───────────────────┘
            ┌─────────┴─────────┐
            ▼                   ▼
   ┌────────────────┐   ┌────────────────┐
   │  Credits       │   │  Card          │
   │  in-client     │   │  Stripe (web)  │
   └────────┬───────┘   └────────┬───────┘
            └──────────┬─────────┘
                       ▼
   ┌──────────────────────────────────────┐
   │  install_package.py                   │
   └──────────────────┬───────────────────┘
            ┌─────────┴─────────┐
            ▼                   ▼
   ┌────────────────┐   ┌────────────────┐
   │  Run Online    │   │  Download      │
   │  Thin Skill    │   │  Full Skill    │
   │  routes to     │   │  runs on your  │
   │  cloud instance│   │  machine       │
   └────────┬───────┘   └────────┬───────┘
            └──────────┬─────────┘
                       ▼
   ┌──────────────────────────────────────┐
   │  use                                  │
   │  describe a task in client chat       │
   │  → routed automatically               │
   └──────────────────┬───────────────────┘
                      ▼
   ┌──────────────────────────────────────┐
   │  resume · renew · top up              │
   └──────────────────────────────────────┘
```

**Search** — *"find an Agent that summarizes PDFs"* hits the catalog and returns matches.

**Buy** — pick one and say *"order this"*. The skill confirms billing plan and asks how you want to pay (credits or card), then either deducts credits or sends you a Stripe link.

**Use** — for Run Online Agents, a **Thin Skill** is installed locally — just a router. The next time you describe a similar task, your agent client routes the conversation to that Agent automatically. For Download Agents, the full Skill package is installed and runs on your machine.

**Resume** — *"continue the agent I was using"* picks up the active instance and replays the message stream.

---

## Supported Agent Clients

| Agent Client | Notes |
|--------------|-------|
| Claude Code | `--runtime-dir` is the project root you opened with `claude` |
| Codex | `--runtime-dir` is the project root you opened with `codex` |
| OpenClaw | `--runtime-dir` must be a real OpenClaw workspace path (e.g. `/home/me/.openclaw/workspace_xxx`), not `~/.openclaw` |


---

## FAQ / Troubleshooting

<details>
<summary><b>Q1: The publisher says my <code>review_url</code> expired.</b></summary>

`review_url` is valid for 1 hour. Don't reopen an old one — re-run the same command (`publish-init`, `publish-configure`, or `publish-ship`) with the same `--agent-id` and the skill prints a fresh URL pointing at the same draft. No data is lost.
</details>

<details>
<summary><b>Q2: <code>publish-init</code> fails with <code>existing_local_publish_state</code>.</b></summary>

This is a guardrail, not an error. The skill has unfinished local state from a previous session. Run `publish-status` to see where you stopped, then continue with `publish-configure` or `publish-ship` — usually no need to start over. Only pass `--reset-local-state` if you genuinely want to abandon the local draft (it does **not** delete the Agent on the platform).
</details>

<details>
<summary><b>Q3: I changed the mode on the web (Run Online ↔ Download). Now the publisher complains.</b></summary>

The platform clears the previous version's confirmed skills when the mode changes. Re-run `publish-init` — the publisher will re-discover candidates and stage everything fresh under the new mode. Keep your existing Agent ID; you're not creating a new one.
</details>

<details>
<summary><b>Q4: <code>capafy-user</code> says "Insufficient Credits" but I want to use my card.</b></summary>

The in-client API only supports credits. For card payment, the skill redirects you to <https://capafy.ai/my-agents> (for renewals or repeat purchases) or `https://capafy.ai/agent/{agentId}` (for first-time purchases). Pay on the web; the Agent unlocks immediately after.
</details>

<details>
<summary><b>Q5: I bought an Agent but the agent client doesn't route to it automatically.</b></summary>

The Thin Skill may not have installed. From the `capafy-user/` directory, run `python3 scripts/thin_skill_state.py list`. If the Agent isn't there but the order is paid, run `python3 scripts/install_package.py --order-id <orderId>` manually — usually a transient API hiccup caused the auto-install to skip state write-back.
</details>

<details>
<summary><b>Q6: The publisher is reading the wrong directory as my project.</b></summary>

`--runtime-dir` must be the absolute path your agent client opened the project at. The publisher does **not** infer it from the location of the Skill source or the publisher itself. For OpenClaw, it must be a real workspace path (e.g. `/home/me/.openclaw/workspace_xxx`), not `~/.openclaw` or a Skill directory.
</details>

<details>
<summary><b>Q7: I'm asking about audit status but the publisher keeps saying "draft".</b></summary>

`publish-ship` returning `shipped` only means the bundle uploaded. You still have to click **Submit** on the last `review_url`. After that, audit status is queryable via the platform. `status: 0` and `auditStatus: 0` both literally mean **draft / not yet submitted** — not "in review".
</details>

---

## Best Practices

### 📤 For Publishers

- **Run deep scan on first publish.** Slower, but catches credentials the regex scanner misses. Skip it on incremental updates.
- **One `--skill-dir` per Agent.** Bundling unrelated Skills into one Agent makes credential review harder and confuses users. Publish them as separate Agents.
- **Write `purpose` for the user, not for yourself.** Each Skill's `purpose` shows up on the listing. *"Reads a PDF and returns an executive summary in 5 bullets"* beats *"PDF processing skill"*.
- **Don't put secrets in the source.** Even with deep scan, removing leaked credentials adds round trips. Use environment variables.
- **Match price to usage shape.** Hourly Agents earn most when work-per-user is bounded; subscription Agents earn most when usage is steady. Mismatched pricing leaves money on the table.
- **Treat `--reset-local-state` as a last resort.** It clears local staging only — it does not abandon the platform Agent. Most "stuck" cases are solved by `publish-status` followed by resuming `publish-configure` / `publish-ship`.

### 📥 For Users

- **Reuse instances.** A new Run Online instance has its own storage and history. Resuming an existing one is cheaper and keeps context.
- **Renew storage before purge.** Storage purge is irreversible. Renew in 1–12 month chunks at 2 credits/month.
- **Be cautious when sending secrets.** If your work genuinely needs you to send sensitive credentials to an Agent, do it deliberately and stay aware of the security risk — chat messages persist in the instance log and can be read by anyone with access to it.

---

## Resources

- **Website**: <https://capafy.ai>
- **Publisher Skill source**: [`capafy-publisher/`](capafy-publisher/)
- **User Skill source**: [`capafy-user/`](capafy-user/)
- **Publisher install URL**: `https://capafy.ai/install-publisher-skill.md`
- **User install URL**: `https://capafy.ai/install-user-skill.md`

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=capafy-ai/market-skill&type=Date)](https://star-history.com/#capafy-ai/market-skill&Date)

---

## License

MIT

---

<div align="center">
Built for creators and operators who want their tools to show up where the work already happens. · <a href="https://capafy.ai">capafy.ai</a>
</div>
