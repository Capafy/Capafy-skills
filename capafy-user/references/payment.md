# Payment and top-up

Read before any paid action or top-up. Determine the operation and cost through [commerce](commerce.md), and authenticate through [authentication](authentication.md).

Commands and script paths below are relative to the installed Skill root, not this references directory. API signatures (read only the module needed): [order](../api-docs/03_order.md), [account](../api-docs/08_account.md).

## Payment Preference (Ask Before Any Paid Action)

> **Before calling any endpoint that spends credits or charges money — new orders, time renewals, instance storage renewals, subscription creation — ask the user how they want to pay, even when the credits balance is sufficient. The Agent-side API only supports `credit` payment; card payment is web-only.**

> **Card payment minimum threshold**: Card payment is only available when the single-order total is **`>= $5 USD`** (i.e. **`>= 5` credits**, since 1 credit = $1 USD per platform spec). When the computed cost is **`< 5` credits**, do NOT offer the Card option at all — present only Credits in the prompt, and in the insufficient-credits sub-branch only the top-up follow-up applies. This threshold gate fires before the prompt is shown and before the insufficient-credits branching.

### Applies to

- `POST /agent/orders/buyer/create` (purchase in commerce.md new agent purchase, renewal in commerce.md time renewal, subscription creation)
- `POST /agent/orders/instance-storage/renew` (renewal in commerce.md instance storage renewal)

### Does NOT apply to (skip the prompt)

- `POST /agent/orders/topup/create` (top-up in payment.md — buying credits is itself the card transaction)
- `POST /agent/subscriptions/{subscriptionId}/resume` (account management in account-and-web.md — only flips the auto-renewal flag; the next billing uses the stored payment method)
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

   - **Credits + balance sufficient** → call the API as documented in commerce.md
   - **Card** → do NOT call any order API.

     ⚠️ **When credits balance is sufficient and the user picks Card**, the only response is the web redirect below. **Do NOT propose a "top up Credits via Stripe, then pay with Credits" two-step workaround** as an alternative — that adds friction, is not what the user asked for, and treats Card as if it required Credits as an intermediate. The top-up flow below is a separate operation; it is offered as an option **only** when credits are insufficient (see the sub-branch below).

     Redirect target depends on **whether this is a renewal of an existing instance or a brand-new order**. Both targets are resolved per [Web links](../SKILL.md#web-links).

     1. **Renewal / extend an existing instance** (renewal in commerce.md — time renewal via `POST /agent/orders/buyer/create { instanceId, hours }`, expired subscription renewal via `POST /agent/orders/buyer/create { instanceId }`, or storage renewal via `POST /agent/orders/instance-storage/renew`) → `{web_base}/my-agents`. The buyer locates the specific instance / subscription there and completes the renewal payment.
     2. **New order** (purchase in commerce.md — including a first-time purchase *and* the case where the user, after the duplicate-purchase check in commerce.md, explicitly chose to buy a new instance rather than reuse the active one) → `{web_base}/agent/{agentId}`. The Agent Card page fronts a Stripe Checkout for this specific Agent — Stripe → final order in one step, no Credits intermediate.

     Do **not** decide between these two by calling `GET /agent/orders/buyer/list?status=paid`; the dividing line is the operation type (renewal vs new order), not whether the buyer has prior order history for the Agent.

     Standard phrasing for **renewal**: *"Card payment must be completed on the web. Please open: {web_base}/my-agents — find this {instance / subscription} there and complete payment."*

     Standard phrasing for **new order**: *"Card payment must be completed on the web. Please open: {web_base}/agent/{agentId} — complete payment there."*

   - **Credits + balance insufficient** → offer follow-ups based on the card threshold:
     - **If cost `>= 5` credits**, offer two:
       - a. **Top up first** → run the top-up flow below, then retry the original action with credits
       - b. **Switch to card** → treat as if the user picked card from the start (apply the renewal-vs-new-order redirect rule above)
     - **If cost `< 5` credits**, offer only one (card is below threshold):
       - a. **Top up first** → run the top-up flow below, then retry the original action with credits
       - Switch-to-card is NOT available below the threshold; do not offer it.

### Memory within a session

By default, ask every time. Only suppress the prompt if the user explicitly says something like *"always use credits from now on"* or *"from now on charge my card"* — honor that for the rest of the current session. Do **not** carry the preference into future sessions; ask again next time.

## "Top up"

**Trigger phrases**: top up, add funds, buy Credits, insufficient balance

```
→ Confirm amount is 10–2000 USD and current balance + amount ≤ 2000 Credits.
→ POST /agent/orders/topup/create { amount, callbackUrl? }; use the idempotency guidance in api-docs/03_order.md. Save the top-up orderId.
→ Returns stripCheckoutUrl → send the link to complete payment; creation and callback successful do not prove the balance was credited.
→ POST /agent/orders/topup/{orderId}/payment-result (no body), using the original top-up ID, not a buyer bill.
   ├── pending_payment → retain the ID and check later; do not create another top-up automatically
   ├── payment_failed → show paymentFailureReason; let the user decide whether to retry with a new order
   └── paid → GET /agent/account, then use the refreshed balance before continuing the purchase
```
