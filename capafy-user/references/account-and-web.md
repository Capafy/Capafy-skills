# Accounts, subscriptions, web redirects and publishing handoff

Read for account/order/subscription management, reviews, web-only requests or Publisher handoff. Protected calls require [authentication](authentication.md).

Commands and script paths below are relative to the installed Skill root, not this references directory. API signatures (read only the module needed): [account](../api-docs/08_account.md), [order](../api-docs/03_order.md), [subscription](../api-docs/06_subscription.md), [instance](../api-docs/05_instance.md).

## "View my account / balance / subscriptions / orders"

**Trigger phrases**: account, balance, Profile, bio, orders, subscriptions, spending history

```
→ Account info: GET /agent/account
→ View Profile: GET /agent/account/profile
→ Update Profile: PUT /agent/account/profile { "profile": "<new content>" }
→ Order list: GET /agent/orders/buyer/list?status=paid
→ Order detail: GET /agent/orders/buyer/{orderId}/detail
→ Subscription list: GET /agent/subscriptions/list
→ Subscription fields are cycleType/cyclePrice/nextBillingAt/firstPaymentAt (Unix milliseconds); active filtering also includes trialing.
→ Cancel subscription: POST /agent/subscriptions/{subscriptionId}/cancel; use effectiveAt in the response (retrying cancellation may take effect immediately)
→ Resume subscription: POST /agent/subscriptions/{subscriptionId}/resume; only canceled subscriptions before cycle expiry, and renewalEnabled=true. Response uses nextBillingAt.
→ Instance list: GET /agent/instance?status=active
→ Rename instance: PATCH /agent/instance/{instanceId} { "name": "<new name>" }
```

## "Rate / review this Agent"

```
→ Need agentId (obtained from search results, instance list, or order information)
→ POST /agent/review/agents/{agentId}/review { rating, comment }
→ Each buyer can only review an Agent once; returns 4049 if already reviewed
→ A valid purchase record for the Agent is required before reviewing
```

## Web Redirect Operations (not covered by API — this Skill only identifies intent and provides links)

The following operations are not performed via in-Agent API calls. Once the LLM identifies the intent, it builds the corresponding web link and sends it to the user.

> All paths in this section are relative. Prepend the web base before showing each link to the user — see [Web links](../SKILL.md#web-links) for the derivation rule (read `scripts/common/defaults.py`, strip `/api`).

| User Intent | Example Trigger Phrases | Redirect Path |
|-------------|------------------------|---------------|
| Refund / dispute an order | refund, money back, not working, complaint, cancel order | `/wallet` |
| Set auto spending limit | spending cap, monthly limit, safety limit, auto-charge limit | `/settings` |
| Manage Access Tokens | Token management, API Key, reset token | `/settings?tab=token` |
| Switch subscription payment method | change subscription payment, switch to credit card for subscription | `/subscriptions/{subscriptionId}/payment` |
| View billing details | billing details, account statement, how much have I spent | `/wallet` |
| Report an Agent | report, violation, this Agent has a problem | `/report/{agentId}` |

> **Note**: Binding or changing a credit card is handled natively by Stripe's hosted checkout, not by a Capafy page; no in-Skill redirect is exposed for that. If a buyer asks to manage their card, tell them it happens during the next Stripe checkout (e.g. top-up at top-up in payment.md).

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

## "I want to list / sell something I built" (Redirect — Not Handled by This Skill)

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
