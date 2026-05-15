<!-- cspell:ignore OIDC JWKS userinfo Fernet -->

# OIDC (OpenID Connect) — A Beginner's Explainer

This is a companion to `OAUTH_FLOW.md`. That document assumes you already know what OIDC is and just tells you how we use it. This one starts from zero.

By the end you should be able to read sections 4 and 7 of `OAUTH_FLOW.md` without bouncing off the acronym.

---

## 1. The one-sentence definition

**OIDC is a thin standardization layer built on top of OAuth 2.0 that adds a way to answer the question "*who* is this user?" with a single signed token, instead of forcing you to make a separate API call.**

That sentence has three things worth unpacking:

1. "Thin standardization layer" — OIDC doesn't replace OAuth. It rides on top of it.
2. "Who is this user" — OAuth alone is about *authorization* (what an app is allowed to do). OIDC is about *authentication* (who the human is).
3. "Single signed token" — that token is the `id_token`, and it's the entire reason OIDC exists.

---

## 2. The problem OIDC solves

Imagine you've just implemented plain OAuth 2.0 (`OAUTH_FLOW.md` §2–3). The user clicks "Sign in with X", they redirect to the provider, they consent, the provider redirects back with a `code`, and you exchange that `code` for an `access_token`.

Now you have an access token. **But you still don't know who the user is.**

The access token says "you are allowed to call X's API on this person's behalf." It does *not* say "this person is alice@gmail.com with stable ID 11099822." To learn that, you have to make *another* HTTP call to the provider's "give me the profile" endpoint (often called `/userinfo` or `/user`).

That's exactly what we do for GitHub today (see `OAUTH_FLOW.md` §5):

```
Backend  ──── access_token ────▶  Provider's /userinfo endpoint
Backend  ◀─── { id, email, name, ... } ────
```

This works, but it has problems:

- **One extra round-trip on every login.** Slower.
- **No cryptographic proof of who said what.** You're just trusting that the JSON blob you got back came from the right provider — you trust it because the TLS connection terminated at their hostname, but the *payload itself* isn't signed.
- **Every provider's `/userinfo` looks slightly different.** GitHub returns `{ id, login, name, ... }`. Google returns `{ sub, email, name, ... }`. Microsoft returns something else. There's no standard.

OIDC fixes all three at once.

---

## 3. What OIDC adds: the `id_token`

OIDC says: "When the user exchanges their `code`, the provider should give back **a second token** alongside the access token — the `id_token` — which is a signed JWT containing the user's identity."

So instead of this (plain OAuth):

```
POST /token  with { code, client_id, client_secret }
  ←  { access_token, refresh_token, expires_in }
```

You get this (OIDC):

```
POST /token  with { code, client_id, client_secret }
  ←  { access_token, refresh_token, expires_in, id_token }   ← NEW
```

The `id_token` is the headline feature. Everything else in OIDC is supporting machinery for it.

### What's inside the `id_token`

It's a JWT (JSON Web Token) — three base64-encoded parts joined by dots: `header.payload.signature`. The payload is a JSON object full of standardized fields called **claims**. The important ones:

| Claim | Meaning |
|---|---|
| `iss` | Issuer — the URL of the provider that signed this. e.g. `https://accounts.google.com`. |
| `sub` | Subject — a **stable, opaque ID** for this user *at this provider*. Never changes, even if their email changes. |
| `aud` | Audience — our client_id. Proves this token was minted for us, not some other app. |
| `exp` | Expiry — Unix timestamp after which the token must be rejected. |
| `iat` | Issued-at — Unix timestamp when it was minted. |
| `email`, `email_verified`, `name`, `picture` | Standard profile claims, if the user consented to the `email`/`profile` scopes. |

Notice the standardization: every OIDC provider uses `sub` for the user ID, `email` for email, `name` for name. No more per-provider parsing.

### Why "signed" is the magic word

The `signature` part of the JWT is computed by the provider using their private key. We verify it using their public key. The math guarantees that:

1. **The provider really said this** — nobody else could have produced a valid signature.
2. **Nobody tampered with it** — flipping one bit in the payload invalidates the signature.

This means we can trust the contents of the `id_token` *without making a network call to verify it*. The token itself is the proof.

Compare:

| | Plain OAuth (GitHub-style) | OIDC (Google-style) |
|---|---|---|
| How we learn who the user is | Call `/userinfo` with the access token | Decode and verify the `id_token` |
| Network calls | 1 extra HTTP request | 0 (after one-time key fetch) |
| Cryptographic proof of authenticity | No (only TLS endpoint trust) | Yes (signature) |
| Standardized claim names | No | Yes |

---

## 4. How signature verification actually works (JWKS)

You might wonder: how do we get the provider's public key? We don't hardcode it — providers rotate keys regularly. Instead, OIDC providers publish their current public keys at a well-known URL called the **JWKS endpoint** (JSON Web Key Set).

For Google, it's `https://www.googleapis.com/oauth2/v3/certs`. It returns something like:

```json
{
  "keys": [
    { "kid": "abc123", "kty": "RSA", "n": "...", "e": "AQAB" },
    { "kid": "def456", "kty": "RSA", "n": "...", "e": "AQAB" }
  ]
}
```

The `id_token`'s header says which key signed it (`"kid": "abc123"`), so we know which entry in the JWKS to use. Our OIDC library (we'll use `python-jose` or `authlib`) handles this for us — it fetches and caches JWKS, finds the right key, verifies the signature, and checks `iss`, `aud`, and `exp`. We get back a parsed dict of claims or a verification error.

That's the full ceremony. From our code's perspective it's a one-liner; under the hood it's "fetch JWKS, find key, verify signature, validate standard claims."

---

## 5. OIDC vs. OAuth in one picture

```
┌─────────────────────────────────────────────────────────────┐
│  OAuth 2.0 (the protocol)                                   │
│  "Can this app act on the user's behalf?"                   │
│                                                             │
│  Gives you: access_token (for calling provider APIs)        │
│             refresh_token (to renew the access token)       │
│                                                             │
│  Does NOT tell you, directly, who the user is.              │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ OIDC adds one more thing:
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  OpenID Connect (built on top of OAuth)                     │
│  "...and also, here is a signed token saying who they are." │
│                                                             │
│  Adds:    id_token (signed JWT with identity claims)        │
│           a standard /userinfo endpoint (rarely needed if   │
│             id_token already has what you want)             │
│           a standard discovery doc at                       │
│             /.well-known/openid-configuration               │
│           standardized scope names: openid, email, profile  │
└─────────────────────────────────────────────────────────────┘
```

The `openid` scope is the trigger: if you include `openid` in your authorize request, the provider will return an `id_token`. Without `openid` in scopes, it's pure OAuth and you get no `id_token` back, even from an OIDC-capable provider.

That's why our Google authorize URL uses `scope=openid email profile` and not just `scope=email profile`.

---

## 6. How this maps to *this* project

Now `OAUTH_FLOW.md` §4 and §7 should make sense. The short version:

| Provider | OIDC? | How we learn user identity |
|---|---|---|
| **Google** | Yes | Decode the `id_token` we get back with the access token. No second HTTP call. |
| **GitHub** | No (OAuth Apps) | Call `GET https://api.github.com/user` with the access token. |

GitHub OAuth Apps just don't implement OIDC — there's no `id_token`, no JWKS endpoint. (GitHub *Apps*, a different product, are a bit closer but still don't speak OIDC the way Google does.) So we deal with each provider on its own terms: OIDC verification for Google, an extra API call for GitHub.

And from `OAUTH_FLOW.md` §11's token lifecycle table: the `id_token` doesn't appear there at all. That's deliberate. We use the `id_token` *once*, at callback time, to extract identity claims — then we throw it away. We don't store it, don't refresh it, don't pass it to the browser. It's a transient identity assertion, not a long-lived credential.

---

## 7. Common confusion points

A few traps a beginner usually falls into:

- **"Is the `id_token` the same as our JWT access token?"** No. They're both JWTs, but they're issued by different parties for different purposes. The `id_token` is issued by **Google** and proves identity to **us** at login. Our JWT access token (`OAUTH_FLOW.md` Layer 2) is issued by **us** and proves session identity to **us** on every API call. They never appear in the same context.

- **"Is OIDC more secure than plain OAuth?"** Not in the sense of "harder to hack." It's more *expressive*: it tells you something OAuth alone doesn't (who the user is, cryptographically). The actual security of the login flow comes from OAuth's Authorization Code mechanics — `state`, the `code` exchange, the client secret. OIDC sits on top.

- **"Do I need an OIDC library, or can I just decode the JWT myself?"** Use a library. JWT signature verification has sharp edges — algorithm confusion attacks, JWKS rotation handling, audience/issuer validation. `authlib` handles it all and is well-maintained.

- **"What if the provider supports OIDC but I just call `/userinfo` anyway?"** That works! `/userinfo` is a perfectly valid OIDC endpoint. The `id_token` is just an optimization that saves a round-trip. Some flows even use both — `id_token` for the immediate "who are you" answer, then `/userinfo` later if more claims are needed.

---

## 8. Glossary (just OIDC-specific terms)

| Term | Meaning |
|---|---|
| **OIDC** | OpenID Connect. An identity layer on top of OAuth 2.0. |
| **`id_token`** | A signed JWT issued by an OIDC provider that asserts who the user is. The defining feature of OIDC. |
| **Claim** | A field inside a JWT's payload. `sub`, `email`, `iss`, etc. |
| **JWKS** | JSON Web Key Set. A provider's published public keys, used to verify `id_token` signatures. Fetched from a well-known URL. |
| **`iss` / `sub` / `aud`** | Standard claims: who signed the token, who it's about, who it's for. The three things you always validate. |
| **Discovery document** | The JSON at `<provider>/.well-known/openid-configuration` listing all of a provider's OIDC endpoints. Lets libraries auto-configure. |
| **`openid` scope** | The magic scope name that tells an OIDC-capable provider "please include an `id_token` in the response." |

---

## 9. Where to go next

When you're ready to read code/design that uses this:
1. `OAUTH_FLOW.md` §4 (Google specifics) and §7 (Google end-to-end login).
2. `OAUTH_FLOW.md` §11 — notice that `id_token` does **not** appear in the token lifecycle table, and now you know why (it's a one-shot identity assertion, not a stored credential).
3. The Google docs at https://developers.google.com/identity/openid-connect/openid-connect for a vendor-flavored version of the same explanation.
