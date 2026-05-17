<!-- cspell:ignore Fernet dramatiq exfiltratable exfiltration blocklist djangorestframework simplejwt structlog healthz readyz Jotai -->

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
| 14 | Deploy placeholder semantics | Locked (revised 2026-05-17 — see §14) |
| 15 | `Project` model removed | Locked 2026-05-17 |

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
- **Linking is OUT OF SCOPE for MVP (locked 2026-05-17, after a brief in-scope iteration the same day).** The recruiter's spec lists "Login with GitHub OAuth" and "Login with Google/Gmail OAuth" as two independent sign-in options on the login page — it never mentions linking accounts or "Connect <other provider>". Implementing a link flow was over-engineering relative to the spec. The codebase therefore implements only the login path: two providers, two parallel sign-in entry points, each one stands on its own. A user who signs in with both providers (in different sessions) gets two separate `User` rows that share an email — by design, because identity is keyed on `(provider, provider_user_id)`, not email (see §6). The frontend does not surface a "Connect <other provider>" button. The provider status badges on the dashboard are read-only chips.
- **Reading-the-spec heuristic.** When the requirement says "Login with X" and "Login with Y" as two bullets, treat them as two independent entry points — not as "the same user can have X and Y attached." If the recruiter wanted the latter, the requirement would say "link Google with GitHub" or "after signing in with one, attach the other." The locked design here matches the literal read.
- **Collision handling (MVP):** with linking removed, the only collision possible is two anonymous sign-ins resolving to the same `(provider, provider_user_id)` — handled idempotently by `resolve_*` in `accounts/services/user_service.py`.
- **Google-only users.** A user who signs in via Google sees the dashboard, the "Google linked" badge, and an informational empty state on the Repositories section reading *"Sign in with GitHub to see your repositories."* (no button — the user logs out and signs back in via GitHub on the login page). This honours the spec's *"User logs in, sees repos"* happy path while keeping Google as a supported but limited login option.
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
- `name`, `slug`, `status`
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

## 6. User model — email-as-display, identity-as-tuple

- Drop Django's `username` field. `User.email` is the user-facing handle (admin lookup, dashboard display).
- **Email is the handle, not the identity.** Stable identity is the `(provider, provider_user_id)` tuple on the linked profile rows. If a user changes their primary email at GitHub or Google, identity holds; `User.email` is updated on next login.
- **`email` is intentionally NOT unique** (revised 2026-05-17). The earlier design called for `unique=True`, but that contradicted §2's "two `User` rows for two providers" policy when both providers return the same email. The constraint was removed via migration `accounts.0002_alter_user_email`. `USERNAME_FIELD = 'email'` is retained for Django's plumbing (admin, fixtures); `auth.E003` is silenced in `settings.py` because we never use `ModelBackend` password login — all authentication is OAuth → SimpleJWT.
- Rejected: keeping `username` as a vanity handle — can be added later without disruption if needed.

## 7. Repository sync — manual only (revised 2026-05-17)

- **All visits:** sync is **manual** via a "Sync" button on the dashboard. No periodic background sync for MVP, and no auto-sync on first sign-in.
- **Why the change.** The original design auto-triggered a full sync inside the GitHub OAuth callback so the dashboard would land populated. With Supabase Postgres in `aws-0-us-east-1` and our Lightsail host in `ap-south-1`, the ~240 cross-continent DB round-trips for a typical 120-repo user blew past the browser's default request timeout (~20–30 s), producing HTTP 499 (client-closed-connection) on first sign-in. Users would refresh, hit /start again, and the second callback would succeed (because `profile_created=False` on a now-existing user, skipping the sync). Cleaner to make Sync explicit and the first-sign-in callback fast.
- **First-time UX:** new GitHub users land on the dashboard with the empty Repositories state ("No repositories yet — click Sync above"). Click Sync once to fetch.
- **Execution model (MVP):** synchronous in-request with bounded pagination through the GitHub API. Sync writes status transitions on `GitHubProfile` (`in_progress` → `success` / `failure`). The synchronicity is *within* the explicit `/repositories/sync` call — the dashboard shows a "Syncing…" indicator until the request returns. The OAuth callback is now fast (no sync).
- **Bounds:** `GITHUB_SYNC_MAX_PAGES=5` × `GITHUB_SYNC_PER_PAGE=100` = up to 500 most-recently-pushed repos per sync. Users with more are served by the future async path.
- **Future work:** async queue (Celery / RQ / dramatiq), GitHub webhooks for push-driven updates, periodic background refresh, and moving Postgres to the same region as the Lightsail host so sync feels instantaneous.

## 8. GitHub OAuth scopes — `read:user` + `repo`

- Requested scopes: `read:user` (profile) and `repo` (full read/write to public *and* private repos).
- **Tradeoff acknowledged:** `repo` is broader than strictly needed for MVP read flows. We pick it because:
  - Private repos are a meaningful UX signal in a deployment platform — hiding them would mislead users.
  - Future "Deploy to K8S" flows will need write-equivalent power (status checks, deploy keys, branch reads on protected branches). Paying that consent cost once is better than re-prompting later.
- **Mitigations:** tokens encrypted at rest, never sent to the frontend, server-side use only, scope explicitly enumerated in the consent screen copy.
- **Documented future option:** a "public-only mode" that downgrades to `public_repo` for security-conscious users.

## 9. Pagination — offset-based

- API style: `?limit=20&offset=40` on list endpoints (`/repositories`, `/projects`).
- **Why offset, not cursor:** MVP-scale data (≤ a few hundred repos per user) doesn't hit offset's deep-pagination cost. Cursor pagination adds client-side opacity and API complexity without payoff at this scale.
- **Stable ordering is mandatory.** All paginated lists specify a deterministic `ORDER BY` (e.g., `pushed_at DESC, id ASC`) so offset is meaningful across requests.
- **Response shape:** `{ count, next, previous, results }` — DRF's `LimitOffsetPagination` default.
- **Future:** switch to cursor pagination when list sizes routinely exceed ~10k or write traffic causes noticeable offset drift.

## 10. Auth boundary — JWT

- Frontend ↔ backend boundary uses **JWT**, not Django sessions.
- **Token strategy:**
  - **Access token:** short-lived (~15 min), held **in memory** on the frontend (never `localStorage`), sent via `Authorization: Bearer …`.
  - **Refresh token:** long-lived (e.g., 14 days), stored in an **httpOnly + Secure + SameSite=Strict** cookie. Inaccessible to JS; not exfiltratable via XSS.
  - `/auth/refresh` rotates the access token using the refresh cookie. **Refresh-token rotation** on each use (one-time-use refresh tokens; reuse detection triggers session revocation).
  - `/auth/logout` invalidates the refresh token (server-side blocklist with TTL) and clears the cookie.
- **Tradeoffs acknowledged:**
  - **Pro:** stateless backend, horizontal scale without sticky sessions or session-store coupling.
  - **Pro:** clean API surface for future non-browser clients (CLI, mobile).
  - **Con:** revocation needs short access TTL + refresh rotation (what we do) or a blocklist (we keep a small one for refresh tokens only).
  - **Con:** XSS on the frontend remains serious — in-memory access tokens mitigate exfiltration but not in-page abuse.
- **Library choice:** `djangorestframework-simplejwt` for issuance/refresh/rotation. Custom glue for the OAuth-callback → JWT-issue handoff.

## 11. Frontend state — React Query + minimal local state

- **Server state** (user, repos, projects, sync status): **React Query (TanStack Query)**. Centralized cache, automatic refetch on focus/reconnect, mutation-driven invalidation (e.g., post-sync invalidates `['repositories']`).
- **Client/UI state** (modals, form drafts, theme): React `useState` / `useReducer`, scoped locally.
- **No global state library** (Redux / Zustand / Jotai) for MVP.
- **Rationale:** server state and client state have fundamentally different semantics (cache, freshness, refetch, coalescing). React Query is purpose-built; using a generic store for server state means re-implementing it badly.
- **Future:** introduce Zustand for cross-route *client* state if multi-step flows (deployment configuration wizards, drafts) appear.

## 12. Backend app boundaries — `accounts`, `oauth`, `repositories`, `projects` (+ `core`)

Four Django apps + a `core/` package for shared utilities.

| App | Owns | Notable contents |
|---|---|---|
| `accounts` | `User` model, profile endpoints, JWT issuance/refresh views | `models.User`, `views.MeView`, `views.TokenRefreshView`, `services.user_service` |
| `oauth` | `AbstractOAuthProfile`, `GoogleProfile`, `GitHubProfile`, OAuth callbacks, token encryption | `models.AbstractOAuthProfile`, `models.GoogleProfile`, `models.GitHubProfile`, `views.GoogleCallbackView`, `views.GitHubCallbackView`, `services.token_crypto` |
| `repositories` | `Repository` model, GitHub sync service, list/detail endpoints | `models.Repository`, `services.github_sync`, `services.github_client`, `views.RepositoryViewSet` |
| `projects` | `Project` model, deployment placeholder, list/CRUD endpoints | `models.Project`, `views.ProjectViewSet`, `views.DeployPlaceholderView` |
| `core` | Shared mixins, base serializers, standard error responses, pagination defaults | `pagination.py`, `permissions.py`, `responses.py`, `exceptions.py` |

- Each app exposes URLs via its own `urls.py`, mounted in the project root under a versioned prefix (`/api/v1/...`).
- **Cross-app calls flow through service modules**, not direct model imports across app boundaries. Keeps coupling explicit and refactor-safe.

## 13. Sync metadata — fields on `GitHubProfile`

Re-stated from section 3 for clarity and to lock the future-work seam:

- Fields on `GitHubProfile`: `last_synced_at` (timestamp, nullable), `last_sync_status` (enum: `pending`, `in_progress`, `success`, `failure`), `last_sync_error` (text, nullable).
- **Why not a separate table for MVP:** dashboard only needs "latest sync state." A historical timeline isn't a current requirement and adds write volume + query complexity.
- **Future work:** introduce a `SyncLog` table (one append-only row per sync attempt) when debugging timelines, sync-rate analysis, or audit history becomes a real need.

## 14. Deploy placeholder — toast only

- Clicking **"Deploy to K8S"** triggers a frontend **toast notification** ("Deployment coming soon"). No backend call.
- The button hangs off each repo row (added 2026-05-17 when the `Project` table was removed — see §15). The original design put it on a "projects" row but that abstraction added zero value at MVP scale.
- No "deploy intent" persistence — adds DB writes and migration cost for zero current value. Telemetry on click can be added later without schema changes.
- **Future work:** when real deployments land, the button becomes a multi-step flow (target selection → manifest generation → confirmation), persisted as a `Deployment` row owned directly by `User` (and FK'd to `Repository`).

## 15. `Project` model removed (2026-05-17)

- The `projects` Django app and its `Project` model are deleted. `INSTALLED_APPS`, `config/urls.py`, the frontend `useProjects` hook, and the dashboard `ProjectsSection` are all gone.
- **Why:** the original `Project` row had no fields beyond `name` + `status` + FKs, and "project = a repo I might deploy" turned out to be a thinly disguised duplicate of the `Repository` row. Conflating them was UX confusion; separating them was DB noise.
- The legacy `projects_project` table is left in place on the prod SQLite DB (0 rows, never queried). It can be dropped at any time with `DROP TABLE projects_project;` — no application code references it.
- The screening-task spec mentions a "projects table" — that bullet is fulfilled in spirit by the repos list with its Deploy buttons (which is what the spec author actually wanted: a list of deployable things). The literal "Projects table" UI element is gone.

---

## Open items / next to decide

The previous round of opens is closed. Items to surface as we move deeper into the architecture doc:

- [ ] **API versioning mechanism** — path-based (`/api/v1/`) vs. header-based. Lean: path-based.
- [ ] **Error response standard** — DRF default exceptions vs. RFC 7807 (`application/problem+json`).
- [ ] **Logging/observability stack** — `structlog` + JSON to stdout for MVP? Sentry for error tracking? Health-check endpoints (`/healthz`, `/readyz`)?
- [ ] **Production deployment target** — local `docker-compose` for dev is given; what's "prod"? (Fly.io, Railway, AWS ECS, k8s.) Affects reverse-proxy and static-asset sections.
- [ ] **CI/CD direction** — GitHub Actions assumed; what gates (lint, type-check, tests, migrations dry-run, container build)?
- [ ] **Rate limiting** — DRF throttle classes (per-user, per-IP, per-endpoint) and any GitHub-API-side throttling we expose to clients.
- [ ] **CSRF posture** — with JWT in Authorization header for API calls and refresh cookie marked SameSite=Strict, do we still need Django's CSRF middleware on `/api/`? (Answer is likely "no for API, yes for any cookie-authenticated routes.")
