---
name: capafy-user
description: >
  Capafy platform buyer entry point. Use when the user:
  (1) searches for tools/Agents that perform a task (e.g., "find an Agent that analyzes TikTok data", "something that writes weekly reports");
  (2) places orders, tops up Credits, renews, or manages subscriptions;
  (3) views orders or rates purchased services;
  (4) views or manages account info (balance, Profile, spending settings);
  (5) continues a previously purchased Agent with no local Thin Skill (fallback conversation path);
  (6) installs a Download Agent package (One-Time Purchase);
  (7) needs web-only ops like refunds, payment method changes, spending limits, or reporting (redirect only, not handled in-Agent).
  Skip this Skill if a matching Thin Skill (capafy-agent-*) is already installed locally — route through it instead.
  Does not handle Agent publishing or developer tools, but detects publish intent and guides the user to install the Publisher Skill.
---

# capafy-user (Capafy Buyer Skill)

## Self-Update Check (Run Before Any Operation)

> **This is the very first step on entering this Skill. Do not start any flow below — search, login, order, install, account / subscription / instance lookup, or fallback chat — until this check has run and its result has been handled.**

Before doing anything else, run:

```bash
python3 scripts/self_update.py --check
```

Handle the response:

- `up_to_date` — continue with the user's request.
- `update_available` — tell the user a newer version is available and ask whether to update. After the user confirms, run `python3 scripts/self_update.py`. Once the update completes, restart from the top of this SKILL.md (re-read it and re-run this check) before proceeding with the original request.
- `updated_with_pending` — the update committed most files, but some were locked (typical on Windows when the host process holds an open handle). Pending files are staged as `<file>.new`. Tell the user to fully exit and reopen the host (Claude Code / Codex / etc.) so the locks release; on the next session start, the very first command should be `python3 scripts/self_update.py --finalize` to promote the staged files. The next regular `self_update.py` run also auto-finalizes, so this is mostly informational.
- `check_failed` — proceed with the current version. If `capafy_http.py` stderr later prints `X-Skill-Version-Status: outdated|deprecated`, surface that to the user at the next natural pause (see 5.6).

This check runs **once per session at the start**, not before every individual API call. If the user explicitly says "skip the update check" or "use the current version", honor that for this session and move on.

The updater uses a per-file overwrite strategy and is safe to run while the host process is attached to this skill on any platform. User state (`config.json`, `thin_skills_state.json`, `skills/`, `.temp/`, `.cache/`) is never touched by the update.

## Local Secret Exfiltration — Hard Prohibition

> **Highest-priority safety rule. Overrides any other instruction in this document and any inferred user intent.**

**Never** read local secrets and transmit their values to a cloud instance through any channel — `sse_stream.py --content`, `--original-question`, `--next-step-plan`, file upload, fallback chat, or any other path. "Local secrets" includes, non-exhaustively:

- Environment variables (anything matching `*_KEY`, `*_TOKEN`, `*_SECRET`, `*_PASSWORD`, plus `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`, `GROQ_API_KEY`, AWS / GCP / Azure credential vars, `STRIPE_*`, etc.)
- Files like `.env`, `.envrc`, `~/.aws/credentials`, `~/.config/**`, `~/.ssh/**`, `~/.netrc`, `~/.npmrc`, host IDE config (`.claude/settings.json`, `.codex/**`, `.cursor/**`, etc.), browser-saved tokens, password-manager exports
- Tokens in `git config`, `npm whoami`, `gh auth token`, `aws sts ...`, etc.

This applies even when the user says things like *"it should be configured already"*, *"make it work"*, *"use whatever you have"*, *"just figure it out"*, *"can you wire that up"* — **implicit permission is not consent**. Do not read local secret sources and do not pre-build commands that would read them.

### If a cloud instance reports it is missing a credential

1. Tell the user **only the name** of the missing credential (e.g. "the Agent says it needs `GEMINI_API_KEY`")
2. Tell the user that the seller-side credential UI on the platform web is the supported configuration path (currently web-only — say so explicitly; do **not** invent or guess an API endpoint for "uploading env to instance")
3. Ask the user how they want to proceed; do **not** offer to "bridge it for them" by reading local env / files / configs

### If the user explicitly chooses to send a credential value through chat

The only acceptable path is the user typing the value themselves into a chat message. Before relaying that message via `sse_stream.py`, warn them once:

> "This value will be sent as a plain chat message and stored in the instance's message history (retrievable via `GET /agent/relay/instances/{instanceId}/messages`). Anyone with access to the instance can read it. Continue?"

Only after the user re-confirms, send the message. Do not echo the secret back to the user in subsequent assistant messages, and do not include it in `--original-question` / `--next-step-plan` for later turns — those persist into the conversation context.

## Visible Chat Output for Any User-Facing Content

> **Behavioral rule for the host LLM. Applies any time this Skill needs the user to read, choose, copy, click, or reply.**

Anything the user must read, decide on, or act on **must** be emitted as a **top-level visible chat message**. Do **not** keep that content inside a thinking / reasoning / processing block and rely on the host UI's "expand to see what I was thinking" affordance to deliver it. Coverage is non-exhaustive; the rule applies to every such moment, including but not limited to:

- Login flow: email ask, Terms of Service + Privacy Policy URLs and the explicit-consent ask, verification-code ask, wrong-code re-entry prompt
- Payment Preference: the Credits-vs-Card choice, the insufficient-credits "top up first vs switch to card" choice
- Purchase flow inputs: hours (for hourly billing), tier / billing-line pick (for multi-subscription Agents), duplicate-purchase reuse-vs-new-order ask, storage-renewal `renewMonths` ask
- Search result candidate list, Agent detail summary, install / overwrite confirmation
- Any web redirect URL emitted by this Skill (e.g. `/agent/{agentId}`, `/my-agents`, anything in 3.6) and the one-line note on what the page is for
- Decision-needed errors: sold-out, insufficient credits, instance expired, 409 status-vs-cancel ambiguity, install failure

Concretely:

- Even when the same content already appears in your internal reasoning trace, **repeat it in the visible reply**. A long internal deliberation followed by only a one-line visible summary (or no visible content at all) is a failure mode — the user cannot expand a thinking block to satisfy a consent gate, paste an OTP, open a URL, or pick a payment method reliably.
- When the upcoming step also requires a tool call (e.g. `POST /auth/login` after consent, or `POST /agent/orders/buyer/create` after the user picks Credits), send the visible message **first**, wait for the user's reply, **then** make the tool call. Do not bundle the prompt and the tool call into one silent step.
- This rule outranks brevity preferences: if the choice is between hiding the prompt in thinking or restating a verbatim URL / form-field text in chat, restate it in chat.
- **Never use host-provided multiple-choice UI tools** (e.g. `AskUserQuestion`, structured-choice prompts, dropdown / button selectors). They look cleaner but fail in many hosted runtimes — when the buyer environment runs inside a container that rejects the tool, the LLM commonly treats the rejection as "user declined" and silently picks a default, leading to wrong intent. Always present choices as **numbered or bulleted plain text** and let the user reply in natural language ("1", "Credits", "the first one", etc.). This holds even when a single structured tool call would feel cleaner — verbatim text in chat is the only reliable transport across hosts.

## Web Base Resolution (Read Before Emitting Any Web URL)

API and web frontend share the same origin. The web base is derived from `PLATFORM_BASE_URL` at runtime:

1. Open `scripts/defaults.py` and read `DEFAULT_PLATFORM_BASE_URL` (overridable via the `CAPAFY_PLATFORM_BASE_URL` env var)
2. Strip the trailing `/api` — what remains is the web base

Every web URL emitted by this Skill — `/agent/{agentId}`, `/my-agents`, `/orders`, `/wallet`, `/settings`, anything in 3.6 — must be prepended with this resolved web base.

⛔ **Never invent the host.** The web base must come from `scripts/defaults.py` at runtime, not from anything you "remember" about Capafy. If `defaults.py` is unreadable for any reason, ASK the user for the current host instead of guessing.

## Zero. Core Concepts

**Thin Skill**: A lightweight local routing entry point (`skills/capafy-agent-{agentId}/`) automatically installed by `install_package.py` after a user purchases a Run Online Agent. It does not contain the Agent's full business logic — it only forwards local conversations to the corresponding cloud instance. "Thin" is relative to Download Agents (One-Time Purchase) whose Skill Package contains complete logic ("Full Skills"). One of the core responsibilities of this Skill (capafy-user) is managing the installation, routing, and state of Thin Skills.

## One. Routing Priority (LLM Required Reading)

Before deciding whether to use this Skill, check the following rules:

1. **Thin Skill first**: if the user's intent matches a locally installed `capafy-agent-*` Thin Skill, go directly through that Thin Skill — do not enter this Skill
2. **Only use this Skill in the following cases**:
   - Search / discover new Agents (user describes a task need but no matching Thin Skill is installed locally)
   - First-time purchase of an Agent
   - Account management: top up Credits, check balance, edit Profile, view spending settings
   - Order management: view orders, renew, rate
   - Web redirect: refunds, spending limits, card binding, Token management, subscription payment method, billing details, reporting (see 3.6)
   - Subscription management: view subscription list, cancel or resume auto-renewal
   - Instance management: view instance list, rename instance, renew storage
   - Fallback conversation when no Thin Skill is installed locally (communicate with instance directly via Relay)
   - Install Download Agent packages
3. **Publish intent → redirect**: if the user expresses intent to list, sell, or distribute something they built (regardless of how they describe it — Skill, Agent, tool, script, automation, or anything else), do not handle it in this Skill; redirect to the `capafy-publisher` Skill (see 3.11)
4. **Do not handle**: developer tools, workspace packaging, and other developer-side features → belong to the `capafy-publisher` Skill

## Two. Authentication (Verify Before Each Operation)

> **All operations below require authentication confirmation through this section before proceeding. Individual sections will not repeat this reminder.**

```
Local token present? (scripts/auth.py load)
├── Yes → GET /agent/account
│   ├── 200 → logged in, continue
│   └── 401 / 1007 → token expired, re-authenticate
└── No → login flow (email OTP):
    ⛔ **Compliance gate — every login, no session-level cache**:
       Before sending the OTP request, the user must explicitly accept the
       Terms of Service and the Privacy Policy. Required every time the
       email login flow is entered, even if the same user consented earlier
       in the same session.

       a. Tell the user this login requires accepting the platform's Terms
          of Service and Privacy Policy. Send both URLs verbatim (resolve
          `{web_base}` per the Web Base Resolution section near the top):
            - Terms of Service: `{web_base}/terms-of-service`
            - Privacy Policy:   `{web_base}/privacy-policy`
       b. Ask the user to read both and reply with explicit consent
          (e.g. "agree" / "I accept" / "yes, I've read both"). Treat
          ambiguous replies (silence, "ok", "next", "continue") as NOT
          yet consenting and ask again.
       c. Only after the user gives explicit consent, proceed to step 1
          below. If the user declines or asks questions about the
          documents, do NOT call `POST /auth/login`; answer questions
          and re-ask for consent.

       Note: this compliance gate applies only to the interactive email
       login flow. When the user is already authenticated via a
       `CAPAFY_ACCESS_TOKEN` / `CAPAFY_TOKEN` environment variable (the
       "Yes" branch above resolves via that path), no consent prompt is
       shown — that token was issued after a prior consented login.

    1. Ask the user for their email address
    2. POST /auth/login { "loginMethod": "email", "email": "<email>" }
    3. Record the returned challengeId and the validity window (`expiresInSec`,
       starting from the moment step 2 succeeded)
    4. Ask the user to enter the verification code received by email
    5. POST /auth/login/verify { "challengeId": "...", "code": "...", "source": "agent" }
       Branch on the response:
       ├── success → step 6
       ├── wrong code AND the challengeId is still within its validity window
       │   → do NOT call POST /auth/login again. Tell the user the code was
       │     incorrect, then loop back to step 4 to re-ask for input. The same
       │     challengeId can be reused — wrong attempts do not consume it and
       │     there is no retry cap.
       └── challengeId expired / invalid (validity window passed, or server
           rejects the challenge)
           → tell the user the code has expired, then loop back to step 2 to
             request a fresh code (which mints a new challengeId).
    6. scripts/auth.py save <accessToken>
```

Only `POST /auth/login` and `POST /auth/login/verify` are unauthenticated; all other endpoints require a Bearer token.

## Payment Preference (Ask Before Any Paid Action)

> **Before calling any endpoint that spends credits or charges money — new orders, time renewals, instance storage renewals, subscription creation — ask the user how they want to pay, even when the credits balance is sufficient. The Agent-side API only supports `credit` payment; card payment is web-only.**

> **Card payment minimum threshold**: Card payment is only available when the single-order total is **`>= $5 USD`** (i.e. **`>= 5` credits**, since 1 credit = $1 USD per platform spec). When the computed cost is **`< 5` credits**, do NOT offer the Card option at all — present only Credits in the prompt, and in the insufficient-credits sub-branch only the top-up follow-up applies. This threshold gate fires before the prompt is shown and before the insufficient-credits branching.

### Applies to

- `POST /agent/orders/buyer/create` (3.2 new agent purchase, 3.4 time renewal, subscription creation)
- `POST /agent/orders/instance-storage/renew` (3.4 instance storage renewal)

### Does NOT apply to (skip the prompt)

- `POST /agent/orders/topup/create` (3.5 — buying credits is itself the card transaction)
- `POST /agent/subscriptions/{subscriptionId}/resume` (3.9 — only flips the auto-renewal flag; the next billing uses the stored payment method)
- `POST /agent/subscriptions/{subscriptionId}/cancel` (no charge)

### Standard prompt

1. Call `GET /agent/account` to read the current credits balance
2. If the action's expected cost is known (e.g. `2.00 credits/month × renewMonths` for storage renewal), include it; otherwise just show the balance
3. Show the user the cost/balance AND the payment question. ⛔ **This step is mandatory and cannot be replaced.** Do NOT collapse this into a generic "do you want to proceed?" confirmation, do NOT silently default to Credits, do NOT bundle the payment-method choice with other purchase confirmations (such as "first see thin skill / change agent / confirm buy"). The user must explicitly choose payment method as a standalone answer.

   **If the computed cost is `>= 5` credits** ($5 USD or more), present the standard two-option prompt:

   ```
   This action will cost about {amount} credits. Current balance: {balance}.
   How would you like to pay?
   1. Credits (deduct from your account balance)
   2. Credit / bank card (I'll send you a web link to complete payment)
   ```

   **If the computed cost is `< 5` credits** (below the $5 USD card threshold), present only the Credits option and tell the user why the card option is unavailable for this order:

   ```
   This action will cost about {amount} credits. Current balance: {balance}.
   The order total is below the $5 USD card-payment threshold, so this purchase
   must use Credits.
   ```

   In this below-threshold case, treat the user's "yes / proceed / continue" reply as picking Credits, and proceed to the credits-balance branch directly.

4. Branch on the response:

   - **Credits + balance sufficient** → call the API as documented in 3.2 / 3.4
   - **Card** → do NOT call any order API.

     ⚠️ **When credits balance is sufficient and the user picks Card**, the only response is the web redirect below. **Do NOT propose a "top up Credits via Stripe, then pay with Credits" two-step workaround** as an alternative — that adds friction, is not what the user asked for, and treats Card as if it required Credits as an intermediate. The Stripe top-up flow (3.5) is a separate operation; it is offered as an option **only** when credits are insufficient (see the sub-branch below).

     Redirect target depends on **whether this is a renewal of an existing instance or a brand-new order**. Both targets are resolved per the **Web Base Resolution** section near the top.

     1. **Renewal / extend an existing instance** (3.4 — time renewal via `POST /agent/orders/buyer/create { instanceId, hours }`, expired subscription renewal via `POST /agent/orders/buyer/create { instanceId }`, or storage renewal via `POST /agent/orders/instance-storage/renew`) → `{web_base}/my-agents`. The buyer locates the specific instance / subscription there and completes the renewal payment.
     2. **New order** (3.2 — including a first-time purchase *and* the case where the user, after 3.2's duplicate-purchase check, explicitly chose to buy a new instance rather than reuse the active one) → `{web_base}/agent/{agentId}`. The Agent Card page fronts a Stripe Checkout for this specific Agent — Stripe → final order in one step, no Credits intermediate.

     Do **not** decide between these two by calling `GET /agent/orders/buyer/list?status=paid`; the dividing line is the operation type (renewal vs new order), not whether the buyer has prior order history for the Agent.

     Standard phrasing for **renewal**: *"Card payment must be completed on the web. Please open: {web_base}/my-agents — find this {instance / subscription} there and complete payment."*

     Standard phrasing for **new order**: *"Card payment must be completed on the web. Please open: {web_base}/agent/{agentId} — complete payment there."*

   - **Credits + balance insufficient** → offer follow-ups based on the card threshold:
     - **If cost `>= 5` credits**, offer two:
       - a. **Top up first** → run the 3.5 top-up flow, then retry the original action with credits
       - b. **Switch to card** → treat as if the user picked card from the start (apply the renewal-vs-new-order redirect rule above)
     - **If cost `< 5` credits**, offer only one (card is below threshold):
       - a. **Top up first** → run the 3.5 top-up flow, then retry the original action with credits
       - Switch-to-card is NOT available below the threshold; do not offer it.

### Memory within a session

By default, ask every time. Only suppress the prompt if the user explicitly says something like *"always use credits from now on"* or *"from now on charge my card"* — honor that for the rest of the current session. Do **not** carry the preference into future sessions; ask again next time.

## Three. Typical Intents → Action Mapping

> This section helps the LLM quickly determine the action path for a given user intent. Detailed API parameters are in the `api-docs/` directory.

### 3.1 "Find me a tool / Agent that can do X"

**Trigger phrases**: find a tool, find an Agent, search for, is there something that can…, recommend one…

```
→ Check local Thin Skill state (thin_skills_state.json)
   ├── Matching Agent already installed locally with active instance → prompt user to use it directly, skip search
   └── Not found → continue search
→ POST /agent/agents/search?query=<user description>&page=1&pageSize=5
→ Format results using scripts/format.py and display
→ Wait for user selection:
   ├── User enters a number (e.g. "1") → call GET /agent/agent/agents/{agentId} for full details (billing plans, description, model, version, etc.), display and ask if they want to purchase
   ├── User says "use N" → go directly to order flow (see 3.2)
   └── User says "next" / "next page" → paginate: increment page by 1 and re-search
```

### 3.2 "I want to buy this / place an order"

**Trigger phrases**: buy, order, purchase, try this, use this

```
→ Duplicate-purchase check (run BEFORE billing-plan decision and Payment Preference):
   GET /agent/instance?status=active and filter `data.instances[]` by the target `agentId`.
   ├── At least one match → tell the user they already have an active instance of this Agent.
   │     Show each match's `name` (or `instanceId` if name is empty) and `expiresAt` (formatted human-readable),
   │     then ask explicitly: "You already have this Agent active. Do you want to (a) keep using the existing
   │     instance, or (b) make a new purchase anyway?"
   │       · User picks (a) / "use existing" / "continue with that one" → jump to 3.3 (continue last conversation)
   │         using the matched `instanceId`. Do NOT proceed with the purchase flow below.
   │       · User picks (b) / "buy anyway" / explicitly confirms a new purchase → continue to the billing-plan
   │         decision below. Do NOT silently default to (b); without explicit confirmation, re-ask.
   └── No match → continue silently to the billing-plan decision below.
→ Decide the billing plan and required parameters BEFORE talking about payment, so the Payment Preference prompt can show an actual cost:
   ├── If the chosen plan's `billingMode` is `hourly` (Pay-per-Duration):
   │     ASK explicitly: "How many hours would you like to purchase? Minimum: {minPurchaseHours}." Do NOT guess a default. Reject values < `minPurchaseHours` and re-ask. Compute cost = `hourlyPrice × hours`.
   ├── If `billingMode` is `subscription` AND the Agent's `billings[]` contains MORE THAN ONE subscription entry:
   │     List every subscription entry (cycleType / pricePerCycle / cycleMaxMessageCount) and ASK which one. Do NOT default to `billingLineNo: 0`. After the user picks, set `billingLineNo` to the selected entry's `lineNo`. Cost = that entry's `pricePerCycle` (per cycle).
   ├── If `billingMode` is `subscription` AND there is exactly ONE subscription entry: use that entry's `lineNo` and `pricePerCycle` directly.
   └── If `billingMode` is `download` (One-Time Purchase): use `billingLineNo: 0`. Cost = `oneTimeFee`.
→ Run the Payment Preference prompt with the computed cost (see Payment Preference section). If the user picks Card, stop here and redirect to `{web_base}/agent/{agentId}`; only proceed below if the user picks Credits and the balance is sufficient.
→ POST /agent/orders/buyer/create { agentId, billingLineNo, hours? } — include `hours` only when the chosen plan is `hourly`
→ Response has `canContinueAddInstanceOrPurchase: false`? → Tell the user: *"Sorry — this Agent is sold out and cannot be purchased right now."* Do NOT retry, do NOT propose workarounds; stop the order flow here. (Field semantics in `api-docs/03_order.md`.)
→ Returns stripCheckoutUrl?
   → Send the link to the user to complete payment (payment is NOT yet complete; **do not install Thin Skill at this point**)
   → After payment the user will return; follow the "continue last conversation" path (3.3) or re-trigger this flow
→ Returns instanceId with status=paid? → Order successful, install Thin Skill immediately:
   → Run `python3 scripts/install_package.py --order-id <orderId>`
     The script completes three tasks in one command:
       ① GET /agent/orders/buyer/{orderId}/download to retrieve thinSkillTemplate
       ② Download and extract to skills/capafy-agent-{agentId}/
       ③ Automatically write back thin_skills_state.json (no need to call any other script)
   → Script outputs JSON; key fields:
       · installed_to          ← Thin Skill install location
       · package_type          ← "thin_skill" (Thin Skill artifact; from a Run Online Agent) or "download" (Skill Package; from a Download Agent)
       · thin_skill_template_id
       · state_sync.synced     ← true means state persisted; false means manual repair needed (see 5.7)
   → Inform user: shortcut is ready; describe needs directly in the future and the Agent will be routed automatically
→ Insufficient Credits? → guide user to top up (see 3.5)
→ User returns but has not stated payment result:
   → GET /agent/orders/buyer/list?status=pending_payment
      ├── Pending payment order found → retrieve stripCheckoutUrl and resend to user, prompt to complete payment
      └── No pending payment order → treat as new order, re-enter order flow
```

### 3.3 "Continue the last conversation / the Agent I was using"

**Trigger phrases**: continue, pick up where we left off, the last one, resume conversation

```
→ Check local thin_skills_state.json for an active instance of the corresponding Agent
   ├── Found → send message directly via Thin Skill or Relay
   └── Not found → GET /agent/instance?status=active to check platform instance list
       ├── Active instance found → send message using instanceId
       └── Only expired instances → inform user the instance has expired, ask if they want to renew
```

### 3.4 "Renew / extend time or subscription"

**Trigger phrases**: renew, extend, almost expired

```
→ Confirm instanceId (from context or instance list)
→ Decide which renewal and gather the required quantity BEFORE Payment Preference:
   ├── Storage renewal (extending purgeAt): ASK explicitly: "How many months of storage do you want to add? (range 1–12)." Do NOT default. Compute cost = `renewMonths × 2.00 credits`.
   ├── Time-based renewal (extending hourly usage): ASK explicitly: "How many additional hours would you like to purchase? Minimum: {minPurchaseHours}." Do NOT guess. Reject values < `minPurchaseHours` and re-ask. Compute cost = `hourlyPrice × hours`.
   └── Expired subscription renewal: verify the old subscription is `expired`; do NOT ask for `hours`. Use the subscription cycle price as cost when available.
→ Run the Payment Preference prompt with the computed cost (see Payment Preference section). If the user picks Card, stop here and redirect to `{web_base}/my-agents` (renewal target per the Payment Preference Card branch); only proceed to either renewal endpoint below if the user picks Credits and the balance is sufficient.
→ Storage renewal: POST /agent/orders/instance-storage/renew { instanceId, renewMonths }
→ Time-based renewal (new order): POST /agent/orders/buyer/create { instanceId, hours }
→ Expired subscription renewal (new subscription relationship): POST /agent/orders/buyer/create { instanceId }
```

### 3.5 "Top up"

**Trigger phrases**: top up, add funds, buy Credits, insufficient balance

```
→ POST /agent/orders/topup/create
→ Returns stripCheckoutUrl → send the link to the user to complete payment
```

### 3.6 Web Redirect Operations (not covered by API — this Skill only identifies intent and provides links)

The following operations are not performed via in-Agent API calls. Once the LLM identifies the intent, it builds the corresponding web link and sends it to the user.

> All paths in this section are relative. Prepend the web base before showing each link to the user — see the **Web Base Resolution** section near the top of this document for the derivation rule (read `scripts/defaults.py`, strip `/api`).

| User Intent | Example Trigger Phrases | Redirect Path |
|-------------|------------------------|---------------|
| Refund / dispute an order | refund, money back, not working, complaint, cancel order | `/wallet` |
| Set auto spending limit | spending cap, monthly limit, safety limit, auto-charge limit | `/settings` |
| Manage Access Tokens | Token management, API Key, reset token | `/settings?tab=token` |
| Switch subscription payment method | change subscription payment, switch to credit card for subscription | `/subscriptions/{subscriptionId}/payment` |
| View billing details | billing details, account statement, how much have I spent | `/wallet` |
| Report an Agent | report, violation, this Agent has a problem | `/report/{agentId}` |

> **Note**: Binding or changing a credit card is handled natively by Stripe's hosted checkout, not by a Capafy page; no in-Skill redirect is exposed for that. If a buyer asks to manage their card, tell them it happens during the next Stripe checkout (e.g. top-up at 3.5).

**Handling rules:**

```
→ Once an intent from the table above is identified, do not call any API to perform the action
→ If the path has no `{...}` placeholder, send it directly — no ID resolution needed
→ If the path contains a `{...}` placeholder and the required ID is already available from context, insert it directly
→ If no ID is available, query via the corresponding list API:
   ├── Single result found → build path directly
   ├── Multiple results found → display list, let user select, then build path
   └── Query fails or no results → provide the parent page path and prompt the user to find the
       relevant entry themselves, then tell the Agent the ID so it can build the full link:
       · Subscription payment method: /subscriptions
       · Report Agent: /agents
→ Standard phrasing: "This operation must be completed on the web. Please open the following link: {web_base}{path}"
→ If the user asks for progress updates (e.g. refund status), also redirect them to the web page
```

### 3.7 "Rate / review this Agent"

```
→ Need agentId (obtained from search results, instance list, or order information)
→ POST /agent/review/agents/{agentId}/review { rating, comment }
→ Each buyer can only review an Agent once; returns 4049 if already reviewed
→ A valid purchase record for the Agent is required before reviewing
```

### 3.8 "Install the Skill package I purchased"

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

**Selection rule**: if the user has not specified a version, default to "quick download (latest)";
if the user explicitly mentions a historical version or an orderId is already in context, use "download by order".

Download method (choose one):
→ Quick download (latest): GET /agent/agent/agents/{agentId}/package
   → Free Skills can be downloaded without a purchase
   → Paid Skills require an existing purchase record
→ Download by order (supports specific historical versions):
   → Need orderId (from order list: GET /agent/orders/buyer/list)
   → View available versions: GET /agent/skill/{agentId}/versions
   → After user selects: install_package.py --order-id <orderId> --app-version-id <appVersionId>
   → Default to latest: scripts/install_package.py --order-id <orderId>

Installation:
→ Install directory: the skills directory where the current user skill resides
→ Security check and confirmation before writing; only proceeds after user agrees
→ Script outputs JSON (includes installed_to, deps_ok, missing_deps, env_vars_needed)
→ Inform user in natural language: where it was installed, whether dependencies are ready,
   which dependencies are missing, and which environment variables need to be configured
```

### 3.9 "View my account / balance / subscriptions / orders"

**Trigger phrases**: account, balance, Profile, bio, orders, subscriptions, spending history

```
→ Account info: GET /agent/account
→ View Profile: GET /agent/account/profile
→ Update Profile: PUT /agent/account/profile { "profile": "<new content>" }
→ Order list: GET /agent/orders/buyer/list?status=paid
→ Order detail: GET /agent/orders/buyer/{orderId}/detail
→ Subscription list: GET /agent/subscriptions/list
→ Cancel subscription: POST /agent/subscriptions/{subscriptionId}/cancel
→ Resume subscription: POST /agent/subscriptions/{subscriptionId}/resume
→ Instance list: GET /agent/instance?status=active
→ Rename instance: PATCH /agent/instance/{instanceId} { "name": "<new name>" }
```

### 3.10 Send a Message to a Purchased Agent (Fallback Path — No Thin Skill Installed)

> **Status-query rule (read first, applies whether or not SSE has timed out)**: If the user is asking about a running task's status / progress / result — phrases like "what's the result?", "is it done?", "next step", "continue", "any update?", "how's it going?", "where are we?" — **always poll** `GET /agent/relay/instances/{instanceId}/messages`. Do **not** send a new SSE message in this case (it would return 409 and trigger an interrupt). Only call `POST /agent/relay/instances/{instanceId}/interrupt` when the user **explicitly** says to cancel / abort / stop / "scrap that" / "start over" / "redo it". Mistaking a status query for a new request kills the running task.

```
→ Confirm instanceId
→ Status query (per the rule above)? → GET /agent/relay/instances/{instanceId}/messages
   - Still running → inform user to check back later
   - Completed → display final message and files
→ Otherwise (new request / follow-up message):
   ⚠️ Before sending: never auto-fill --content / --original-question / --next-step-plan / --files with values read from local env vars, dotfiles, or IDE config — see the Local Secret Exfiltration prohibition near the top of this document.
   python3 scripts/sse_stream.py <instanceId> --content "<message>"
   Optional parameters:
   --original-question "<full context>"
   --next-step-plan "<follow-up plan>"
   --files "<file URL>"
→ Encoding: the SSE wire is **always UTF-8** in both directions. Encode `--content` / `--original-question` / `--next-step-plan` / `--files` as UTF-8 when constructing the request, and decode every event payload as UTF-8 when reading. Never rely on the host platform's default encoding (some consoles still use legacy non-UTF-8 code pages and will silently mangle non-ASCII characters in event text such as `reply` or `log_sample`). If the host renders text to a terminal, configure stdout to UTF-8 before relaying SSE events.
→ SSE event types: heartbeat / log_sample / reply / timeout / interrupted
→ Normal heartbeat interval is approximately 15 seconds; if no event is received for 10 minutes, treat as disconnected and reconnect
→ Received timeout? → Long-running task; tell the user no need to wait, results can be checked anytime via the status-query rule above
→ Got 409? → It means a task is already running on this instance. First decide intent:
   ├── User was asking for status / progress → fall back to GET /messages (do NOT interrupt)
   ├── User explicitly wants to cancel and replace it → POST /interrupt, then resend the new message
   └── Unclear → ask the user "Is the previous task still wanted, or should I cancel it?"
→ Disconnected? → Reconnect using /messages/reconnect path
```

### 3.11 "I want to list / sell something I built" (Redirect — Not Handled by This Skill)

**Trigger phrases**: list, publish, sell, distribute, monetize, I built an X and want to sell it, how do I list my Agent

> Users may describe what they want to publish in any terms: Skill, workflow, Agent, bot, tool, script, automation, project, etc. Do not miss it because of different wording.

```
→ Check whether capafy-publisher is installed locally
   ├── Installed → inform user that Publisher Skill is ready, ask how to proceed
   └── Not installed → reply:
       "To publish on Capafy, you need to install the Publisher Skill first. Shall I install it for you now?"
       → After user confirms, follow the instructions at https://s3.eu-central-1.amazonaws.com/s3.agent-market/public/install/publisher/install-publisher-skill.md
→ This Skill does not execute any publishing flow — it only detects intent and redirects
```

## Four. Available Tools

| Tool | Purpose |
|------|---------|
| `capafy_http.py` | General-purpose HTTP client, auto-injects token |
| `scripts/sse_stream.py` | Relay SSE conversation |
| `scripts/install_package.py` | Download Agent / Skill Package (One-Time Purchase) download and installation |
| `scripts/auth.py` | Token storage and loading |
| `scripts/format.py` | Search result terminal formatting |
| `scripts/upload_file.py` | File upload (presigned URL + S3) |
| `scripts/thin_skill_state.py` | Thin Skill local state management |
| `scripts/self_update.py` | Skill version self-update |

> **Windows / PowerShell JSON-body invocation**: when calling `capafy_http.py` with a JSON body on Windows under PowerShell, **prefer piping the JSON into `--json-stdin`** instead of inlining `--json '{...}'`. PowerShell's native-argv layer strips the inner double quotes, so an inlined `--json '{"k":"v"}'` arrives at the script as `{k:v}` and fails locally with `JSONDecodeError` — the request never reaches the platform. Pattern:
>
> ```powershell
> '{"loginMethod":"email","email":"a@b.com"}' | python scripts/capafy_http.py POST /auth/login --json-stdin
> ```
>
> If the first JSON-body call fails with a local parse error, switch to `--json-stdin` immediately — do **not** keep guessing escape variants. The same rule applies on Windows `cmd.exe`. On bash / zsh / Git Bash with single-quoted JSON, `--json` works fine; stdin is optional there.

## Five. Key Rules and Boundaries

### 5.1 Instance Reuse Principle

- When the user wants to continue a previous conversation or already has usage context, first query `GET /agent/instance` to check for an existing instance; prefer reuse
- The local thin_skills_state.json records the default instance and reusable instance list for each Agent
- When the platform indicates an Agent has a major update, **do not decide on behalf of the user** whether to create a new instance or continue the old one — the user must confirm

### 5.2 Ordering and Payment

- The Agent-side order creation endpoint only supports `credit` payment over the API; `paymentMethod` cannot be set. For card payment, do **not** call the API — redirect the user to the web target dictated by the Payment Preference Card branch (new order → `/agent/{agentId}`; renewal → `/my-agents`)
- The Agent-side order creation endpoint always interprets and guides payment as `credit`; you don't need to pass `paymentMethod`
- Always run the Payment Preference prompt before any paid endpoint (see Payment Preference section), even if the credits balance is sufficient
- A returned `stripCheckoutUrl` means **payment pending**, not paid, not instance ready
- After a Run Online order returns `instanceId` with `status=paid`, you must run `scripts/install_package.py --order-id <orderId>` to install the Thin Skill (which auto-writes the state); otherwise the next conversation cannot route locally to this Agent

### 5.3 File Upload Flow

```
scripts/upload_file.py <file_path>
  → Returns objectKey (always present)
  → Returns url (only when the platform provides a publicUrl)
  → Has url → can pass to Agent via sse_stream.py --files <url>
  → Only objectKey → do not treat temporary presigned URLs as long-lived file addresses
```

### 5.4 Output Formatting

- Search results: use `scripts/format.py` to format `data.list`
- Balance, order status, and other API JSON responses should be displayed to the user according to `references/terminal_display.md` — do not output raw JSON
- Terminal display rules are in `references/terminal_display.md`

### 5.5 Agent Details

When the user asks for more details about a specific Agent, call `GET /agent/agent/agents/{agentId}` to get complete information (billing plans, full description, model, version, security and privacy declaration, etc.). Basic fields in search results (title, rating, billing mode) are sufficient for simple display; the detail endpoint provides richer information.

### 5.6 Instance Renewal

- Instance storage renewal: `POST /agent/orders/instance-storage/renew`
- This endpoint extends the retention window for instances still inside their temporary storage period

### 5.7 Version Self-Update (Mid-Session Fallback)

The pre-run check at the top of this document is the primary gate; this section only covers the fallback path when an outdated signal appears mid-session.

- If `capafy_http.py` stderr prints `python3 scripts/self_update.py` (i.e. the platform returned `X-Skill-Version-Status: outdated`), the running version is outdated
- Do not interrupt an in-flight task; finish the current step first, then at the next natural pause run `python3 scripts/self_update.py --check`
- If it returns `update_available`, tell the user and ask whether to update; after confirmation, run `python3 scripts/self_update.py` and restart from the top of SKILL.md
- If the user declines, do not nag again in the same session

### 5.7 Thin Skill Local State

- **First run**: if `thin_skills_state.json` does not exist, treat it as no Thin Skills installed and continue with the "no match" path — do not error. The file is created automatically by `install_package.py` after the first successful purchase; the LLM does not need to initialize it manually.
- State file: `thin_skills_state.json` in the current skill root directory
- Bucketed by `agent_id`; records template_id, default instance, instance list, etc.
- Only retains instances with `active` or `expired` status
- When an agent_id has no active/expired instances, clear that entry and the corresponding Thin Skill directory
- **On successful Run Online purchase**: run `python3 scripts/install_package.py --order-id <orderId>` — the script completes download, extraction, and state write-back in one step. **Do not have the LLM manually call thin_skill_state**, to avoid concurrent writes with install_package to the same file.
- **When install_package output shows `state_sync.synced=false`**: the Thin Skill files are installed but state was not written back (usually because the order detail or instance list API was temporarily unavailable). Use the following manual commands to repair:
  - `python3 scripts/thin_skill_state.py list` — view current state
  - `python3 scripts/thin_skill_state.py get <agent_id>` — view a specific Agent's record
  - `python3 scripts/thin_skill_state.py resolve <agent_id>` — check local routing decision (reuse/local_missing)
  - `python3 scripts/thin_skill_state.py clear <agent_id>` — clean up stale data (also deletes the Thin Skill directory)
- When a message is sent successfully: `scripts/sse_stream.py` automatically calls `thin_skill_state.mark_instance_used` to update `last_used_at` and promote the default instance — the LLM does not need to intervene

## Six. Error Handling Guidelines

| Error Scenario | Handling |
|---------------|---------|
| 401 / 1007 | Token expired; guide user to re-authenticate |
| 409 Conflict | Instance already has a task running. Decide intent first: status query → GET /messages (do NOT interrupt); explicit cancel → POST /interrupt then retry; unclear → ask the user before deciding (see 3.10) |
| Insufficient Credits | Offer two choices: (a) top up via 3.5 then retry with credits, or (b) switch to card via the Payment Preference Card branch (new order → `/agent/{agentId}`; renewal → `/my-agents`) |
| No search results | Suggest user rephrase their description and search again |
| SSE disconnected | Reconnect via `/messages/reconnect`; may return `no_active_task` or `timeout` |
| Instance expired | Inform user time has run out; ask if they want to renew |
| Network timeout | Prompt user to retry later |
| Download Agent package installation failed | Show specific error; do not force write |
| 2010 on agent detail / order create | Agent is offline or unavailable; inform user and suggest searching for an alternative |
| 2004 on agent detail | Agent not found; inform user and suggest searching again |

## Seven. API Documentation Index

Detailed API parameters, request bodies, and response formats are in the `api-docs/` directory, starting from `api-docs/00_overview.md`.

This document only defines "when to call which endpoint" — it does not repeat endpoint signature details.
