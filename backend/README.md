# Backend

Django 6 + DRF + SimpleJWT. Five apps + one core package.

## Apps

| App | Owns |
|---|---|
| `core` | Pagination, exception handler, request-ID middleware, health endpoints. |
| `accounts` | `User` model, JWT issuance/refresh/logout, `/auth/me`, `user_service` (OAuth identity resolution). |
| `oauth` | `GoogleProfile` + `GitHubProfile` models, Fernet token encryption, OAuth start/callback views, provider service modules (state, google, github). |
| `repositories` | `Repository` model, GitHub client + sync service, list endpoint, manual sync trigger. |
| `projects` | `Project` model, CRUD endpoint, deploy-to-K8S placeholder. |

## Setup

```bash
# From this directory (backend/):
python -m venv venv
./venv/bin/pip install -U pip
./venv/bin/pip install -r requirements.txt
cp ../.env.example .env   # then fill in the values
./venv/bin/python manage.py migrate
./venv/bin/python manage.py createsuperuser
./venv/bin/python manage.py runserver 0.0.0.0:8000
```

## Environment variables

See `../.env.example` at the repo root. The required ones for local dev:

| Var | Notes |
|---|---|
| `DJANGO_SECRET_KEY` | Any unpredictable string. Generator command in `.env.example`. |
| `FERNET_KEY` | 32-byte URL-safe base64 key. Generator command in `.env.example`. |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | From Google Cloud Console. |
| `GITHUB_OAUTH_CLIENT_ID` / `GITHUB_OAUTH_CLIENT_SECRET` | From GitHub Developer Settings. |
| `SPA_AUTH_COMPLETE_URL` | Where to redirect after OAuth callback. Defaults to `http://localhost:5173/auth/complete`. |

## Tests

```bash
./venv/bin/pytest                # full suite
./venv/bin/pytest accounts/      # one app
./venv/bin/pytest -k oauth       # by keyword
```

Fixtures live in [`conftest.py`](conftest.py): `user`, `other_user`, `api_client`, `other_api_client`, `unauth_client`, `google_profile`, `github_profile`.

## URL map (currently wired)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/healthz` | Liveness |
| GET | `/api/v1/readyz` | Readiness (DB ping) |
| GET | `/api/v1/auth/me` | Current user |
| POST | `/api/v1/auth/refresh` | Rotate refresh + return new access |
| POST | `/api/v1/auth/logout` | Blacklist refresh, clear cookie |
| GET | `/api/v1/oauth/{google,github}/start` | Begin login flow (browser nav) |
| POST | `/api/v1/oauth/{google,github}/start` | Begin link flow (authenticated XHR) |
| GET | `/api/v1/oauth/{google,github}/callback` | Provider redirects browser here |
| GET | `/api/v1/repositories/` | Paginated list (409 without `GitHubProfile`) |
| POST | `/api/v1/repositories/sync` | Manual sync trigger |
| CRUD | `/api/v1/projects/` | Full CRUD, scoped to `request.user` |
| POST | `/api/v1/projects/<id>/deploy` | 501 placeholder |

Admin lives at `/admin/`.

## Linting

```bash
./venv/bin/python -m ruff check .
./venv/bin/python -m ruff format .
```

Config in [`../ruff.toml`](../ruff.toml).

## Conventions

- **Service modules over fat views.** Views handle HTTP shape; logic lives in `<app>/services/*.py`.
- **Cross-app calls go through services**, never direct model imports across app boundaries when the call is non-trivial.
- **Standard error envelope** on all DRF responses: `{ "error": { "code": "...", "message": "...", "detail"?: ... } }` — produced by `core.exceptions.custom_exception_handler`.
- **Provider tokens are always Fernet-encrypted** via `oauth.services.token_crypto`. Callers use `set_access_token` / `get_access_token` on profile models.
