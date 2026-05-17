# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A small deployment-platform MVP: users sign in via Google or GitHub OAuth, browse their GitHub repos, and create `Project` rows that will eventually deploy to K8s. Backend is Django 6 + DRF + SimpleJWT; frontend is Vite + React 19 + TypeScript + Tailwind v4. Architectural decisions are locked in [`plan.md`](plan.md); the end-to-end auth design is in [`OAUTH_FLOW.md`](OAUTH_FLOW.md). **Always consult `plan.md` before changing data-model, auth, or app-boundary shape** — most "why is it this way?" answers live there.

## Common commands

Everything runs through the root `Makefile`, which assumes the backend has its own venv at `backend/venv/`. Don't invoke `manage.py` or `pytest` directly from the repo root — they need `cd backend &&` and `./venv/bin/...`.

```bash
make install         # backend venv + pip install + npm install
make backend         # Django dev server :8000
make frontend        # Vite dev server :5173
make migrate         # apply migrations
make makemigrations  # generate from model changes
make superuser
make test            # full pytest suite (backend only — no frontend tests yet)
make lint            # ruff check
make format          # ruff format
```

Run a subset of tests (must `cd backend` first because pytest config lives in `backend/pyproject.toml`):

```bash
cd backend && ./venv/bin/pytest accounts/        # one app
cd backend && ./venv/bin/pytest -k oauth         # by keyword
cd backend && ./venv/bin/pytest accounts/tests.py::TestMeView::test_returns_user  # one test
```

Frontend lint: `cd frontend && npm run lint`. Frontend build: `npm run build`.

## Architecture — the load-bearing pieces

### Two completely separate auth layers

Internalize this before touching anything in `oauth/` or `accounts/`:

- **Layer 1 — Provider OAuth.** Backend ↔ Google/GitHub. Server-side only. Per-user access tokens stored **Fernet-encrypted** in `GoogleProfile.access_token_encrypted` / `GitHubProfile.access_token_encrypted`. Never sent to the browser. Always go through `profile.set_access_token(...)` / `profile.get_access_token()` (defined on `AbstractOAuthProfile` in `backend/oauth/models.py`) — direct field reads will hand you ciphertext.
- **Layer 2 — App session JWT.** Browser ↔ backend. SimpleJWT-issued. Access token (~15 min) held in memory on the SPA via `frontend/src/lib/authStore.ts` — **never `localStorage`**. Refresh token (~14 days) in an httpOnly cookie scoped to `/api/v1/auth/`, with rotation + blacklist-on-rotate (reuse detection). The OAuth callback views are the *only* place the two layers meet: they exchange the provider code, resolve the user, then mint a JWT pair via `accounts.services.jwt_service.issue_jwt_pair`.

The full sequence (state-cookie issuance, JWKS verify for Google, `/user` fetch for GitHub, fragment-delivery of the access token to the SPA) is in `OAUTH_FLOW.md`.

### Asymmetric provider roles

Google = **identity only** (OIDC `id_token` is verified against Google's JWKS; no API calls beyond token exchange). GitHub = **identity + data** (we also fetch and sync the user's repos). This asymmetry is why there are two physical profile tables (`GoogleProfile`, `GitHubProfile`) rather than a single polymorphic `oauth_accounts` table — they have different lifecycle, scopes, and attached state (sync metadata is GitHub-only). See `plan.md` §4.

### Identity key is `(provider, provider_user_id)`, not email

`GoogleProfile.google_sub` and `GitHubProfile.github_user_id` are the stable identifiers. Emails can change and aren't trustworthy as a join key — **no auto-merge by email**. If a user signs in via Google and later via GitHub with the same email, they get two separate `User` rows. The linking flow that would have joined them has been removed from the frontend; `accounts/services/user_service.py` is now login-only. See `plan.md` §2.

### Data-model cascade semantics (deliberate)

```
User ── OneToOne ──► GoogleProfile / GitHubProfile  (CASCADE)
                     └── FK ──► Repository           (CASCADE from GitHubProfile)
User ── FK ──► Project ── FK ──► Repository          (Project: CASCADE on user, SET_NULL on repo)
```

`Project` survives repo deletion (deployment history outlasts upstream churn); `Repository` is scoped to `GitHubProfile` (not `User`) so disconnecting GitHub cleanly removes stale repo rows. See `plan.md` §3.

### Service modules over fat views

Views handle HTTP shape; business logic lives in `<app>/services/*.py`. **Cross-app calls go through services, not direct model imports.** Example: the GitHub callback view (`oauth/views.py`) calls `accounts.services.user_service.resolve_github` and `repositories.services.github_sync.sync_repositories` — it never reaches into `accounts/models.py` or `repositories/models.py` directly.

When adding logic, ask: "does this belong in a view, a serializer, or a service?" If it's anything beyond shape transformation, it's a service.

### Standard error envelope

All DRF error responses are reshaped by `core.exceptions.custom_exception_handler` into:

```json
{ "error": { "code": "...", "message": "...", "detail": ... } }
```

Custom exceptions live in `core/exceptions.py` (e.g., `GitHubNotConnected` → 409, `OAuthError` → 400). For non-exception error responses, use `core.responses.error_response(code, message, status_code, detail=None)`. Don't return raw `{"detail": "..."}` — it bypasses the envelope shape the frontend depends on.

### App boundaries

| App | Owns |
|---|---|
| `core` | Pagination, exception handler, request-ID middleware, healthz/readyz |
| `accounts` | `User` model (email-only, `AUTH_USER_MODEL`), JWT issuance/refresh/logout, `/auth/me`, `user_service` (OAuth identity resolution) |
| `oauth` | `GoogleProfile` + `GitHubProfile` + `AbstractOAuthProfile`, Fernet token crypto, OAuth start/callback views, provider service modules (`google.py`, `github.py`, `state.py`) |
| `repositories` | `Repository` model, GitHub API client + sync service, list endpoint, manual sync trigger |
| `projects` | `Project` model, list endpoint, deploy placeholder (frontend toast, no backend call) |

URLs are mounted under `/api/v1/` (see `backend/config/urls.py`).

### Frontend data flow

- **Server state** via React Query. Cache keys: `['me']`, `['repositories']`, `['projects']`. Mutations invalidate the relevant key (e.g., `useSyncRepositories` invalidates `['repositories']`).
- **Auth**: `frontend/src/lib/api.ts` is an axios instance with two interceptors — a request-side bearer injector and a response-side 401 handler that single-flight-refreshes the access token (queues concurrent failed requests, retries them once refresh completes). Don't bypass this client for authenticated calls.
- **Login**: `LoginPage` sets `window.location` to `${API_BASE}/oauth/<provider>/start` (full browser nav, not XHR). After callback, the backend redirects to `/auth/complete#access=<jwt>&intent=login`; `AuthComplete` reads the fragment, stores the token in memory, and routes to `/`.

## Conventions to follow

- **Test fixtures live in `backend/conftest.py`** — `user`, `other_user`, `api_client` (pre-authenticated), `other_api_client`, `unauth_client`, `google_profile`, `github_profile`. Use these instead of building users by hand in tests.
- **Pagination** is offset-based via `core.pagination.StandardLimitOffsetPagination` (default 20, max 100). All paginated list views must have a deterministic `ORDER BY` (see `Repository.Meta.ordering = ["-github_pushed_at", "id"]`).
- **Ruff** is configured in `ruff.toml` at the repo root with deliberate ignores (E501 — formatter handles it; B008 — Django pattern; RUF012 — DRF idiom). Don't add `# noqa` for these; if a new ignore is needed, add it to `ruff.toml` instead.
- **Frontend access token is module-scoped state**, not React state and not `localStorage`. The accessor pattern (`getAccessToken` / `setAccessToken` / `subscribeToken`) is in `frontend/src/lib/authStore.ts`.
- **Pyright/Pylance** is configured for django-stubs (see `backend/pyproject.toml` `[tool.pyright]`). ORM-aware types resolve through the venv — if you see "X has no attribute objects" warnings, the editor isn't pointed at `backend/venv/`.

## Where to read more

| Doc | When to read |
|---|---|
| [`plan.md`](plan.md) | Architecture decisions and rationale. Authoritative — read before changing data-model or auth shape. |
| [`OAUTH_FLOW.md`](OAUTH_FLOW.md) | End-to-end OAuth + JWT control/data flow. |
| [`OIDC.md`](OIDC.md) | OIDC primer (Google's id_token, JWKS, claims). |
| [`OAUTH_DOCS.md`](OAUTH_DOCS.md) | Setting up Google Cloud / GitHub OAuth Apps. |
| [`CHECKLIST.md`](CHECKLIST.md) | What's done vs. pending — especially §15 (provider app registration) and §16 (deployment). |
| `backend/README.md` / `frontend/README.md` | Per-stack dev notes (URL map, npm scripts, conventions). |
