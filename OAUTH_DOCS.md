# OAuth Provider Setup — GitHub & Google

Step-by-step instructions to register OAuth applications with GitHub and Google for this project. Steps are derived from the official 2026 documentation (sources at bottom). Values match what's already in `backend/.env` and the decisions locked in `plan.md`.

## Goal

Populate four blank slots in `backend/.env`:

```
GITHUB_OAUTH_CLIENT_ID=
GITHUB_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
```

The redirect URIs and scopes are already chosen and committed to settings; the only manual work is registering each app and pasting back the issued credentials.

---

## 1. GitHub OAuth App

### Project values to use

| Field | Value |
|---|---|
| Application name | `Repo-Manage (dev)` (informational) |
| Homepage URL | `http://localhost:5173` |
| Application description | *optional* |
| Authorization callback URL | `http://localhost:8000/api/v1/oauth/github/callback` |
| Enable Device Flow | **unchecked** |
| Scopes requested at authorize time (not configured here — sent in the URL by the backend) | `read:user`, `repo` |

### Steps

1. Sign in to GitHub. Click your **profile picture (top right) → Settings**.
2. Left sidebar: **Developer settings**.
3. Left sidebar: **OAuth Apps**.
4. Click **New OAuth App** (or **Register a new application** if this is your first one). Direct link: <https://github.com/settings/applications/new>.
5. Fill in the form with the values above.
6. Leave **Enable Device Flow** unchecked — we use the standard authorization-code flow.
7. Click **Register application**.
8. On the resulting app page, copy the **Client ID** (visible at the top).
9. Click **Generate a new client secret**. Copy the value **immediately** — GitHub shows the full secret exactly once. If you lose it, generate a new one.
10. Open `backend/.env` and paste:
    ```
    GITHUB_OAUTH_CLIENT_ID=<paste Client ID>
    GITHUB_OAUTH_CLIENT_SECRET=<paste Client Secret>
    ```

### Scopes — what each one grants

- **`read:user`** — *"Grants access to read a user's profile data."* Read-only access to name, login, avatar, public profile fields. Source of identity data we'll store in `GitHubProfile`.
- **`repo`** — *"Grants full access to public and private repositories including read and write access to code, commit statuses, repository invitations, collaborators, deployment statuses, and repository webhooks."* This is broader than strictly needed for MVP read flows; we accept the breadth per `plan.md` section 8 because (a) private repos are a meaningful product signal, and (b) future "Deploy to K8S" workflows will need write-equivalent power anyway.

### Notes

- An OAuth App has **exactly one callback URL**. For production, register a second OAuth App (`Repo-Manage (prod)`) instead of trying to share one across environments.
- "Only use information you consider public" — GitHub's reminder that OAuth Apps don't support fine-grained permissions like GitHub Apps do.
- GitHub Apps are an alternative with short-lived tokens and per-repo permissions. We're using OAuth Apps for MVP simplicity; GitHub Apps is a documented future-work consideration.

---

## 2. Google OAuth Client

### Project values to use

| Field | Value |
|---|---|
| Application type | **Web application** |
| Name | `Repo-Manage (dev)` |
| Authorized JavaScript origins | `http://localhost:5173` |
| Authorized redirect URIs | `http://localhost:8000/api/v1/oauth/google/callback` |
| Requested scopes | `openid`, `https://www.googleapis.com/auth/userinfo.email`, `https://www.googleapis.com/auth/userinfo.profile` |

### Steps — OAuth consent screen (one-time per project)

1. Open <https://console.cloud.google.com/>.
2. Top bar: **select an existing project** or **create one** (e.g., `repo-manage-dev`).
3. Navigation menu → **APIs & Services → OAuth consent screen** (in newer console UI: **Google Auth Platform → Branding**).
4. Choose **External** user type (use **Internal** only if you have a Google Workspace org and want to restrict to it).
5. Fill in the consent screen:
   - **App name:** `Repo-Manage`
   - **User support email:** your email
   - **Developer contact email:** your email
6. **Scopes step:** add the three scopes above. All three are **non-sensitive** — no Google verification needed.
7. **Test users step:** add your own email address. External apps in **Testing** mode only allow listed test users to sign in (100-user cap, refresh tokens expire after 7 days).
8. Save and continue.

### Steps — create the OAuth client (the actual credentials)

9. Navigation menu → **APIs & Services → Credentials** (newer UI: **Google Auth Platform → Clients**).
10. Click **CREATE CLIENT** (or **CREATE CREDENTIALS → OAuth client ID** in older menus).
11. **Application type:** Web application.
12. **Name:** `Repo-Manage (dev)`.
13. **Authorized JavaScript origins:** add `http://localhost:5173`.
14. **Authorized redirect URIs:** add `http://localhost:8000/api/v1/oauth/google/callback`.
15. Click **CREATE**.
16. A modal shows the **Client ID** and **Client Secret**. Click **Download JSON** *and/or* copy both values — the secret is only shown at creation time.
17. Open `backend/.env` and paste:
    ```
    GOOGLE_OAUTH_CLIENT_ID=<paste Client ID>
    GOOGLE_OAUTH_CLIENT_SECRET=<paste Client Secret>
    ```

### Redirect URI validation rules (2026)

Google's validator enforces these for every redirect URI you add:

- **HTTPS required**, except `localhost` and `127.0.0.1` (these are exempt — that's why our local URL works).
- No raw IP addresses (except localhost).
- Domain must be on the public suffix list (no `.local`, no internal-only TLDs).
- No path traversal (`/..`), no userinfo (`user:pass@host`), no fragments, no wildcards, no invalid percent-encoding.
- Must match the redirect URI sent in the OAuth request **exactly** (scheme, host, port, path).

Our value `http://localhost:8000/api/v1/oauth/google/callback` passes under the localhost exemption.

### Why these scopes

- **`openid`** — enables OpenID Connect; gets us the `sub` claim, which is Google's stable user identifier and what we'll store as `google_sub` (`plan.md` section 6).
- **`userinfo.email`** — the user's verified primary email.
- **`userinfo.profile`** — name and picture URL.

We deliberately request nothing broader because Google is identity-only in this design (`plan.md` section 1) — no Google APIs are called after sign-in.

### Notes

- **Testing vs Published:** Apps in **Testing** mode are limited to listed test users (100 max) and refresh tokens expire after 7 days. For production, **publish** the app on the consent screen page. Publishing requires verification only if you use sensitive or restricted scopes — we don't, so publishing is one click.
- The downloaded `client_secret_<id>.json` is sensitive. Treat it like a database password — never commit it.

---

## 3. Verify both are configured

After populating `backend/.env`, run this from `backend/` to confirm both clients are loaded:

```
DJANGO_SETTINGS_MODULE=config.settings venv/bin/python -c "from django.conf import settings; print('GitHub configured:', bool(settings.GITHUB_OAUTH['CLIENT_ID']) and bool(settings.GITHUB_OAUTH['CLIENT_SECRET'])); print('Google configured:', bool(settings.GOOGLE_OAUTH['CLIENT_ID']) and bool(settings.GOOGLE_OAUTH['CLIENT_SECRET']))"
```

Both lines should print `True`.

---

## 4. Production setup (not for MVP — recorded for later)

When this project is deployed, **register a second OAuth App / Client per provider** for the prod environment. Reasons:

- One callback URL per GitHub OAuth App.
- Google clients tie a fixed set of redirect URIs and JS origins.
- Compromise of dev credentials must not yield prod access.

Naming convention: `<app-name> (dev)` and `<app-name> (prod)`. Store prod credentials in the secrets manager you choose (Vault / AWS Secrets Manager / Doppler), never in a committed `.env`. `plan.md` section 5 covers the broader token storage policy.

---

## Sources (official 2026 documentation)

- [GitHub Docs — Creating an OAuth app](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app)
- [GitHub Docs — Scopes for OAuth Apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps)
- [GitHub — Register a new OAuth application (direct link)](https://github.com/settings/applications/new)
- [Google Identity — Using OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Google Cloud Help — Setting up OAuth 2.0](https://support.google.com/cloud/answer/6158849)
- [Google Cloud Help — Manage OAuth Clients](https://support.google.com/cloud/answer/15549257)
