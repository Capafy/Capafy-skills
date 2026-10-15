# Authentication

Read before protected operations or an explicit login/account switch. Guest browsing needs no login.

Commands and script paths below are relative to the installed Skill root, not this references directory. API signatures (read only the module needed): [auth](../api-docs/01_auth.md).

## Authentication (Verify Before Protected Operations)

> Search and listed details allow guest access; do not require login just to browse. Public quotes use guest mode (see discovery in commerce.md). Before orders, account, instance, subscription, downloads or chat, verify authentication through this section.

```
Local token present? (scripts/auth.py load)
├── Yes → GET /agent/account
│   ├── HTTP 200 with business code=0 → logged in, continue
│   ├── 401 / 1007 → token expired, re-authenticate
│   └── Other failure → report the error; do not treat HTTP 200 alone as login success
└── No → login flow (email OTP):
    ⛔ **Compliance gate — every login, no session-level cache**:
       Before sending the OTP request, the user must explicitly accept the
       Terms of Service and the Privacy Policy. Required every time the
       email login flow is entered, even if the same user consented earlier
       in the same session.

       a. Tell the user this login requires accepting the platform's Terms
          of Service and Privacy Policy. Send both URLs verbatim (resolve
          `{web_base}` per the Web links section of ../SKILL.md):
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
       ├── wrong code → the challenge remains usable until expiresInSec has elapsed.
       │   Ask for the corrected code and repeat step 5 with the same challengeId.
       │   If it has expired, return to step 2 for a new challenge.
       └── challengeId expired / invalid → explain the error, then loop back
           to step 2 to request a new challenge and email code.
    6. scripts/auth.py save <accessToken>
```

Login, guest search/details and guest public quotes can run without an Access Token. Other buyer endpoints require one. Explicitly supplied Access Tokens on search/details are still validated; use `capafy_http.py --no-auth` for a guest request. The current OTP validity is 300 seconds; always use the returned expiresInSec.
