<!-- cspell:ignore OIDC Fernet simplejwt structlog healthz readyz djangorestframework -->

# Project Checklist — Deployment Platform MVP

Single source of truth for what's done and what's left. Tick items as they ship.

---

## 1. Repository & Tooling

- [x] Git repo initialized
- [x] `plan.md` written and locked
- [x] `OAUTH_FLOW.md` written
- [x] `OIDC.md` primer written
- [x] `OAUTH_DOCS.md` provider setup notes
- [x] Root `README.md` (run instructions, env vars, ports)
- [x] `.gitignore` covers `.env`, `__pycache__`, `node_modules`, `dist/`
- [x] `.env.example` at repo root listing every required env var

---

## 2. Backend — Project Scaffold

- [x] Django project (`config/`) created
- [x] `accounts` app created
- [x] `oauth` app created
- [x] `repositories` app created
- [x] `projects` app created
- [x] `core` app/package created (pagination, permissions, exceptions, responses)
- [x] `requirements.txt` pinned
- [x] `INSTALLED_APPS` includes all four apps + `core`
- [x] `AUTH_USER_MODEL = "accounts.User"` set
- [x] `SECRET_KEY` from env
- [x] `FERNET_KEY` from env, validated at startup
- [x] `DEBUG` from env
- [x] `ALLOWED_HOSTS` from env
- [x] `CORS_ALLOWED_ORIGINS` configured for SPA dev origin
- [x] Versioned URL mount: `path("api/v1/", include(...))`
- [x] `/healthz` endpoint
- [x] `/readyz` endpoint (DB check)

---

## 3. Backend — `accounts` App

- [x] `User` model (`AbstractBaseUser` + `PermissionsMixin`, email-only)
- [x] `UserManager` with `create_user` / `create_superuser`
- [x] `accounts/admin.py` registers `User`
- [x] Initial migration generated
- [x] `/api/v1/auth/me` view (returns current user)
- [x] `/api/v1/auth/refresh` view (rotating refresh)
- [x] `/api/v1/auth/logout` view (blacklist refresh, clear cookie)
- [x] `UserSerializer` (id, email, display_name, has_google, has_github)
- [x] Services: `user_service.resolve_google` / `resolve_github`
- [x] Tests: model, manager, `/me`, refresh, logout

---

## 4. Backend — `oauth` App

- [x] `AbstractOAuthProfile` model
- [x] `GoogleProfile` model (`google_sub` unique, encrypted tokens)
- [x] `GitHubProfile` model (`github_user_id` unique, sync metadata)
- [x] `token_crypto.encrypt` / `decrypt` (Fernet)
- [x] `oauth/admin.py` registers both profiles
- [x] Initial migration generated
- [x] `/api/v1/oauth/google/start` view (state cookie, redirect to Google) — GET (login) + POST (link)
- [x] `/api/v1/oauth/google/callback` view (code exchange, `id_token` verify via JWKS, identity resolution, JWT issuance)
- [x] `/api/v1/oauth/github/start` view (state cookie, redirect to GitHub) — GET (login) + POST (link)
- [x] `/api/v1/oauth/github/callback` view (code exchange, `/user` fetch, identity resolution, JWT issuance, first-link sync)
- [x] `state` cookie helper (signed, short-lived, single-use)
- [x] `intent=login|link` handling in state payload
- [x] Link-collision branch returns SPA redirect with `error=link_collision`
- [x] `oauth_service.exchange_code_google(...)`
- [x] `oauth_service.exchange_code_github(...)`
- [x] `oauth_service.verify_google_id_token(...)`
- [x] Tests: encrypt/decrypt roundtrip, state CSRF defense, login path, link path, collision path

---

## 5. Backend — JWT Layer

- [x] `djangorestframework-simplejwt` installed
- [x] Access token TTL = 15 min
- [x] Refresh token TTL = 14 days
- [x] Refresh-token rotation enabled
- [x] Refresh-token blacklist app installed and migrated
- [x] Custom `IssueJWTPair` service used by OAuth callbacks
- [x] Refresh cookie: `httpOnly`, `Secure`, `SameSite=Strict`, path-scoped
- [x] SPA-redirect-with-fragment delivery of access token on callback
- [x] Reuse-detection revocation path tested

---

## 6. Backend — `repositories` App

- [x] `Repository` model with `UniqueConstraint(github_profile, github_repo_id)`
- [x] `repositories/admin.py` registers model
- [x] Initial migration generated
- [x] `RepositorySerializer`
- [x] `RepositoryViewSet` (list, retrieve) at `/api/v1/repositories/`
- [x] Pagination: `LimitOffsetPagination`, deterministic `pushed_at DESC, id ASC`
- [x] `services/github_client.py` (paginated `/user/repos` fetch, token from `GitHubProfile`)
- [x] `services/github_sync.py` (idempotent upsert, status transitions, error capture)
- [x] `POST /api/v1/repositories/sync` manual trigger view
- [x] Auto-sync on first GitHub link
- [x] `409` when `GitHubProfile` missing
- [x] Bounded page count for MVP
- [x] Tests: sync upsert, sync re-run idempotent, missing profile → 409, pagination

---

## 7. Backend — `projects` App

- [x] `Project` model (FK user cascade, FK repo SET_NULL, slug, status)
- [x] `projects/admin.py` registers model
- [x] Initial migration generated
- [x] `ProjectSerializer`
- [x] `ProjectViewSet` (list, create, retrieve, update, destroy) at `/api/v1/projects/`
- [x] `UniqueConstraint(user, name)` enforced
- [x] `slug` auto-generated from `name`
- [x] `POST /api/v1/projects/<id>/deploy` placeholder returning `501` / canned payload
- [x] List filtered to `request.user`
- [x] Pagination: `LimitOffsetPagination`
- [x] Tests: create, list scope per user, repo unlink survives, deploy placeholder

---

## 8. Backend — `core` / Cross-Cutting

- [x] `core/pagination.py` — project-wide `LimitOffsetPagination` defaults
- [x] `core/exceptions.py` — custom handler with consistent error envelope
- [x] `core/responses.py` — helpers for `{ error: { code, message, detail } }`
- [x] DRF `DEFAULT_AUTHENTICATION_CLASSES` = SimpleJWT
- [x] DRF `DEFAULT_PERMISSION_CLASSES` = `IsAuthenticated`
- [x] DRF `EXCEPTION_HANDLER` wired to `core.exceptions`
- [x] Request ID middleware
- [x] CORS middleware ordered correctly

---

## 9. Backend — Tests & QA

- [x] `pytest` + `pytest-django` installed
- [x] `conftest.py` fixtures: `user`, `other_user`, `api_client`, `other_api_client`, `unauth_client`, `google_profile`, `github_profile`
- [x] Migration round-trip test (`makemigrations --check`)
- [x] `ruff` clean

---

## 10. Frontend — Foundation

- [x] Vite + React + TypeScript scaffold
- [x] `package.json` with base deps
- [x] `tsconfig.json` configured
- [x] `axios` installed
- [x] `@tanstack/react-query` installed
- [x] `react-router-dom` installed
- [x] Tailwind v4 (via `@tailwindcss/vite`)
- [x] `.env` with `VITE_API_BASE_URL`
- [x] App shell layout (header + content)

---

## 11. Frontend — Auth Flow

- [x] `<LoginPage />` with "Sign in with Google" + "Sign in with GitHub" buttons
- [x] Buttons set `window.location = <backend>/api/v1/oauth/<provider>/start`
- [x] `<AuthComplete />` route reads access token from URL fragment, stores in memory, clears fragment, redirects to `/`
- [x] In-memory access-token store (module-scoped, NOT `localStorage`)
- [x] `apiClient` injects `Authorization: Bearer …`
- [x] 401 interceptor calls `/auth/refresh`, retries pending request
- [x] Refresh-in-flight queueing (single refresh, fan-out of waiters)
- [x] `<AuthGuard />` redirects to `/login` if no access token
- [x] `useMe()` React Query hook (`['me']`)
- [x] Logout button calls `/auth/logout`, clears in-memory token, redirects

---

## 12. Frontend — Home Page (single authenticated page)

- [x] User details card (email, display name, linked-provider badges)
- [x] Connect-GitHub CTA when `/repositories/` returns 409
- [x] `useRepositories()` hook
- [x] Repo list (name, private badge, default branch, last push, link to GitHub)
- [x] "Sync" button triggers mutation, invalidates `['repositories']`
- [x] Sync success/error banner
- [x] `useProjects()` hook
- [x] Projects table (name, repo, status, action column)
- [x] "Deploy to K8S" button shows toast "coming soon"

---

## 15. OAuth App Registration (External)

- [x] Google Cloud Console: OAuth client created
- [x] Google: authorized redirect URI `http://localhost:8000/api/v1/oauth/google/callback`
- [ ] Google: production redirect URI added *(deferred — §16)*
- [x] Google: consent screen configured (scopes, app name, support email) — `openid email profile`, audience set to External, test user added
- [x] GitHub OAuth App created (dev)
- [x] GitHub: authorization callback URL `http://localhost:8000/api/v1/oauth/github/callback`
- [ ] GitHub: production callback URL added *(deferred — §16; new OAuth App required per GitHub's one-callback-per-app rule)*
- [x] Client IDs in `.env.example`
- [x] Client secrets in dev `.env` (NOT committed — confirmed in `.gitignore`)
- [x] **Bonus:** scopes expanded to `read:user user:email repo` to handle GitHub users with private primary email (fixes the silent "no verified email" error path)
- [x] **Bonus:** `User.email` unique constraint removed via migration `accounts.0002_alter_user_email` to allow two `User` rows for the same human across providers (locks `plan.md` §2)
- [x] End-to-end sign-in verified in local dev — Google ✓, GitHub ✓, repos synced ✓

---

## 16. AWS Deployment — Lightsail (`deploy-hub.ayyadurai.online`)

- [x] `Makefile` with `make dev` / `make test` / `make migrate`
- [x] Lightsail instance launched (`ap-south-1`, Amazon Linux 2023, 419 MiB RAM) — firewall opened for **TCP 80 + 443**
- [x] DNS: `deploy-hub.ayyadurai.online` → `3.7.143.78`
- [x] Python 3.12.13 installed via `dnf` on host
- [x] Frontend built **locally** with `VITE_API_BASE_URL=https://deploy-hub.ayyadurai.online/api/v1` and rsynced to `/home/ec2-user/deploy-hub/frontend/dist/` (skipped Node on host to dodge OOM on the 419 MiB instance)
- [x] Repo rsynced (no .git, no venv, no node_modules) to `/home/ec2-user/deploy-hub/`
- [x] Backend venv at `/home/ec2-user/deploy-hub/backend/venv`, `pip install -r requirements.txt` clean
- [x] `backend/.env` written on host (fresh `SECRET_KEY` + `FERNET_KEY` generated **on host**, mode 600, `DJANGO_DEBUG=False`, prod hostname in `ALLOWED_HOSTS`, `REFRESH_COOKIE_SECURE=True`, `CSRF_TRUSTED_ORIGINS` set)
- [x] `python manage.py migrate` clean
- [x] `python manage.py collectstatic` → 157 files in `backend/staticfiles/`
- [x] Backend served via gunicorn (2 workers, 60 s timeout, max-requests 1000 with jitter) under systemd unit `/etc/systemd/system/deploy-hub.service`, enabled
- [x] Frontend `dist/` served by nginx at `/`; `/static/` served by nginx from Django collected static; `/api/`, `/admin/` proxied to gunicorn at 127.0.0.1:8000
- [x] Let's Encrypt cert via certbot for `deploy-hub.ayyadurai.online`; nginx config rewritten to include 443 + 80→443 redirect; auto-renew installed
- [x] Google: production redirect URI `https://deploy-hub.ayyadurai.online/api/v1/oauth/google/callback` added to existing dev client
- [x] GitHub: new prod OAuth App `Deploy Hub (prod)` created with callback `https://deploy-hub.ayyadurai.online/api/v1/oauth/github/callback` (Client ID `Ov23lirrLEX9ti8RUni6`)
- [x] `backend/.env` placeholder `GITHUB_OAUTH_CLIENT_ID/SECRET` replaced with prod values
- [x] End-to-end Google + GitHub login verified on deploy-hub.ayyadurai.online — two `User` rows (Google + GitHub) per `plan.md` §2, GitHub first-sync pulled 120 repos with `sync=success`

---

## 19. Documentation

- [x] `plan.md`
- [x] `OAUTH_FLOW.md`
- [x] `OIDC.md`
- [x] `OAUTH_DOCS.md`
- [x] `CHECKLIST.md` (this file)
- [x] Root `README.md`
- [x] `backend/README.md` (local dev setup)
- [x] `frontend/README.md` (local dev setup)
