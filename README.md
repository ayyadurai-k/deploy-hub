# repo-manage

A small deployment platform: sign in with Google or GitHub, browse your repos, create projects, hit "Deploy to K8S" (placeholder for now).

> **Status:** MVP backend in progress. Frontend scaffold present, auth flow not yet wired. See [`CHECKLIST.md`](CHECKLIST.md) for the current punch list.

## Stack

- **Backend:** Django 6 · DRF · djangorestframework-simplejwt · Fernet token-at-rest encryption · authlib (OIDC) · Postgres in prod / SQLite in dev
- **Frontend:** Vite · React · TypeScript (React Query / router not yet wired)
- **OAuth providers:** Google (OIDC, identity-only) + GitHub OAuth Apps (identity + repo data)

## Repository layout

```
.
├── backend/        Django project (config + 5 apps: accounts, oauth, repositories, projects, core)
├── frontend/       Vite + React + TS scaffold
├── plan.md         Locked architecture decisions
├── OAUTH_FLOW.md   End-to-end OAuth + JWT design (read this first)
├── OIDC.md         Beginner-friendly OIDC primer
├── OAUTH_DOCS.md   Provider app setup notes (Google Cloud / GitHub OAuth Apps)
├── CHECKLIST.md    Ship-readiness tracker
└── Makefile        Common targets — run `make help`
```

## Prerequisites

- Python 3.12+
- Node 20+
- Postgres 15+ (optional for dev — SQLite is the default)
- Google OAuth client + GitHub OAuth App (see `OAUTH_DOCS.md`)

## Quick start

```bash
# 1. Copy environment files
cp .env.example backend/.env
cp .env.example frontend/.env

# Fill in FERNET_KEY (see backend/.env comment for generator) and OAuth client IDs/secrets.

# 2. Install everything
make install

# 3. Run migrations + create a superuser
make migrate
make superuser

# 4. Run the dev servers (two terminals)
make backend     # → http://localhost:8000
make frontend    # → http://localhost:5173
```

## Local development

| Task | Command |
|---|---|
| Run tests | `make test` |
| Lint backend | `make lint` |
| Format backend | `make format` |
| New migration | `make makemigrations` |
| Django shell | `make shell` |
| List all targets | `make help` |

## Authentication flow (high-level)

Two completely separate auth layers — internalize this:

- **Layer 1 — Provider OAuth.** Backend ↔ Google/GitHub. Server-side only. Tokens stored Fernet-encrypted in the DB.
- **Layer 2 — App session JWT.** Browser ↔ Backend. Access token in memory (~15 min), refresh token in an httpOnly cookie (~14 days) with rotation + reuse detection.

The full design is in [`OAUTH_FLOW.md`](OAUTH_FLOW.md). Beginner OIDC primer in [`OIDC.md`](OIDC.md).

## Where to read next

| Doc | When |
|---|---|
| [`plan.md`](plan.md) | Architecture decisions and rationale. Start here. |
| [`OAUTH_FLOW.md`](OAUTH_FLOW.md) | End-to-end OAuth + JWT control/data flow. |
| [`OIDC.md`](OIDC.md) | If "OIDC" is new to you. |
| [`OAUTH_DOCS.md`](OAUTH_DOCS.md) | When setting up Google/GitHub OAuth apps. |
| [`CHECKLIST.md`](CHECKLIST.md) | What's done / what's left. |
| `backend/README.md` | Backend-specific dev notes. |
| `frontend/README.md` | Frontend-specific dev notes. |
