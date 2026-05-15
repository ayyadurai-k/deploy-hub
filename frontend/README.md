# Frontend

Vite + React + TypeScript. Currently the default Vite scaffold — auth flow, routing, and dashboard are not yet wired (see [`../CHECKLIST.md`](../CHECKLIST.md) §11–13).

## Setup

```bash
# From this directory (frontend/):
npm install
cp ../.env.example .env       # then trim to just the VITE_* vars
npm run dev                   # → http://localhost:5173
```

## Environment variables

| Var | Default | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Backend base URL. Used by API client. |

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Production build into `dist/` |
| `npm run preview` | Preview the production build |
| `npm run lint` | ESLint |

## Conventions (when we wire them up)

- **Server state via React Query** (`@tanstack/react-query`). Cache key prefixes: `['me']`, `['repositories']`, `['projects']`. Mutations invalidate the relevant prefix.
- **Client/UI state** stays in `useState` / `useReducer` locally — no global state library.
- **Access token in memory only** (a module-scoped variable behind a `getAccessToken()` accessor). Never `localStorage`.
- **Refresh handled by an axios interceptor** that catches 401, calls `/auth/refresh`, retries the original request. In-flight refresh is shared across pending requests.

## Auth callback flow (when wired)

After OAuth login, the backend redirects the browser to `/auth/complete#access=<jwt>&intent=login`. The `<AuthComplete />` route:
1. Reads the access token from `window.location.hash`.
2. Clears the hash (`history.replaceState`).
3. Stores the token in the in-memory store.
4. Navigates to `/dashboard`.

The refresh token rides along automatically as an httpOnly cookie set by the backend.

## See also

- [`../OAUTH_FLOW.md`](../OAUTH_FLOW.md) — full OAuth + JWT design.
- [`../CHECKLIST.md`](../CHECKLIST.md) — what's wired vs. pending.
