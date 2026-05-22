# Terminal Display Specification

The User Skill runs in a terminal / conversational environment where the information overload threshold is much lower than in a web interface. The following rules primarily describe output that the current scripts already produce; host rendering logic not yet implemented is noted separately as "recommended display".

---

## Search Results Display

At most **5 results** per page; each result kept to **3 lines**:

| Line | Content | Length Limit |
|------|---------|--------------|
| Line 1 | Title + rating + sales volume (free Agents get a 🆓 badge) | Title 50 chars + rating/sales ~15 chars |
| Line 2 | Short description or tags/category fallback (truncated) | **150 characters**, truncated with "…" |
| Line 3 | Price + billing mode; if no price in search results, show billing mode only | e.g. "$3/use \| Pay-per-Duration", "Subscription", "One-Time Purchase", or "Free" |

**Example output:**

```
🔍 Found 12 matching agents (showing 1-5)

 1. TikTok KOL Deep Analysis  ⭐4.8 (342 sales)
    Influencer data specialist: audience profiles, content performance, commercial value assessment, supports batch…
    $3/use | Pay-per-Duration

 2. Social Media All-in-One Assistant  ⭐4.5 (128 sales)
    Covers TikTok/Instagram/YouTube, multi-platform KOL comparison, auto-generates analysis rep…
    $29/month | Subscription

 3. KOL Quick Filter 🆓  ⭐4.2 (89 sales)
    Enter keywords to quickly filter matching KOLs; supports follower count/engagement rate/region filtering…
    Free

Enter "use N" to purchase | "next" for more results
```

`scripts/format.py` currently outputs directly:

```
Enter a number for details | enter "next page" to paginate | enter "use N" to start
```

> **Note**: When the user enters a number, the LLM may call `GET /agent/agent/agents/{agentId}` to retrieve complete details (billing plans, full description, model, etc.) and then ask whether they want to place an order.

## Balance Display

Recommended single-line text:

```
Credit balance: $15.00 (frozen: $3.00)
```

## Order Status Display

Recommended single-line text:

```
Order order_xxx: active, 1h23m remaining
```

## Long-Task Result Query

After receiving `timeout`, recommended display:

```
This is a long-running task — no need to wait. Say "next step" anytime to check the result.
```

> **Note**: User phrases like "next step", "continue", "what's the result?", "is it done?" all indicate intent to check results. The LLM should not require specific wording from the user.

The host or user then queries on their next turn:

```
GET /agent/relay/instances/{instanceId}/messages
```

Recommended result display:

```
The task is still running. I'll pull the latest message again shortly.
```

Then display the final message and files once completed.

## Installation Result Output (`install_package.py`)

The current script outputs JSON rather than a rich-text card:

```json
{"installed_to":"/home/user/.opencode/skills/demo-skill","deps_ok":true,"missing_deps":[],"env_vars_needed":[]}
```

> **Note**: Upon receiving this JSON, the LLM should translate it into natural language and inform the user: where it was installed, whether dependencies are ready, any missing dependencies and their install commands, and any environment variables that need to be configured. Do not output the raw JSON directly.

`env_vars_needed` comes from a heuristic scan of common environment variable references in the package; dependency installation attempts follow `requirements.txt` / `package.json` heuristically but is not equivalent to a full runtime acceptance test.

## Web Redirect Display

The most stable web redirect entry point from the current API documentation is the `stripCheckoutUrl` returned directly by the order endpoints.

Recommended display:

```
Web payment required. Please open:
https://checkout.stripe.com/...
```
