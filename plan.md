# Plan — Deployment Platform MVP Architecture

Working document for architecture decisions. Items locked here will flow into the final architecture document (per PROMPT.txt). We add items one by one as they're settled.

## Status

| # | Topic | Status |
|---|---|---|
| 1 | Authentication providers & roles | Locked |
| 2 | Identity & linking policy | Locked |
| 3 | Data model — five tables | Locked |
| 4 | Provider table design (two-table vs. polymorphic) | Locked |
| 5 | Token storage policy | Locked |
| 6 | User model — email-only identifier | Locked |
| 7 | Repository sync trigger | Locked |
| 8 | GitHub OAuth scopes | Locked |
| 9 | Pagination strategy | Locked |
| 10 | Auth boundary — JWT | Locked |
| 11 | Frontend state management | Locked |
| 12 | Backend app boundaries | Locked |
| 13 | Sync metadata storage | Locked |
| 14 | Deploy placeholder semantics | Locked |

---

## 1. Authentication providers & roles

- Two OAuth providers supported: **Google** and **GitHub**.
- Roles are **asymmetric** — this is the key insight that shapes the rest of the design:
  - **Google = identity provider only.** Used for login; no data is fetched from Google APIs.
  - **GitHub = identity + data provider.** Used for login *and* repository fetch/sync.
- A user logging in via Google sees an empty repositories dashboard with a **"Connect GitHub"** CTA.
- All GitHub data flows are gated on the user having a linked `GitHubProfile`. If absent, the API returns `409 Conflict` ("GitHub not connected"), and the frontend renders the connect prompt.

## 2. Identity & linking policy

- **Identity key:** `(provider, provider_user_id)` — *not* email.
  - `provider_user_id` is the provider's stable identifier (`sub` for Google, numeric `id` for GitHub). Usernames and emails can change; these IDs don't.
- **No auto-merge by email.** Emails are not a trustworthy join key:
  - Account-takeover risk (controlling either email-issuing side could hijack the other).
  - Emails rotate; shared inboxes exist; corporate emails get reassigned.
- **Logout + login with a different provider → separate `User` rows by default.** Same email is not enough to merge.
- **Linking happens only from an authenticated session:**
  1. User is already logged in (via Google or GitHub).
  2. Settings → "Connect <other provider>" → OAuth round-trip.
  3. Backend writes a new profile row attached to the existing `User`.
- **Collision handling (MVP):** if the second provider's account is already attached to a *different* `User`, refuse the link with a clear message ("This GitHub account is already linked to another user — log in there instead"). An explicit merge flow is future work.
- **One account per provider per user** for MVP (no multi-GitHub-per-user). Future work.

## 3. Data model — five tables

| Model | Purpose | Relationship | On delete |
|---|---|---|---|
| `User` | Provider-agnostic identity. Custom model via `AUTH_USER_MODEL`. | — | — |
| `GoogleProfile` | Google-specific identity + tokens. | `OneToOne(User)` | Cascade from `User` |
| `GitHubProfile` | GitHub-specific identity + tokens + sync state. | `OneToOne(User)` | Cascade from `User` |
| `Repository` | Mirror of a GitHub repo (source of truth = GitHub). | `FK → GitHubProfile` | Cascade from `GitHubProfile` |
| `Project` | App-owned deployment entity referencing a repo (source of truth = our DB). | `FK → User` (cascade) + `FK → Repository` (nullable, SET_NULL) | Survives repo deletion |

### Fields per model

**`User`** — custom, abstracted from Django's user from day one (`AUTH_USER_MODEL` is painful to change later).
- `email` (unique), display name, `is_active`, timestamps.
- Email-as-identifier (no `username`) — *to confirm; see Open Items.*

**`GoogleProfile`**
- `user` (OneToOne)
- `google_sub` — **UNIQUE**; the `sub` claim from Google's ID token; stable across email/name changes.
- `email`, `picture_url`
- `access_token` (encrypted), `refresh_token` (encrypted), `token_expires_at`, `scopes`

**`GitHubProfile`**
- `user` (OneToOne)
- `github_user_id` — **UNIQUE**; numeric GitHub ID (not username — usernames change on rename).
- `github_login`, `avatar_url`
- `access_token` (encrypted), `scopes` — *no* `refresh_token` (GitHub OAuth Apps don't issue them; GitHub Apps do, out of scope for MVP).
- Sync state: `last_synced_at`, `last_sync_status`, `last_sync_error`.

**`Repository`**
- `github_profile` (FK, cascade)
- `github_repo_id` (numeric — GitHub's stable repo ID)
- `name`, `full_name`, `private`, `default_branch`, `description`, `html_url`
- Upstream timestamps (`created_at`, `pushed_at`) + local timestamps
- **UNIQUE**(`github_profile`, `github_repo_id`) — prevents duplicates on re-sync.

**`Project`**
- `user` (FK, cascade)
- `repository` (FK, nullable, SET_NULL — project survives if repo disappears)
- `name`, `slug`, `deployment_target` (placeholder "k8s" for MVP), `status`
- Timestamps
- **UNIQUE**(`user`, `name`)

### Why `Repository` links to `GitHubProfile` (not `User`)

- Semantically, repos exist *because* of a GitHub connection.
- If the user disconnects GitHub, cascade cleanly removes their repos — no stale data.
- If the user later reconnects a *different* GitHub account, old repos don't incorrectly attach to the new account.

### Why `Project` decouples from `Repository`

- `Project` is *our* deployment entity, not GitHub's. It must not vanish just because the upstream repo did (disconnect, repo deleted, transferred).
- `SET_NULL` on repo deletion preserves project history; `CASCADE` on user deletion is correct because there's nothing to keep without the owner.

## 4. Provider table design — two tables, not polymorphic

- **Decision:** two physical tables (`GoogleProfile`, `GitHubProfile`), each with provider-specific columns.
- **Code reuse:** Django **abstract base model** `AbstractOAuthProfile` (no table) holds shared fields and methods (token encrypt/decrypt, `scopes`, timestamps). Provider models inherit from it.
- **Rejected alternative:** single polymorphic `oauth_accounts` table with a `provider` enum + JSONB raw profile.
- **Reasoning:**
  - **Asymmetry is real.** Google = identity-only, GitHub = identity + data sync. They have different lifecycle (refresh tokens, expiry), different operations, and different attached state (sync metadata is GitHub-only).
  - **Lowest-common-denominator schema is lossy.** A polymorphic table forces nullable columns (refresh_token, expires_at) or JSONB blobs (no type safety, no indexed access without expression indexes).
  - **Sync metadata has no natural home** in a polymorphic table.
  - **Adding a new provider** requires bespoke OAuth callback code, scope handling, and profile-fetch logic regardless of schema shape. The migration is the cheapest part.
- **Polymorphic would be right when:** 5+ providers, symmetric behavior, runtime-pluggable providers (e.g., an Auth0-style aggregator). None apply here.

## 5. Token storage policy

Two distinct "secret" concerns, deliberately separated:

| Secret | Lives in | Why |
|---|---|---|
| **OAuth client secrets** (the *app's* GitHub/Google app credentials) | Environment variables locally; managed secrets store (AWS Secrets Manager / Vault / Doppler) in production. Never in DB. Never in source. | One per app, rotated rarely, compromise = total platform compromise. |
| **Per-user OAuth tokens** (access + refresh) | Inside the corresponding profile table, **encrypted at rest**. | One per user, rotated per-user, compromise = single-user impact. |

- MVP encryption: Django `cryptography` Fernet with a single key sourced from the secrets store.
- Future: envelope encryption + key rotation without re-encrypting every row.
- Tokens are *never* sent to the frontend. The frontend holds only its own session/JWT; GitHub API calls are made server-side using the stored token.

---

## Open items / next to decide

- [ ] **Email-as-identifier vs. keep `username`** on `User`. Lean: email-only.
- [ ] **Repository sync trigger** — manual button only for MVP, or auto-sync on first login / on every login? Lean: manual + first-login auto, with periodic auto-sync as future work.
- [ ] **GitHub OAuth scopes** — `read:user` + `repo` (private repos visible) vs. `read:user` + `public_repo` (public only). Lean: `public_repo` for MVP (least privilege).
- [ ] **Pagination strategy** for the repositories list — cursor vs. offset.
- [ ] **Session vs. JWT** for the frontend auth boundary (cookie-based session is simpler with Django; JWT is more API-native).
- [ ] **Frontend state management** — React Query + minimal local state vs. Redux/Zustand.
- [ ] **Backend app/module boundaries** — Django apps layout (`accounts`, `oauth`, `repositories`, `projects` …).
- [ ] **Sync metadata storage** — fields on `GitHubProfile` (MVP) vs. separate `SyncLog` table (future).
- [ ] **Deployment placeholder semantics** — what does clicking "Deploy to K8S" record/return in the MVP? (No-op toast? Persist an attempt row?)
