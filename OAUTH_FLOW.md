<!-- cspell:ignore OIDC userinfo Fernet -->

# OAuth + JWT Auth — Flow & Architecture

This document explains how a user signs in to our deployment platform end-to-end: from clicking "Sign in with GitHub" in the browser, to receiving a usable session, to refreshing that session later. It covers control flow, data flow, and where each piece of state lives. No code — this is a design document; implementation will reference it.

Locked design decisions referenced throughout:
- `plan.md` §1 — Google = identity-only; GitHub = identity + data.
- `plan.md` §2 — identity keyed on `(provider, provider_user_id)`, linking only from authenticated session.
- `plan.md` §5 — provider tokens encrypted at rest with Fernet.
- `plan.md` §10 — JWT (access + refresh) for our app session.

---

## 1. The two-layer auth model (the most important thing to internalize)

There are **two completely separate authentication layers** operating in this system. Conflating them is the most common source of confusion.

```
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 2 — App session auth (our problem)                        │
│  Browser  ←─── JWT (access in memory + refresh cookie) ───→  Backend
│                                                                  │
│  We issue these. We rotate these. They are how our SPA proves    │
│  "I'm user 42" on every API call to our backend.                 │
└──────────────────────────────────────────────────────────────────┘
                                  ▲
                                  │ (Layer 2 exists only because Layer 1 succeeded)
                                  │
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 1 — Provider OAuth (Google/GitHub's problem)              │
│  Backend  ←─── OAuth code, then provider access token ───→  Google/GitHub
│                                                                  │
│  Google/GitHub issue these. We store them server-side, encrypted.│
│  We use them to call provider APIs (e.g. list GitHub repos).     │
│  The browser NEVER sees them.                                    │
└──────────────────────────────────────────────────────────────────┘
```

- **Layer 1 is OAuth.** Its job is to prove to *our backend* that "Google says this person is alice@gmail.com with stable ID `sub=11099822...`" and (in GitHub's case) to give us a token we can use to read their repos.
- **Layer 2 is JWT.** Its job is to prove to *our backend*, on every subsequent API call, that "the browser making this call belongs to user 42." This is what you already know from DRF-style API auth.

These two layers are independent: Layer 1 happens once at login (and again on linking, refresh, or re-consent). Layer 2 happens on every request.

---

## 2. OAuth 2.0 — the essential concepts

OAuth 2.0 is a protocol for delegated authorization. Four roles exist; understanding which is which is half the battle:

| Role | Who it is in our system |
|---|---|
| **Resource Owner** | The human user signing in. |
| **Client** | **Our backend** (Django). The name "client" is misleading — it does *not* mean the browser. It means the application asking for access on the user's behalf. |
| **Authorization Server** | Google's `accounts.google.com` / GitHub's `github.com/login/oauth/...`. The thing that authenticates the human and issues codes/tokens. |
| **Resource Server** | Google's APIs / GitHub's API. What we call with the access token to fetch profile data or repos. |

For Google, the Authorization Server and Resource Server are different hostnames. For GitHub, they're effectively the same host with different paths. The distinction matters conceptually, not in code.

### Which OAuth flow we use, and why

OAuth defines several flows. We use **Authorization Code with a confidential client**:

- **Authorization Code** = the user is redirected to the provider, the provider redirects back with a one-time `code`, the backend exchanges that code for tokens out-of-band (server-to-server). Tokens never pass through the browser.
- **Confidential client** = our backend can keep a client secret (it's a server, not a script in a browser). Google and GitHub trust us to authenticate ourselves to them with that secret.

Other flows exist (Implicit, Device, PKCE-without-secret) and are right for other shapes of app — SPAs talking directly to providers, TVs that can't open browsers, etc. None apply here because we have a real backend with secret storage.

---

## 3. Anatomy of the Authorization Code flow

Stripped of provider-specific details, here is what every Authorization Code flow looks like:

```
   Browser              Our Backend              Provider
      │                      │                       │
  (1) │  GET /oauth/X/start  │                       │
      │─────────────────────▶│                       │
      │                      │  generate state,      │
      │                      │  remember it          │
      │                      │  build authorize URL  │
      │  302 → provider URL  │                       │
      │◀─────────────────────│                       │
      │                                              │
  (2) │  GET authorize URL (?client_id=…&scope=…&state=…&redirect_uri=…)
      │─────────────────────────────────────────────▶│
      │  ←── login page ──                           │
      │  ←── consent page ──                         │
      │  302 → our /callback?code=…&state=…          │
      │◀─────────────────────────────────────────────│
      │                                              │
  (3) │  GET /oauth/X/callback?code=…&state=…        │
      │─────────────────────▶│                       │
      │                      │  verify state matches │
      │                      │  POST /token          │
      │                      │   {code, client_id,   │
      │                      │    client_secret,     │
      │                      │    redirect_uri}      │
      │                      │──────────────────────▶│
      │                      │  ←── access_token,    │
      │                      │     (refresh_token),  │
      │                      │     (id_token),       │
      │                      │     expires_in        │
      │                      │◀──────────────────────│
      │                      │  GET userinfo with    │
      │                      │   Authorization:      │
      │                      │   Bearer <access>     │
      │                      │──────────────────────▶│
      │                      │  ←── profile JSON     │
      │                      │◀──────────────────────│
      │                      │  decide: existing     │
      │                      │   user? new user?     │
      │                      │   linking? collision? │
      │                      │  encrypt + persist    │
      │                      │   provider token      │
      │                      │  ISSUE OUR JWT PAIR   │
      │                      │  set refresh cookie   │
      │   302 → /dashboard   │                       │
      │   (or JSON with      │                       │
      │    access token)     │                       │
      │◀─────────────────────│                       │
```

Three steps from the browser's perspective:
- **(1) Start:** browser hits our `/start`, we redirect it to the provider.
- **(2) Provider:** user logs in to provider + grants consent. Provider redirects back to our `/callback` with a one-time `code`.
- **(3) Callback:** our backend exchanges `code` for tokens (without involving the browser), creates/finds the user, then issues *our* JWT.

The `state` parameter is OAuth's CSRF defense — a random value we generate at step (1), echo through the provider, and verify at step (3). If they don't match, we reject the callback. Without state, an attacker could trick a logged-in victim into completing an OAuth handshake the attacker started.

---

## 4. Google specifics (OpenID Connect on top of OAuth)

Google implements OAuth 2.0 *and* OpenID Connect (OIDC), a thin standardization layer that adds an identity-specific token.

What's distinctive about Google's response:

| Field | What it is | We use it for? |
|---|---|---|
| `access_token` | OAuth token for calling Google APIs | Not really — Google is identity-only in our design (`plan.md` §1). |
| `id_token` | A signed JWT containing the user's identity claims (`sub`, `email`, `name`, `picture`, `email_verified`, ...) | **Yes — this is our source of truth for identity.** |
| `refresh_token` | Long-lived; lets us get a new access token without re-prompting the user | Stored encrypted, but rarely used since we don't call Google APIs. |
| `expires_in` | Seconds until `access_token` expires (typically 3600) | Saved as `token_expires_at`. |

Because the `id_token` is a *signed* JWT issued by Google, we can verify it without making an extra HTTP call to Google's userinfo endpoint. This is the key OIDC win. The signature proves "Google really said this." Validation involves checking the issuer, audience (our client ID), expiry, and signature against Google's published JWKS keys.

What we extract from the `id_token`:
- `sub` → stored as `GoogleProfile.google_sub` (the stable identity per `plan.md` §6)
- `email` → stored as `GoogleProfile.email`
- `name` → stored as `User.display_name` (only on first creation)
- `picture` → stored as `GoogleProfile.picture_url`

We deliberately don't call Google APIs after this. Google is purely an identity provider in our design.

---

## 5. GitHub specifics (plain OAuth, no OIDC)

GitHub does *not* implement OpenID Connect for OAuth Apps. There is no `id_token`, no signed JWT containing identity, no JWKS endpoint.

What we get back:

| Field | What it is |
|---|---|
| `access_token` | OAuth token for calling the GitHub REST/GraphQL API. **No expiry** for classic OAuth App tokens. |
| `scope` | Echo of granted scopes. |
| `token_type` | Always `bearer`. |

To learn who the user is, we have to *call* the API:

- `GET https://api.github.com/user` (with `Authorization: Bearer <access_token>`) returns `id`, `login`, `name`, `email`, `avatar_url`.
- We may also call `GET /user/emails` if we want their verified primary email when `email` is null on the main object (GitHub hides email by default).

What we extract:
- `id` → stored as `GitHubProfile.github_user_id` (numeric, stable across renames — `plan.md` §6)
- `login` → stored as `GitHubProfile.github_login`
- `avatar_url` → stored as `GitHubProfile.avatar_url`
- `name` → stored as `User.display_name` on first creation

The GitHub access token is then used for the subsequent **repository sync** (`plan.md` §7) — `GET /user/repos`, paginated.

### Why no refresh token from GitHub

OAuth Apps issue access tokens that simply don't expire (or expire only if the user revokes the app from their GitHub settings, or the token is unused for a long time per current policies). There's no refresh story because there's nothing to refresh against. If the user revokes us, the next API call returns 401 and we mark `GitHubProfile.last_sync_status = failure` and prompt re-auth (`plan.md` §13).

GitHub *Apps* (a different product) do have short-lived tokens with a refresh-like installation-token flow. We're using OAuth Apps for MVP simplicity; switching to GitHub Apps is documented future work in `plan.md`.

---

## 6. End-to-end: first-time login with GitHub

Putting it all together. User has no account in our system, clicks "Sign in with GitHub" on the marketing page.

```
Browser            SPA (Vite, :5173)         Backend (Django, :8000)        GitHub
   │                    │                            │                          │
   │ click button       │                            │                          │
   │───────────────────▶│                            │                          │
   │                    │ navigate to backend:       │                          │
   │ window.location =  │  /api/v1/oauth/github/start│                          │
   │  backend/start     │                            │                          │
   │───────────────────────────────────────────────▶│                           │
   │                                                │ generate state,           │
   │                                                │ store in signed cookie    │
   │                                                │ (also sets `intent=login`)│
   │                                                │                           │
   │  302 → https://github.com/login/oauth/authorize?client_id=…
   │       &scope=read:user%20repo&state=…&redirect_uri=…
   │◀───────────────────────────────────────────────│                           │
   │                                                                            │
   │ GET github.com/.../authorize                                               │
   │──────────────────────────────────────────────────────────────────────────▶│
   │  ← GitHub login page  ──                                                  │
   │  ← (user signs in)                                                        │
   │  ← consent page: "Repo-Manage wants: read profile, full repo access" ──   │
   │  (user clicks Authorize)                                                  │
   │  302 → backend:/api/v1/oauth/github/callback?code=…&state=…               │
   │◀──────────────────────────────────────────────────────────────────────────│
   │                                                                            │
   │ GET backend/.../callback?code=…&state=…                                    │
   │───────────────────────────────────────────────▶│                           │
   │                                                │ verify state vs cookie    │
   │                                                │ POST github.com/login/    │
   │                                                │  oauth/access_token       │
   │                                                │  {code, client_id,        │
   │                                                │   client_secret}          │
   │                                                │──────────────────────────▶│
   │                                                │  ← {access_token, scope} ─│
   │                                                │◀──────────────────────────│
   │                                                │ GET api.github.com/user   │
   │                                                │  Authorization: Bearer …  │
   │                                                │──────────────────────────▶│
   │                                                │  ← {id, login, name, …}  ─│
   │                                                │◀──────────────────────────│
   │                                                │                           │
   │                                                │ identity lookup:          │
   │                                                │  GitHubProfile WHERE      │
   │                                                │   github_user_id = id     │
   │                                                │ → not found               │
   │                                                │                           │
   │                                                │ intent=login, no current  │
   │                                                │  session → CREATE new     │
   │                                                │  User                     │
   │                                                │ create GitHubProfile,     │
   │                                                │  encrypt + store token    │
   │                                                │ enqueue first sync (§7)   │
   │                                                │                           │
   │                                                │ issue JWT pair:           │
   │                                                │  - access (15 min) in     │
   │                                                │    response body          │
   │                                                │  - refresh (14 days) in   │
   │                                                │    httpOnly cookie        │
   │                                                │                           │
   │  302 → SPA:/auth/complete#access=<jwt>                                     │
   │◀───────────────────────────────────────────────│                           │
   │                                                                            │
   │ SPA reads access from URL fragment,            │                           │
   │  drops fragment, stores in memory              │                           │
   │ subsequent /api/v1/* calls send:               │                           │
   │  Authorization: Bearer <access>                │                           │
   │  + automatic refresh cookie                    │                           │
```

A few delivery-mechanism choices land here:
- **How the SPA receives the access token after callback.** Common patterns: redirect to `/auth/complete#access=…` (fragment is JS-readable, doesn't go to server logs); or return JSON if the callback was opened in a popup that posts to the parent; or set a *short-lived* access cookie that the SPA reads once then clears. The redirect-with-fragment approach is the simplest and what this design assumes.
- **Refresh token transport.** Always an httpOnly + Secure + SameSite=Strict cookie (`plan.md` §10). The SPA never touches it; the browser attaches it automatically on calls to `/auth/refresh`.

---

## 7. End-to-end: first-time login with Google

Mostly the same shape, with two differences highlighted:

```
... [same as GitHub up through callback exchange] ...

                                                │ POST oauth2.googleapis.com/   │
                                                │  token {code, client_id,      │
                                                │  client_secret, redirect_uri, │
                                                │  grant_type=authorization_code}
                                                │──────────────────────────────▶│ Google
                                                │  ← {access_token,             │
                                                │     refresh_token,            │
                                                │     id_token,                 │
                                                │     expires_in}              ─│
                                                │◀──────────────────────────────│
                                                │                               │
                                                │ verify id_token signature     │
                                                │  using Google's JWKS          │
                                                │ extract claims:               │
                                                │   sub, email, email_verified, │
                                                │   name, picture               │
                                                │  (no HTTP call to userinfo!)  │
                                                │                               │
                                                │ identity lookup:              │
                                                │  GoogleProfile WHERE          │
                                                │   google_sub = sub            │
                                                │ → not found, create User,     │
                                                │   create GoogleProfile,       │
                                                │   encrypt + store access_     │
                                                │   token AND refresh_token     │
                                                │                               │
                                                │ NO sync — Google is           │
                                                │   identity-only (§1)          │
                                                │                               │
                                                │ issue JWT pair, set refresh   │
                                                │   cookie, redirect SPA        │
                                                │                               │
```

Two callouts:
1. The `id_token` removes the need for a separate `userinfo` call. Signature verification is the cost of avoiding the extra round-trip.
2. No first-sync trigger. The dashboard for a Google-only user shows the "Connect GitHub" CTA from `plan.md` §1.

---

## 8. End-to-end: account linking (user adds GitHub to a Google account)

User is already logged in via Google. Their dashboard shows "Connect GitHub" because they have no `GitHubProfile`. They click it.

```
SPA                  Backend                       GitHub
 │                     │                              │
 │ click "Connect GH"  │                              │
 │ window.location =   │                              │
 │  /api/v1/oauth/     │                              │
 │  github/start       │                              │
 │  (browser sends     │                              │
 │   refresh cookie    │                              │
 │   automatically;    │                              │
 │   start endpoint    │                              │
 │   also accepts      │                              │
 │   Authorization     │                              │
 │   header if SPA     │                              │
 │   sends it)         │                              │
 │────────────────────▶│                              │
 │                     │ resolve current_user_id from │
 │                     │  Bearer token / refresh      │
 │                     │  cookie session              │
 │                     │ generate state, store        │
 │                     │  intent=link, owner=user_id  │
 │                     │ 302 → github.com/...         │
 │ ... [same as before] ...                           │
 │                     │ exchange code, fetch /user   │
 │                     │ identity lookup:             │
 │                     │  GitHubProfile WHERE         │
 │                     │   github_user_id = id        │
 │                     │                              │
 │                     │ ┌──────────────────────────┐ │
 │                     │ │ Branching (plan.md §2):  │ │
 │                     │ │                          │ │
 │                     │ │ a) not found:            │ │
 │                     │ │    create GitHubProfile, │ │
 │                     │ │    attach to current     │ │
 │                     │ │    user_id, enqueue sync │ │
 │                     │ │                          │ │
 │                     │ │ b) found, attached to    │ │
 │                     │ │    SAME user_id:         │ │
 │                     │ │    refresh token,        │ │
 │                     │ │    no-op-ish             │ │
 │                     │ │                          │ │
 │                     │ │ c) found, attached to    │ │
 │                     │ │    DIFFERENT user_id:    │ │
 │                     │ │    REFUSE, return 409    │ │
 │                     │ │    "this GitHub account  │ │
 │                     │ │     is linked to another │ │
 │                     │ │     user — log in there  │ │
 │                     │ │     instead"             │ │
 │                     │ └──────────────────────────┘ │
 │                     │                              │
 │                     │ on success, DO NOT issue new │
 │                     │  JWT — the user is already   │
 │                     │  authenticated. Just redirect│
 │                     │  back to /dashboard.         │
 │                     │                              │
```

Key points:
- The same `/callback` endpoint handles both **login** and **link** intents — the `intent` value stashed in the state cookie tells the backend which branch to take.
- For **link**, we deliberately do NOT mint a new JWT. The user's session is unchanged; we've just attached a new provider profile to their existing `User` row.
- Collision (branch c) is the MVP-safe choice (`plan.md` §2). An explicit merge flow is future work.

---

## 9. End-to-end: returning user + JWT refresh

This is pure Layer 2 — no provider interaction at all.

```
SPA                                  Backend
 │                                     │
 │ GET /api/v1/repositories            │
 │  Authorization: Bearer <access>     │
 │ (refresh cookie also sent           │
 │  automatically, but unused for      │
 │  authenticated calls)               │
 │────────────────────────────────────▶│
 │                                     │ validate access JWT signature,
 │                                     │  check exp, load user
 │                                     │ → ok
 │ ← 200 with repo list ─              │
 │◀────────────────────────────────────│

  (15 minutes pass — access token expires)

 │ GET /api/v1/repositories            │
 │  Authorization: Bearer <stale>      │
 │────────────────────────────────────▶│
 │ ← 401 token expired ─              │
 │◀────────────────────────────────────│
 │                                     │
 │ SPA interceptor catches 401,        │
 │  pauses queued requests             │
 │                                     │
 │ POST /api/v1/auth/refresh           │
 │  (refresh cookie sent automatically)│
 │────────────────────────────────────▶│
 │                                     │ validate refresh JWT, check exp,
 │                                     │  check NOT in blacklist
 │                                     │ rotate: issue NEW refresh,
 │                                     │  add OLD refresh to blacklist
 │                                     │  with TTL = original exp
 │                                     │ issue new access
 │ ← {access: <new>}                   │
 │   Set-Cookie: refresh=<new>; ...    │
 │◀────────────────────────────────────│
 │                                     │
 │ SPA stores new access, resumes      │
 │  queued requests                    │
 │ GET /api/v1/repositories            │
 │  Authorization: Bearer <new>        │
 │────────────────────────────────────▶│
 │ ← 200 ─                             │
 │◀────────────────────────────────────│
```

### Refresh-token rotation and reuse detection

Each refresh request issues a *new* refresh token and blacklists the old one (`plan.md` §10). This gives us a tripwire:

- If the **old, blacklisted** refresh token ever shows up again (someone replayed it — likely an attacker), we revoke all the user's active refresh tokens and force a fresh login. This catches refresh-token theft via XSS without requiring perfect XSS prevention.

Reuse detection is the entire point of rotation. Without rotation, refresh tokens are bearer credentials that anyone can replay until they expire.

### Logout

Logout (`POST /api/v1/auth/logout`) blacklists the current refresh token and clears the refresh cookie. The access token, already in browser memory only, evaporates naturally; if it's still valid for the remaining ~15 min, that's accepted as a known short window.

---

## 10. Data flow & boundaries — what's stored where, who sees what

Visualizing where each piece of state lives and what crosses each wire:

```
┌─────────────────────────────────────────────────────────────────┐
│ BROWSER MEMORY (lifetime of tab)                                │
│   • JWT access token  ← readable by SPA JS, sent on every API call │
│                                                                 │
│ BROWSER COOKIE STORE (lifetime = refresh TTL)                   │
│   • Refresh cookie  ← httpOnly (opaque to JS),                  │
│                       Secure, SameSite=Strict                   │
│   • OAuth state cookie  ← only during in-flight OAuth handshake │
│                           (signed, short-lived, cleared on      │
│                            callback)                            │
└─────────────────────────────────────────────────────────────────┘
                          │   HTTPS, JWT in header
                          │   refresh cookie auto-sent on /auth/refresh
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ BACKEND (Django, in-memory)                                     │
│   • JWT signing key (from FERNET_KEY-adjacent env)              │
│   • Validates incoming access JWT signature + exp               │
│   • For OAuth callbacks: holds client_secret in memory          │
└─────────────────────────────────────────────────────────────────┘
                  │                                  │
                  │ DB                               │ HTTPS, server-to-server
                  ▼                                  ▼
┌────────────────────────────────┐   ┌──────────────────────────────┐
│ POSTGRES                       │   │ GOOGLE / GITHUB              │
│   • users                      │   │   • authenticates the human  │
│   • google_profiles            │   │   • issues codes + tokens    │
│      - google_sub              │   │   • serves their APIs        │
│      - access_token (Fernet)   │   │     (we call /user, /user/   │
│      - refresh_token (Fernet)  │   │      repos, etc.)            │
│   • github_profiles            │   │                              │
│      - github_user_id          │   │ Sees: our client_id (public),│
│      - access_token (Fernet)   │   │  client_secret (server only),│
│      - sync metadata           │   │  redirect_uri, scopes, code  │
│   • repositories               │   └──────────────────────────────┘
│   • projects                   │
│   • token_blacklist_*          │
└────────────────────────────────┘
```

**Boundaries that matter most:**

- **Provider tokens never reach the browser.** This is a non-trivial security property. Even if the SPA is compromised (XSS), the attacker has at most a 15-min JWT access token, *not* a long-lived GitHub `repo`-scoped token they could use to wreck the user's repos.
- **Client secret never leaves the backend.** It lives in env, gets loaded into memory at startup, and is used only on server-to-server calls.
- **OAuth `code` is a one-time, short-lived secret.** It's redeemable exactly once at the token endpoint. If it leaks (e.g., in browser history), it's useless unless the attacker also has our client_secret.
- **Refresh token is opaque to JS.** httpOnly cookie. Stolen only via XSRF or by a network attacker who can break TLS — both far harder than reading `localStorage`.

---

## 11. Token lifecycle table

The single biggest source of confusion when reading OAuth + JWT code is which token is which. Memorize this table.

|                       | Provider access token    | Provider refresh token   | Our JWT access            | Our JWT refresh                |
|-----------------------|--------------------------|--------------------------|---------------------------|--------------------------------|
| Issued by             | Google / GitHub          | Google only              | Our backend               | Our backend                    |
| Consumed by           | Provider's API           | Provider's token endpoint| Our backend's API views   | Our backend's `/auth/refresh`  |
| Lives in              | DB, Fernet-encrypted     | DB, Fernet-encrypted     | Browser memory            | httpOnly cookie                |
| Lifetime              | Google: 1 hr; GitHub: no expiry | Until revoked       | 15 min                    | 14 days                        |
| Refreshable?          | Google: yes (via refresh)| n/a                      | yes (via JWT refresh)     | yes (rotated on every use)     |
| Travels through browser? | **No**                | **No**                   | Yes (Bearer header)       | Yes (auto cookie only)         |
| Lost on logout?       | No (still in DB unless we revoke at provider) | Same | Yes (expires naturally)| Yes (blacklisted server-side)  |
| Lost on disconnect    | **Yes** (we delete the row) | Yes                  | Affected indirectly       | Affected indirectly            |

---

## 12. Edge cases the design handles

These are the failure modes we expect; the implementation will encode them as specific error paths.

| Situation | What the system does |
|---|---|
| `state` cookie missing or doesn't match callback `state` | Reject callback, 400. CSRF defense fired. |
| OAuth `code` is reused (e.g., user hits back button on /callback) | Provider returns error on second exchange; we surface 400 to user. |
| Linking GitHub to user A when GitHub is already on user B (`plan.md` §2 collision) | 409, no DB write. |
| Refresh JWT replayed (already blacklisted) | Revoke all user's refresh tokens, force fresh login. Reuse-detection fire. |
| Provider revokes our access token (user kicked the app out of GitHub settings) | Next API call returns 401 → mark `last_sync_status=failure`, prompt re-auth at `/oauth/github/start`. |
| Google `refresh_token` not returned on subsequent logins (Google omits it on later consents) | We rely on the first-consent refresh token; if we ever need to force a new one, we'd add `prompt=consent` to the authorize URL. Edge case for MVP. |
| User's email changed at the provider | Identity is keyed on `sub` / `github_user_id`, not email. Identity stays. We optionally update `User.email` from the new claim. |
| User deletes their account at the provider | Their stable ID stops resolving; next provider API call returns 404/401. We mark the profile inactive but don't auto-delete the local `User` (data retention is a product decision, not a security one). |

---

## 13. Why this architecture, in two sentences

We use **Authorization Code with a confidential client** because we have a real backend that can hold a client_secret, and because we want provider tokens to live exclusively on the server (encrypted at rest, never in the browser). We layer **rotating JWTs** over that flow because session state should be stateless and horizontally scalable, with reuse detection providing a tripwire against token theft.

Everything else — identity-not-email keying, link-only-from-session, two distinct database tables for providers, encrypted token columns — is downstream of these two foundational choices and is detailed in `plan.md`.

---

## 14. Glossary

| Term | Meaning |
|---|---|
| **OAuth 2.0** | Protocol for delegated authorization. Lets a user grant our app permission to act on their behalf with a provider, without sharing their password with us. |
| **OIDC (OpenID Connect)** | Identity layer built on top of OAuth 2.0. Adds the `id_token` (a signed JWT containing identity claims). Google supports it; GitHub does not. |
| **Authorization Code** | The OAuth flow we use. A short-lived `code` is sent through the browser; the actual tokens are exchanged backend-to-provider. |
| **Confidential client** | An OAuth client that can keep a secret — i.e., a backend, not an SPA-only app. We are one. |
| **`state`** | A random value generated by us at `/start`, echoed through the provider, validated at `/callback`. OAuth's CSRF defense. |
| **`scope`** | What the user is consenting to. For GitHub we ask for `read:user repo`; for Google `openid email profile`. |
| **Provider access token** | What Google/GitHub issue to let us call their APIs. Stored encrypted in `*_profiles.access_token_encrypted`. |
| **Provider refresh token** | Long-lived token to obtain new access tokens. Google issues these; GitHub OAuth Apps don't. |
| **JWT access token** | Our app's short-lived session token (15 min). Browser memory only. |
| **JWT refresh token** | Our app's long-lived rotation token (14 days). httpOnly cookie only. Rotated on every use. |
| **Reuse detection** | Treating a re-presented (already-blacklisted) refresh token as evidence of theft; triggers session-wide revocation. |
| **Fernet** | Symmetric authenticated encryption used to encrypt provider tokens at rest in our DB. Key from `FERNET_KEY` env. |
