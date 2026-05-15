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
- [ ] Root `README.md` (run instructions, env vars, ports)
- [ ] `.gitignore` covers `.env`, `__pycache__`, `node_modules`, `dist/`
- [ ] `.env.example` at repo root listing every required env var
- [ ] License file (if applicable)
- [ ] Editor config (`.editorconfig`)
- [ ] Pre-commit hooks (`ruff`, `black`, `eslint`, `prettier`)

---

## 2. Backend — Project Scaffold

- [x] Django project (`config/`) created
- [x] `accounts` app created
- [x] `oauth` app created
- [x] `repositories` app created
- [x] `projects` app created
- [x] `core` app/package created (pagination, permissions, exceptions, responses)
- [x] `requirements.txt` pinned
- [ ] `settings.py` split into `base` / `dev` / `prod`
- [x] `INSTALLED_APPS` includes all four apps + `core`
- [x] `AUTH_USER_MODEL = "accounts.User"` set
- [ ] `DATABASES` reads from env (Postgres in dev/prod, SQLite optional for tests)
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
- [ ] Services: `user_service.create_or_get_for_provider(...)`
- [ ] Tests: model, manager, `/me`, refresh, logout

---

## 4. Backend — `oauth` App

- [x] `AbstractOAuthProfile` model
- [x] `GoogleProfile` model (`google_sub` unique, encrypted tokens)
- [x] `GitHubProfile` model (`github_user_id` unique, sync metadata)
- [x] `token_crypto.encrypt` / `decrypt` (Fernet)
- [x] `oauth/admin.py` registers both profiles
- [x] Initial migration generated
- [ ] `/api/v1/oauth/google/start` view (state cookie, redirect to Google)
- [ ] `/api/v1/oauth/google/callback` view (code exchange, `id_token` verify via JWKS, identity resolution, JWT issuance)
- [ ] `/api/v1/oauth/github/start` view (state cookie, redirect to GitHub)
- [ ] `/api/v1/oauth/github/callback` view (code exchange, `/user` fetch, identity resolution, JWT issuance, enqueue first sync)
- [x] `state` cookie helper (signed, short-lived, single-use)
- [x] `intent=login|link` handling in state payload
- [ ] Link-collision branch returns `409`
- [x] `oauth_service.exchange_code_google(...)`
- [x] `oauth_service.exchange_code_github(...)`
- [x] `oauth_service.verify_google_id_token(...)`
- [ ] Tests: encrypt/decrypt roundtrip, state CSRF defense, login path, link path, collision path

---

## 5. Backend — JWT Layer

- [x] `djangorestframework-simplejwt` installed
- [x] Access token TTL = 15 min
- [x] Refresh token TTL = 14 days
- [x] Refresh-token rotation enabled
- [x] Refresh-token blacklist app installed and migrated
- [x] Custom `IssueJWTPair` service used by OAuth callbacks
- [x] Refresh cookie: `httpOnly`, `Secure`, `SameSite=Strict`, path-scoped
- [ ] SPA-redirect-with-fragment delivery of access token on callback
- [ ] Reuse-detection revocation path tested

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
- [ ] Auto-sync on first GitHub link
- [x] `409` when `GitHubProfile` missing
- [x] Bounded page count for MVP
- [ ] Tests: sync upsert, sync re-run idempotent, missing profile → 409, pagination

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
- [ ] Tests: create, list scope per user, repo unlink survives, deploy placeholder

---

## 8. Backend — `core` / Cross-Cutting

- [x] `core/pagination.py` — project-wide `LimitOffsetPagination` defaults
- [ ] `core/permissions.py` — `IsAuthenticated` default
- [x] `core/exceptions.py` — custom handler with consistent error envelope
- [x] `core/responses.py` — helpers for `{ error: { code, message, detail } }`
- [x] DRF `DEFAULT_AUTHENTICATION_CLASSES` = SimpleJWT
- [x] DRF `DEFAULT_PERMISSION_CLASSES` = `IsAuthenticated`
- [x] DRF `EXCEPTION_HANDLER` wired to `core.exceptions`
- [ ] Structured logging (`structlog`) configured to JSON in prod
- [x] Request ID middleware
- [ ] Rate-limit throttle classes (per-user, per-IP)
- [x] CORS middleware ordered correctly
- [ ] CSRF disabled on `/api/` (JWT-only); enabled on admin

---

## 9. Backend — Tests & QA

- [ ] `pytest` + `pytest-django` installed
- [ ] `conftest.py` fixtures: `user`, `google_user`, `github_user`, `api_client`
- [ ] Coverage > 80% on services and views
- [ ] Migration round-trip test (`makemigrations --check`)
- [ ] `ruff` / `black` clean
- [ ] `mypy` (or `pyright`) clean on services

---

## 10. Frontend — Foundation

- [x] Vite + React + TypeScript scaffold
- [x] `package.json` with base deps
- [x] `tsconfig.json` configured
- [ ] `axios` (or `fetch` wrapper) installed
- [ ] `@tanstack/react-query` installed
- [ ] `react-router-dom` installed
- [ ] `zod` for response parsing
- [ ] UI primitives (Tailwind / shadcn / Radix — pick one)
- [ ] `.env.example` for `VITE_API_BASE_URL`
- [ ] App shell layout (header, content, toast container)
- [ ] Global error boundary
- [ ] Theming / dark mode toggle (optional)

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
- [ ] Loading skeleton

---

## 13. Frontend — Projects

- [ ] `<ProjectsPage />` route
- [ ] `useProjects()` list hook
- [ ] `<CreateProjectModal />` (name + repo picker)
- [ ] Repo picker autocomplete from `useRepositories()`
- [ ] Create / update / delete mutations with cache invalidation
- [ ] `<ProjectDetail />` route
- [ ] "Deploy to K8S" button shows toast "coming soon"
- [ ] Unlinked-repo state ("repo no longer available") rendered cleanly

---

## 14. Frontend — Tests & QA

- [ ] `vitest` configured
- [ ] React Testing Library installed
- [ ] Tests: `<LoginPage />`, `<AuthComplete />` fragment parsing
- [ ] Tests: 401 → refresh interceptor
- [ ] Tests: repository list pagination
- [ ] Tests: project create / delete
- [ ] `eslint` clean
- [ ] `tsc --noEmit` clean
- [ ] Playwright / Cypress smoke test for full login → dashboard flow

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

## 16. Infrastructure & Deployment

- [ ] `docker-compose.yml` (backend, db, frontend)
- [ ] Backend `Dockerfile`
- [ ] Frontend `Dockerfile`
- [ ] Postgres container with persistent volume
- [ ] `Makefile` / `justfile` with `make dev` / `make test` / `make migrate`
- [ ] Production deploy target chosen (Fly.io / Railway / ECS / k8s)
- [ ] Production Postgres provisioned
- [ ] `FERNET_KEY` stored in production secrets manager
- [ ] OAuth secrets stored in production secrets manager
- [ ] HTTPS / TLS terminated at reverse proxy
- [ ] Cookie `Secure` flag verified in prod

---

## 17. CI / CD

- [ ] GitHub Actions workflow created
- [ ] Job: backend lint (`ruff`, `black --check`)
- [ ] Job: backend type-check (`mypy` / `pyright`)
- [ ] Job: backend tests (`pytest` against Postgres service)
- [ ] Job: `manage.py makemigrations --check`
- [ ] Job: frontend lint (`eslint`)
- [ ] Job: frontend type-check (`tsc --noEmit`)
- [ ] Job: frontend tests (`vitest`)
- [ ] Job: docker build (both images)
- [ ] Branch protection on `main` requires all checks green

---

## 18. Observability & Ops

- [ ] Sentry DSN wired (backend + frontend)
- [ ] Structured request logs to stdout
- [ ] `/healthz` and `/readyz` wired in deploy probes
- [ ] DB backup strategy documented
- [ ] Key-rotation runbook for `FERNET_KEY` (`MultiFernet` swap)

---

## 19. Documentation

- [x] `plan.md`
- [x] `OAUTH_FLOW.md`
- [x] `OIDC.md`
- [x] `OAUTH_DOCS.md`
- [x] `CHECKLIST.md` (this file)
- [ ] Root `README.md`
- [ ] `backend/README.md` (local dev setup)
- [ ] `frontend/README.md` (local dev setup)
- [ ] API reference (OpenAPI schema via `drf-spectacular`)
- [ ] Architecture diagram (system context, container, sequence for login)

---

## 20. Open Decisions (from `plan.md` §Open items)

- [ ] API versioning mechanism — confirm path-based `/api/v1/`
- [ ] Error response standard — DRF default vs. RFC 7807
- [ ] Logging stack — `structlog` + Sentry?
- [ ] Production deployment target chosen
- [ ] CI gates list finalized
- [ ] Rate-limit policy finalized
- [ ] CSRF posture confirmed (off for `/api/`, on for admin)
