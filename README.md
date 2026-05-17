# Deploy Hub

A small deployment-platform MVP: sign in with Google or GitHub, browse your GitHub repositories, and trigger a *Deploy to K8S* placeholder. Built as a screening project to demonstrate end-to-end OAuth, JWT session management, and production deployment.

**Live:** <https://deploy-hub.ayyadurai.online>

---

## Stack

| Layer | Choice |
|---|---|
| Backend | Django 6 · Django REST Framework · `djangorestframework-simplejwt` |
| Database | PostgreSQL (Supabase in production, local Postgres in dev) |
| Frontend | Vite · React 19 · TypeScript · Tailwind v4 · React Query · React Router |
| Auth | OIDC (Google) · OAuth Apps (GitHub) |
| Encryption | `cryptography` Fernet for provider tokens at rest |
| Deploy | AWS Lightsail (Amazon Linux 2023) + nginx + gunicorn + Let's Encrypt |
| CI/CD | GitHub Actions — push to `live` triggers deploy |

## Design highlights

- **Two-layer auth model.** Provider OAuth (server-side only, tokens encrypted with Fernet) is fully separated from the app's session JWT (access token in browser memory ~15 min, refresh token in `httpOnly` cookie ~14 days with rotation + reuse detection). The two only meet inside the OAuth callback view. Full design: [`docs/OAUTH_FLOW.md`](docs/OAUTH_FLOW.md).
- **Identity-as-tuple, not email.** Users are keyed on `(provider, provider_user_id)`, never email. Same email across Google and GitHub creates two separate `User` rows by design — no auto-merge, no account-takeover risk via email control. See [`plan.md`](plan.md) §2.
- **Asymmetric provider roles.** Google = identity-only (OIDC `id_token` verified against JWKS, no API calls afterward). GitHub = identity + data (we fetch and sync repos). Two physical profile tables instead of a polymorphic one because the lifecycles and attached state are genuinely different.
- **Standard error envelope.** All DRF responses are reshaped to `{ "error": { "code, "message", "detail" } }` by `core.exceptions.custom_exception_handler` — the frontend has a single error-rendering path.
- **Bounded sync.** Manual sync from the dashboard; auto-runs once on dashboard mount when a GitHub profile is present. Capped at 5 pages × 100 = 500 repos per sync to keep request times predictable.

## Prerequisites

- Python 3.12+
- Node 20+
- PostgreSQL 14+ (running locally)
- Google OAuth client + GitHub OAuth App ([`OAUTH_DOCS.md`](OAUTH_DOCS.md))

## Quick start

```bash
# 1. Copy and fill in environment files
cp .env.example backend/.env
cp .env.example frontend/.env
# Edit backend/.env — generate FERNET_KEY + DJANGO_SECRET_KEY (see file
# comments for generator commands), fill in OAuth client IDs/secrets,
# point DB_* at your local Postgres.

# 2. Install dependencies
make install

# 3. Apply migrations + create a superuser
make migrate
make superuser

# 4. Run the dev servers (two terminals)
make backend     # → http://localhost:8000
make frontend    # → http://localhost:5173
```

Then visit <http://localhost:5173>, click *Continue with GitHub*, and you should land on the dashboard with your repos synced.

## Local commands

| Task | Command |
|---|---|
| Run tests | `make test` |
| Lint backend | `make lint` |
| Format backend | `make format` |
| New migration | `make makemigrations` |
| Django shell | `make shell` |
| Frontend build | `cd frontend && npm run build` |
| Frontend lint | `cd frontend && npm run lint` |

## Repository layout

```
.
├── backend/                    Django project — 4 apps + shared core
│   ├── accounts/               User model, JWT issue/refresh/logout, /auth/me
│   ├── oauth/                  Provider profiles, Fernet crypto, OAuth views
│   ├── repositories/           Repository model, GitHub client + sync service
│   └── core/                   Pagination, exception handler, middleware
├── frontend/                   Vite + React 19 + TS SPA
│   └── src/
│       ├── components/         AppShell, AuthGuard, Brand
│       ├── lib/                axios client, React Query hooks, auth store
│       └── pages/              LoginPage, HomePage, AuthComplete
├── docs/                       Architecture references
│   ├── OAUTH_FLOW.md           End-to-end OAuth + JWT control/data flow
│   └── OIDC.md                 OpenID Connect primer
├── plan.md                     Architecture decisions and trade-offs
├── OAUTH_DOCS.md               Google / GitHub OAuth-app setup walkthrough
└── .github/workflows/          CI/CD (`deploy-live.yml`)
```

## Authentication flow at a glance

```
Browser ──[1]──▶ /api/v1/oauth/<provider>/start ──302──▶ Google/GitHub
                                                              │
                                          ←── 302 ?code=… ────┘
                                          │
Browser ──[2]──▶ /api/v1/oauth/<provider>/callback ────────────┐
                          │                                    │
                          │ exchange code for tokens (server)  │
                          │ verify identity                    │
                          │ resolve/create User row            │
                          │ encrypt + store provider token     │
                          │ mint app JWT pair                  │
                          ▼                                    │
                  302 → /auth/complete#access=<jwt>            │
Browser ──[3]──▶ SPA reads JWT from URL fragment, stores in memory,
                  starts hitting /api/v1/* with Authorization: Bearer
```

Full flow doc: [`docs/OAUTH_FLOW.md`](docs/OAUTH_FLOW.md). OIDC primer: [`docs/OIDC.md`](docs/OIDC.md).

## Scope

What this MVP **does**:

- Two OAuth providers — Google (sign in with) and GitHub (sign in with, plus repository sync).
- Persist user identity in Postgres, encrypted provider tokens at rest.
- Paginated repo list (10 per page) with auto-sync on dashboard load and a manual Sync button.
- Placeholder "Deploy to K8S" button on each repo row.

What this MVP **deliberately does not** do (documented in [`plan.md`](plan.md)):

- Account linking across providers — out of scope; two same-email sign-ins produce two `User` rows.
- Real Kubernetes deployment — the Deploy button is a frontend toast only.
- Webhook-driven or periodic repo sync — manual / on-mount only.
- Detection of deleted-on-GitHub repos — stale rows remain.

## Architecture reading order

1. [`plan.md`](plan.md) — locked architecture decisions and rationale.
2. [`docs/OAUTH_FLOW.md`](docs/OAUTH_FLOW.md) — end-to-end OAuth + JWT control/data flow.
3. [`OAUTH_DOCS.md`](OAUTH_DOCS.md) — provider OAuth-app registration walkthrough.
4. [`docs/OIDC.md`](docs/OIDC.md) — short OIDC primer for context on the Google side.
5. `backend/README.md`, `frontend/README.md` — per-stack dev notes.

## License

[MIT](LICENSE)
