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
- [ ] `axios` (or `fetch` wrapper) installed
- [ ] `@tanstack/react-query` installed
- [ ] `react-router-dom` installed
- [ ] UI primitives (Tailwind is the simplest pick)
- [ ] `.env` with `VITE_API_BASE_URL`
- [ ] App shell layout (header + content)

---

## 11. Frontend — Auth Flow

- [ ] `<LoginPage />` with "Sign in with Google" + "Sign in with GitHub" buttons
- [ ] Buttons set `window.location = <backend>/api/v1/oauth/<provider>/start`
- [ ] `<AuthComplete />` route reads access token from URL fragment, stores in memory, clears fragment, redirects to `/dashboard`
- [ ] In-memory access-token store (module-scoped, NOT `localStorage`)
- [ ] `apiClient` injects `Authorization: Bearer …`
- [ ] 401 interceptor calls `/auth/refresh`, retries pending request
- [ ] Refresh-in-flight queueing (single refresh, fan-out of waiters)
- [ ] `<AuthGuard />` redirects to `/login` if no access token
- [ ] `useMe()` React Query hook (`['me']`)
- [ ] Logout button calls `/auth/logout`, clears in-memory token, redirects

---

## 12. Frontend — Dashboard / Repositories

- [ ] `<Dashboard />` route
- [ ] Empty-state "Connect GitHub" CTA when `has_github === false`
- [ ] `useRepositories({ limit, offset })` hook (`['repositories', params]`)
- [ ] Repository list rendering (name, private badge, default branch, last push)
- [ ] Pagination controls (prev / next / page size)
- [ ] "Sync" button triggers mutation, invalidates `['repositories']`
- [ ] Sync status indicator (`pending` / `in_progress` / `success` / `failure`)
- [ ] Error toast on sync failure

---

## 13. Frontend — Projects

- [ ] `<ProjectsPage />` route
- [ ] `useProjects()` list hook
- [ ] `<CreateProjectModal />` (name + repo picker)
- [ ] Repo picker autocomplete from `useRepositories()`
- [ ] Create / delete mutations with cache invalidation
- [ ] "Deploy to K8S" button shows toast "coming soon"

---

## 15. OAuth App Registration (External)

- [ ] Google Cloud Console: OAuth client created
- [ ] Google: authorized redirect URI `http://localhost:8000/api/v1/oauth/google/callback`
- [ ] Google: production redirect URI added
- [ ] Google: consent screen configured (scopes, app name, support email)
- [ ] GitHub OAuth App created
- [ ] GitHub: authorization callback URL `http://localhost:8000/api/v1/oauth/github/callback`
- [ ] GitHub: production callback URL added
- [ ] Client IDs in `.env.example`
- [ ] Client secrets in dev `.env` (NOT committed)

---

## 16. AWS Deployment (single EC2, simple)

- [x] `Makefile` with `make dev` / `make test` / `make migrate`
- [ ] EC2 instance launched + security group opened on the demo port
- [ ] Python 3.12 + Node 20 installed on host
- [ ] Repo cloned, `make install` + `make migrate` + `make superuser` run
- [ ] `backend/.env` populated on host (`SECRET_KEY`, fresh `FERNET_KEY`, OAuth creds, `DJANGO_ALLOWED_HOSTS=<ec2-host>`)
- [ ] `frontend/.env` set with `VITE_API_BASE_URL=http://<ec2-host>/api/v1`
- [ ] Backend served via `gunicorn config.wsgi:application`
- [ ] Frontend `npm run build` output served (nginx or Django staticfiles)
- [ ] Provider redirect URIs updated to the EC2 hostname
- [ ] End-to-end Google + GitHub login verified on the deployed URL

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
