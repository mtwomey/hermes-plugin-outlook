---
name: outlook
description: >
  Robert Half work email (mattwo01@roberthalf.com) via the outlook native plugin.
  This is a redirect stub — load the full skill with skill_view(name="outlook:outlook").
category: email
triggers:
  - "check my work email"
  - "robert half email"
  - "outlook"
  - "work email"
  - "outlook_"
---

# outlook — redirect stub

The full skill lives inside the `outlook` plugin and is registered at runtime.

**Load it with:**

```
skill_view(name="outlook:outlook")
```

This stub exists solely so `skills_list(category="email")` surfaces the skill
and agents can discover the correct namespaced name.

---

## Token Diagnostics (local notes)

The Outlook refresh token is a **binary MSAL SPA token — not a plain JWT**.
Attempting to decode it with base64/json.loads will fail with codec errors.
Do **not** try to read expiry from the token body.

**To check when the token was last rotated (= when the 24h clock started):**

```bash
security dump-keychain 2>/dev/null \
  | grep -A 15 '"hermes-outlook"' \
  | grep -A 3 '"refresh_token"' \
  | grep mdat
# Output: "mdat"<timedate>=0x...  "20260701153235Z\000"
# Format: YYYYMMDDHHmmssZ (UTC). Add 24h for expiry.
```

The token **auto-rotates on every successful API call** — using any Outlook tool
resets the 24-hour clock. If you just read email successfully, the token is fresh.
