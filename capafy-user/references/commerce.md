# Discovery, purchase and renewal

Read for search, purchase or renewal. Protected calls require [authentication](authentication.md); before charging read [payment](payment.md), and before installation read [installation](installation.md).

Commands and script paths below are relative to the installed Skill root, not this references directory. API signatures (read only the module needed): [search](../api-docs/02_search.md), [order](../api-docs/03_order.md), [instance](../api-docs/05_instance.md).

## "Find me a tool / Agent that can do X"

**Trigger phrases**: find a tool, find an Agent, search for, is there something that can…, recommend one…

```
→ Check local Thin Skill state (thin_skills_state.json)
   ├── Matching Agent already installed locally with active instance → prompt user to use it directly, skip search
   └── Not found → continue search (guest access is allowed; use --no-auth when not logged in)
→ POST /agent/agents/search with JSON body:
  { "query": "<user description>", "page": 1, "pageSize": 5 }
  query must contain the user requirement. Send all search fields in the JSON body. minPrice and maxPrice work independently; pageSize defaults to 5 (valid range 1–100). No total/hasMore is returned.
→ When a purchase quote is needed, POST /public/agents/subscription/prices { agentIds: [agentId], callScene: "NORMAL" } via capafy_http.py --no-auth. Do not send the Agent Access Token or read browser credentials. Check each data[] item success, then read its singular billing[] and full agentCardBillingId; quote lookup creates no order.
→ Format results using scripts/format.py and display
→ Wait for user selection:
   ├── User enters a number (e.g. "1") → call GET /agent/agent/agents/{agentId} for full details (billing plans, description, model, version, etc.), display and ask if they want to purchase
   ├── User says "use N" → go directly to order flow (see purchase in commerce.md)
   └── User says "next" / "next page" → paginate: increment page by 1 and re-search
```

## "I want to buy this / place an order"

**Trigger phrases**: buy, order, purchase, try this, use this

```
→ Duplicate-purchase check (run BEFORE billing-plan decision and Payment Preference):
   GET /agent/instance?status=active and filter `data.instances[]` by the target `agentId`.
   ├── At least one match → tell the user they already have an active instance of this Agent.
   │     Show each match's `name` (or `instanceId` if name is empty) and `expiresAt` (formatted human-readable),
   │     then ask explicitly: "You already have this Agent active. Do you want to (a) keep using the existing
   │     instance, or (b) make a new purchase anyway?"
   │       · User picks (a) / "use existing" / "continue with that one" → jump to instance reuse in messaging.md (continue last conversation)
   │         using the matched `instanceId`. Do NOT proceed with the purchase flow below.
   │       · User picks (b) / "buy anyway" / explicitly confirms a new purchase → continue to the billing-plan
   │         decision below. Do NOT silently default to (b); without explicit confirmation, re-ask.
   └── No match → continue silently to the billing-plan decision below.
→ Decide the billing plan and required parameters BEFORE talking about payment, so the Payment Preference prompt can show an actual cost:
   ├── If the chosen plan's `billingMode` is `hourly` (Pay-per-Duration):
   │     Retain the selected entry's complete `agentCardBillingId`. ASK explicitly: "How many hours would you like to purchase? Minimum: {minPurchaseHours}." Do NOT guess a default. Reject values < `minPurchaseHours` and re-ask. Compute cost = `hourlyPrice × hours`.
   ├── If `billingMode` is `subscription` AND the Agent's `billings[]` contains MORE THAN ONE subscription entry:
   │     List every subscription entry (cycleType / cyclePrice / cycleMaxMessageCount) and ASK which one. Do not default to a line number. After the user picks, retain the selected entry's complete `agentCardBillingId` for the order request. Cost = that entry's `cyclePrice` (per cycle).
   ├── If `billingMode` is `subscription` AND there is exactly ONE subscription entry: use that entry's complete `agentCardBillingId` and its `cyclePrice` directly.
   └── If `billingMode` is `download` (One-Time Purchase): use the entry's complete `agentCardBillingId`. Cost = `oneTimeFee`.
→ Run the Payment Preference prompt with the computed cost (see payment.md). If the user picks Card, stop here and redirect to `{web_base}/agent/{agentId}`; only proceed below if the user picks Credits and the balance is sufficient.
→ Fetch current listed details or a successful quote and confirm a nonempty agentCardBillingId for the chosen plan. No ID/default may be invented; lineNo is display order only.
→ POST /agent/orders/buyer/create { agentId, agentCardBillingId, hours? }; hours is an integer 1–24 and must meet minPurchaseHours for hourly plans. Use the idempotency guidance in api-docs/03_order.md.
→ Availability false in search or a business error from buyer/create? → Report the actual failure and stop; never treat HTTP 200 alone as purchase success.
→ code=0 with status=paid and orderId? → Save the orderId (subscription purchases return a bill ID). Creation does not return instanceId. For Run Online, get the order detail to resolve its instanceId; do not choose an ambiguous instance by Agent ID.
→ Run Online paid order → follow installation.md (including existing-target confirmation), then install Thin Skill:
   → Run `python3 scripts/install_package.py --order-id <orderId>`
     The script completes three tasks in one command:
       ① GET /agent/orders/buyer/{orderId}/download to retrieve thinSkillTemplate
       ② Download and install using the returned thinSkillTemplate.folderName
       ③ Automatically write back thin_skills_state.json (no need to call any other script)
   → Script outputs JSON; key fields:
       · installed_to          ← Thin Skill install location
       · package_type          ← "thin_skill" (Thin Skill artifact; from a Run Online Agent) or "download" (Skill Package; from a Download Agent)
       · thin_skill_template_id
       · state_sync.synced     ← true means state persisted; false means manual repair needed (see Thin Skill state repair in installation.md)
   → Report installed files and dependency status. Claim automatic routing is ready only when state_sync.synced=true; otherwise report the sync failure and follow installation.md.
→ Insufficient Credits? → guide user to top up (see top-up in payment.md)
→ User returns from web payment → Query the known order detail, or list orders and resolve the matching record. Install only after paid/completed is confirmed. If the outcome is unknown, do not automatically create another order.
```

## "Renew / extend time or subscription"

**Trigger phrases**: renew, extend, almost expired

```
→ Confirm instanceId (from context or instance list)
→ Decide which renewal and gather the required quantity BEFORE Payment Preference:
   ├── Storage renewal (extending purgeAt): ASK explicitly: "How many months of storage do you want to add? (range 1–12)." Do NOT default. Compute cost = `renewMonths × 2.00 credits`.
   └── Time-based or expired subscription renewal:
       1. Call GET /agent/instance/{instanceId}/agent-version-billing to recover the purchased `billing` and the bound version's available `billings[]`.
       2. Require renewalEnabled=true, an allowed bound version status (listed or expired), and an instance still within retention. If renewal is disabled, stop. If `billing.billingMode` is `hourly`: ASK explicitly: "How many additional hours would you like to purchase? Minimum: {minPurchaseHours}." Do NOT guess. Reject values < `minPurchaseHours` and re-ask. Compute cost = `hourlyPrice × hours`.
       3. If `billing.billingMode` is `subscription`: require subscriptionStatus=expired, or canceled with the instance idle / the paid cycle ended; retrying is blocked (4074). For canceled but still valid subscriptions, use resume instead; do NOT ask for `hours`. Keep the original plan unless the user wants to switch. For a switch, show only subscription entries from the instance version's `billings[]` (cycleType / cyclePrice / cycleMaxMessageCount), confirm the selected plan and cost, and use its complete `agentCardBillingId` in the request. Preserve the original developer-version or experiment-plan constraints returned for this instance. Compute cost = the selected plan's `cyclePrice`, or `billing.cyclePrice` when keeping the original plan.
       4. If the billing data is missing or the mode is not compatible with the requested renewal, explain the mismatch and stop before Payment Preference.
→ Run the Payment Preference prompt with the computed cost (see payment.md). If the user picks Card, stop here and redirect to `{web_base}/my-agents` (renewal target per the Payment Preference Card branch); only proceed to either renewal endpoint below if the user picks Credits and the balance is sufficient.
→ Storage renewal: POST /agent/orders/instance-storage/renew { instanceId, renewMonths }
→ Time-based renewal (new order): POST /agent/orders/buyer/create { instanceId, hours }; omit agentCardBillingId to keep the original hourly plan
→ Eligible subscription renewal (new subscription relationship): POST /agent/orders/buyer/create { instanceId }; include agentCardBillingId only when switching to an allowed subscription plan. Omission keeps the original plan; never send hours.
→ For either buyer/create renewal, use the order idempotency guidance in `api-docs/03_order.md`
```

## Instance Reuse Principle

- When the user wants to continue a previous conversation or already has usage context, first query `GET /agent/instance` to check for an existing instance; prefer reuse
- The local thin_skills_state.json records the default instance and reusable instance list for each Agent
- When the platform indicates an Agent has a major update, **do not decide on behalf of the user** whether to create a new instance or continue the old one — the user must confirm

## Agent Details

When the user asks for more details about a specific Agent, call `GET /agent/agent/agents/{agentId}` to get complete information (billing plans, full description, model, version, security and privacy declaration, etc.). Basic fields in search results (title, rating, billing mode) are sufficient for simple display; the detail endpoint provides richer information.
