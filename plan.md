<!-- cspell:ignore Fernet dramatiq exfiltratable exfiltration blocklist djangorestframework simplejwt structlog healthz readyz Jotai -->

# Architecture Decisions

This document records the architecture decisions for the Deploy Hub MVP — what was chosen, why, what was rejected, and where the future-work seams are. It's organised by concern; each section is self-contained.

## Status

| # | Topic | Status |
|---|---|---|
| 1 | Authentication providers & roles | Locked |
| 2 | Identity policy | Locked |
| 3 | Data model | Locked |
| 4 | Provider table design (two-table vs. polymorphic) | Locked |
| 5 | Token storage policy | Locked |
| 6 | User model | Locked |
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
  - **Google = identity provider only.** Used for login; no Google APIs are called after the OAuth handshake.
  - **GitHub = identity + data provider.** Used for login *and* repository fetch/sync.
- A user logging in via Google sees an empty repositories dashboard with informational copy explaining that GitHub is the data source.
- All GitHub data flows are gated on the user having a linked `GitHubProfile`. If absent, the API returns `409 Conflict` ("GitHub not connected") and the frontend renders an empty state.

## 2. Identity policy

- **Identity key:** `(provider, provider_user_id)` — *not* email.
  - `provider_user_id` is the provider's stable identifier (`sub` for Google, numeric `id` for GitHub). Usernames and emails can change; these IDs don't.
- **No auto-merge by email.** Emails are not a trustworthy join key:
  - Account-takeover risk — controlling either email-issuing side could hijack the other.
  - Emails rotate; shared inboxes exist; corporate emails get reassigned.
- **Logout + login with a different provider → separate `User` rows by default.** Same email is not enough to merge.
- **Linking is out of scope for MVP.** The spec lists "Login with GitHub OAuth" and "Login with Google OAuth" as two independent sign-in options on the login page; it never mentions linking accounts. Both sign-in paths are independent — a user who signs in with both providers (in separate sessions) gets two `User` rows that share an email. The frontend's provider badges on the dashboard are read-only status chips; there is no "Connect <other provider>" button.
- **Collision handling:** the only possible collision is two anonymous sign-ins resolving to the same `(provider, provider_user_id)` — handled idempotently by `resolve_*` in `accounts/services/user_service.py` (which upserts the matching profile and refreshes the stored token).
- **One account per provider per user.** Multi-GitHub-per-user is future work.

## 3. Data model

| Model | Purpose | Relationship | On delete |
|---|---|---|---|
| `User` | Provider-agnostic identity. Custom model via `AUTH_USER_MODEL`. | — | — |
| `GoogleProfile` | Google-specific identity + tokens. | `OneToOne(User)` | Cascade from `User` |
| `GitHubProfile` | GitHub-specific identity + tokens + sync state. | `OneToOne(User)` | Cascade from `User` |
| `Repository` | Mirror of a GitHub repo (source of truth = GitHub). | `FK → GitHubProfile` | Cascade from `GitHubProfile` |

### Fields per model

**`User`** — custom, abstracted from Django's user from day one (`AUTH_USER_MODEL` is painful to change later).

- `email`, `display_name`, `is_active`, `is_staff`, timestamps.
- Email-as-display (no `username`).

**`GoogleProfile`**

- `user` (OneToOne)
- `google_sub` — **UNIQUE**; the `sub` claim from Google's `id_token`; stable across email/name changes.
- `email`, `picture_url`
- `access_token_encrypted` (Fernet)

**`GitHubProfile`**

- `user` (OneToOne)
- `github_user_id` — **UNIQUE**; numeric GitHub ID (not username — usernames change on rename).
- `github_login`, `avatar_url`
- `access_token_encrypted` (Fernet) — no `refresh_token` (GitHub OAuth Apps don't issue them).
- Sync state: `last_synced_at`, `last_sync_status`, `last_sync_error`.

**`Repository`**

- `github_profile` (FK, cascade)
- `github_repo_id` (numeric — GitHub's stable repo ID)
- `name`, `full_name`, `private`, `default_branch`, `description`, `html_url`
- Upstream timestamps (`created_at`, `pushed_at`) + local timestamps
- **UNIQUE**(`github_profile`, `github_repo_id`) — prevents duplicates on re-sync.

### Why `Repository` links to `GitHubProfile`, not `User`

- Semantically, repos exist *because* of a GitHub connection.
- If the user disconnects GitHub, cascade cleanly removes their repos — no stale data.
- If the user later reconnects a *different* GitHub account, old repos don't incorrectly attach to the new account.

## 4. Provider table design — two tables, not polymorphic

- **Decision:** two physical tables (`GoogleProfile`, `GitHubProfile`), each with provider-specific columns.
- **Code reuse:** Django **abstract base model** `AbstractOAuthProfile` (no table) holds shared fields and methods (token encrypt/decrypt, timestamps). Provider models inherit from it.
- **Rejected alternative:** single polymorphic `oauth_accounts` table with a `provider` enum + JSONB raw profile.
- **Reasoning:**
  - **Asymmetry is real.** Google = identity-only, GitHub = identity + data sync. Different lifecycles, different operations, different attached state (sync metadata is GitHub-only).
  - **Lowest-common-denominator schema is lossy.** A polymorphic table forces nullable columns or JSONB blobs (no type safety, no indexed access without expression indexes).
  - **Sync metadata has no natural home** in a polymorphic table.
  - **Adding a new provider** requires bespoke OAuth callback code, scope handling, and profile-fetch logic regardless of schema shape. The migration is the cheapest part.
- **Polymorphic would be right when:** 5+ providers, symmetric behaviour, runtime-pluggable providers. None apply here.

## 5. Token storage policy

Two distinct "secret" concerns, deliberately separated:

| Secret | Lives in | Why |
|---|---|---|
| **OAuth client secrets** (the *app's* GitHub/Google app credentials) | Environment variables locally; managed secrets store (AWS Secrets Manager / Vault / Doppler) in production. Never in DB. Never in source. | One per app, rotated rarely; compromise = total platform compromise. |
| **Per-user OAuth tokens** (access + refresh) | Inside the corresponding profile table, **encrypted at rest**. | One per user, rotated per-user; compromise = single-user impact. |

- MVP encryption: Django `cryptography` Fernet with a single key sourced from environment (`FERNET_KEY`).
- Future: envelope encryption + key rotation without re-encrypting every row.
- Tokens are *never* sent to the frontend. The frontend holds only its own session/JWT; GitHub API calls are made server-side using the stored token.

## 6. User model — email-as-display, identity-as-tuple

- Drop Django's `username` field. `User.email` is the user-facing handle (admin lookup, dashboard display).
- **Email is the handle, not the identity.** Stable identity is the `(provider, provider_user_id)` tuple on the linked profile rows. If a user changes their primary email at GitHub or Google, identity holds; `User.email` is updated on next login.
- **`email` is intentionally NOT unique.** Two `User` rows can share an email — that's the natural consequence of §2's no-auto-merge policy when both providers return the same email. `USERNAME_FIELD = 'email'` is retained for Django's plumbing (admin, fixtures); `auth.E003` is silenced in `settings.py` because we never use `ModelBackend` password login — all authentication is OAuth → SimpleJWT.
- Rejected: keeping `username` as a vanity handle — can be added later without disruption if needed.

## 7. Repository sync — manual + auto-on-mount

- **Trigger:** sync is **manual** via a "Sync" button on the dashboard. The frontend additionally fires one auto-sync on dashboard mount when a GitHub profile is present, so returning users see up-to-date data without clicking.
- **Why not in the OAuth callback?** A full sync of a typical 120-repo user takes 20–40 s due to network round-trips between the application server and the database. Running that inside the OAuth callback blew past browser default request timeouts on first sign-in. Keeping the callback fast and triggering sync separately from the dashboard is the cleaner separation.
- **Execution model:** synchronous in-request with bounded pagination through the GitHub API. Sync writes status transitions on `GitHubProfile` (`in_progress` → `success` / `failure`). The dashboard shows a "Syncing…" indicator until the request returns.
- **Bounds:** `GITHUB_SYNC_MAX_PAGES=5` × `GITHUB_SYNC_PER_PAGE=100` = up to 500 most-recently-pushed repos per sync. Users with more are served by the future async path.
- **Future work:** async queue (Celery / RQ / dramatiq), GitHub webhooks for push-driven updates, periodic background refresh, detection of deleted-on-GitHub repos.

## 8. GitHub OAuth scopes — `read:user`, `user:email`, `repo`

- Requested scopes: `read:user` (profile), `user:email` (verified primary email even when the public profile email is hidden), and `repo` (full read/write to public *and* private repos).
- **Tradeoff acknowledged:** `repo` is broader than strictly needed for MVP read flows. We pick it because:
  - Private repos are a meaningful UX signal in a deployment platform — hiding them would mislead users.
  - Future "Deploy to K8S" flows will need write-equivalent power (status checks, deploy keys, branch reads on protected branches). Paying that consent cost once is better than re-prompting later.
- **Mitigations:** tokens encrypted at rest, never sent to the frontend, server-side use only, scope explicitly enumerated in the consent screen copy.
- **Documented future option:** a "public-only mode" that downgrades to `public_repo` for security-conscious users.

## 9. Pagination — offset-based

- API style: `?limit=10&offset=20` on list endpoints (`/repositories`).
- **Why offset, not cursor:** MVP-scale data (≤ a few hundred repos per user) doesn't hit offset's deep-pagination cost. Cursor pagination adds client-side opacity and API complexity without payoff at this scale.
- **Stable ordering is mandatory.** All paginated lists specify a deterministic `ORDER BY` (e.g., `pushed_at DESC, id ASC`) so offset is meaningful across requests.
- **Default page size:** 10. **Maximum:** 100.
- **Response shape:** `{ count, next, previous, results }` — DRF's `LimitOffsetPagination` default.
- **Future:** switch to cursor pagination when list sizes routinely exceed ~10k or write traffic causes noticeable offset drift.

## 10. Auth boundary — JWT

- Frontend ↔ backend boundary uses **JWT**, not Django sessions.
- **Token strategy:**
  - **Access token:** short-lived (~15 min), held **in memory** on the frontend (never `localStorage`), sent via `Authorization: Bearer …`.
  - **Refresh token:** long-lived (14 days), stored in an **httpOnly + Secure + SameSite=Strict** cookie. Inaccessible to JS; not exfiltratable via XSS.
  - `/auth/refresh` rotates the access token using the refresh cookie. **Refresh-token rotation** on each use (one-time-use refresh tokens; reuse detection triggers session revocation).
  - `/auth/logout` invalidates the refresh token (server-side blocklist with TTL) and clears the cookie.
- **Boot refresh:** the SPA's `AuthGuard` attempts one `POST /auth/refresh` on mount before redirecting to `/login` — ensures browser-refresh doesn't sign the user out.
- **Tradeoffs:**
  - **Pro:** stateless backend, horizontal scale without sticky sessions or session-store coupling.
  - **Pro:** clean API surface for future non-browser clients (CLI, mobile).
  - **Con:** revocation needs short access TTL + refresh rotation (what we do) or a blocklist (we keep a small one for refresh tokens only).
  - **Con:** XSS on the frontend remains serious — in-memory access tokens mitigate exfiltration but not in-page abuse.
- **Library choice:** `djangorestframework-simplejwt` for issuance/refresh/rotation. Custom glue for the OAuth-callback → JWT-issue handoff.

## 11. Frontend state — React Query + minimal local state

- **Server state** (user, repos, sync status): **React Query (TanStack Query)**. Centralized cache, automatic refetch on focus/reconnect, mutation-driven invalidation (e.g., post-sync invalidates `['repositories']`).
- **Client/UI state** (modals, form drafts, current page index): React `useState` / `useReducer`, scoped locally.
- **No global state library** (Redux / Zustand / Jotai) for MVP.
- **Rationale:** server state and client state have fundamentally different semantics (cache, freshness, refetch, coalescing). React Query is purpose-built; using a generic store for server state means re-implementing it badly.
- **Future:** introduce Zustand for cross-route *client* state if multi-step flows (deployment configuration wizards, drafts) appear.

## 12. Backend app boundaries — `accounts`, `oauth`, `repositories` (+ `core`)

Three Django apps + a `core/` package for shared utilities.

| App | Owns | Notable contents |
|---|---|---|
| `accounts` | `User` model, profile endpoints, JWT issuance/refresh views | `models.User`, `views.MeView`, `views.RefreshView`, `services.user_service`, `services.jwt_service` |
| `oauth` | `AbstractOAuthProfile`, `GoogleProfile`, `GitHubProfile`, OAuth callbacks, token encryption, state envelope | `models.AbstractOAuthProfile`, `models.GoogleProfile`, `models.GitHubProfile`, `views.GoogleCallbackView`, `views.GitHubCallbackView`, `services.token_crypto`, `services.state` |
| `repositories` | `Repository` model, GitHub sync service, list endpoint | `models.Repository`, `services.github_sync`, `services.github_client`, `views.RepositoryViewSet` |
| `core` | Shared mixins, base serializers, standard error responses, pagination defaults | `pagination.py`, `exceptions.py`, `responses.py`, `middleware.py` |

- Each app exposes URLs via its own `urls.py`, mounted in the project root under a versioned prefix (`/api/v1/...`).
- **Cross-app calls flow through service modules**, not direct model imports across app boundaries. Keeps coupling explicit and refactor-safe.

## 13. Sync metadata — fields on `GitHubProfile`

- Fields: `last_synced_at` (timestamp, nullable), `last_sync_status` (enum: `pending`, `in_progress`, `success`, `failure`), `last_sync_error` (text, nullable).
- **Why not a separate table for MVP:** dashboard only needs "latest sync state." A historical timeline isn't a current requirement and adds write volume + query complexity.
- **Future work:** introduce a `SyncLog` table (one append-only row per sync attempt) when debugging timelines, sync-rate analysis, or audit history becomes a real need.

## 14. Deploy placeholder — toast only

- Clicking **"Deploy to K8S"** triggers a frontend **toast notification** ("Deployment coming soon"). No backend call.
- The button hangs off each repo row on the dashboard.
- No "deploy intent" persistence — adds DB writes and migration cost for zero current value. Telemetry on click can be added later without schema changes.
- **Future work:** when real deployments land, the button becomes a multi-step flow (target selection → manifest generation → confirmation), persisted as a `Deployment` row owned directly by `User` (and FK'd to `Repository`).
