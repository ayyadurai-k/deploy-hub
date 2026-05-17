<!-- cspell:ignore Fernet OIDC GOCSPX userinfo googleusercontent dropdown venv setdefault -->

# OAuth Provider Setup — GitHub & Google

> **Audience:** A developer setting up this project for the first time. You have a GitHub account and a Google account; you have not necessarily used GitHub's Developer Settings or Google Cloud Console before. Every click is spelled out. Steps verified against the official 2026 documentation — see [Sources](#sources) at the bottom.
>
> **What you'll have at the end:** Four populated env vars in `backend/.env` (`GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`) plus working sign-in flows for both providers in local dev.
>
> **Estimated time:** ~10 minutes for GitHub, ~20 minutes for Google (Google's consent-screen wizard takes longer).

---

## What we're filling in

The redirect URIs, scopes, and architecture are already chosen and committed to `backend/config/settings.py` and `plan.md`. Your only manual work is registering one OAuth app per provider and pasting the issued credentials into `backend/.env`:

```
# Already in .env.example — these four are blank and need values:
GITHUB_OAUTH_CLIENT_ID=
GITHUB_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
```

The redirect URIs the backend uses (you'll register these with each provider):

| Provider | Dev redirect URI |
|---|---|
| GitHub | `http://localhost:8000/api/v1/oauth/github/callback` |
| Google | `http://localhost:8000/api/v1/oauth/google/callback` |

> **Quick note before you start:** Don't add trailing slashes when registering these. Both providers do **exact string match** on redirect URIs, and our backend sends them without a trailing slash. A single extra `/` and you'll get `redirect_uri_mismatch` errors that are easy to miss.

---

## Part A — GitHub OAuth App (do this first; it's simpler)

GitHub has **two** developer products: **OAuth Apps** (older, simpler) and **GitHub Apps** (newer, more permissions). We use **OAuth Apps** — see `plan.md` §1 for the rationale. The UI for OAuth Apps is a single form; no wizard.

### A.1 — Open the OAuth Apps page

1. Sign in to GitHub.
2. Click your **profile picture** in the upper-right corner of any page.
3. Click **Settings** (in the dropdown menu).
4. In the **left sidebar**, scroll down and click **Developer settings**.
5. In the **left sidebar** of Developer settings, click **OAuth Apps**.
6. Click the green **New OAuth App** button (top-right). If this is your first OAuth App, the button may be labeled **Register a new application** — same thing.

> **Direct link** if you want to skip the navigation: <https://github.com/settings/applications/new>

### A.2 — Fill in the registration form

You'll see one form with four fields. Fill them in exactly:

| Field | What to enter | Notes |
|---|---|---|
| **Application name** | `Repo-Manage (dev)` | Shown to users on the consent screen. The `(dev)` suffix matters because you'll create a separate `(prod)` app later. |
| **Homepage URL** | `http://localhost:5173` | Must be a full URL with scheme. This is just the SPA's dev URL. |
| **Application description** *(optional)* | Anything, or leave blank | Shown to users on the consent screen. |
| **Authorization callback URL** | `http://localhost:8000/api/v1/oauth/github/callback` | **No trailing slash. `http` not `https`.** Must exactly match what the backend will send. |

Leave the **Enable Device Flow** checkbox **unchecked**. (Device flow is for input-constrained devices like CLIs and smart TVs. Our backend uses the standard browser-redirect flow.)

Click the green **Register application** button at the bottom.

### A.3 — Capture the Client ID and Client Secret

After clicking Register, you land on the app's settings page at `https://github.com/settings/applications/<numeric-id>`.

**Capture the Client ID:**

- It's displayed at the top of the page, under the heading **Client ID**.
- This value is not secret in the cryptographic sense, but treat it as configuration — don't publish it.

**Generate the Client Secret:**

1. Scroll down to the **Client secrets** section.
2. Click the button **Generate a new client secret**.
3. GitHub will prompt you to re-confirm your password or 2FA (this is "sudo mode"). Confirm it.
4. The fresh secret string is shown **in full one time** on this page. **Copy it immediately.**

> **About the "shown once" behavior:** GitHub's docs don't literally say "shown once" for OAuth Apps, but the UI behavior is exactly that — on the next page load, the secret collapses to a masked form (`••••••••abcd`) with only **Copy** and **Delete** actions, no way to reveal the full value. If you lose it, generate a new one (and delete the old). The docs do say: *"In the event that your app's client secret is compromised, you will need to generate a new secret, update your app to use the new secret, and delete your old secret."*

### A.4 — Paste into `backend/.env`

Open `backend/.env` (copy from `.env.example` if it doesn't exist yet) and fill in:

```
GITHUB_OAUTH_CLIENT_ID=<paste the Client ID from the app page>
GITHUB_OAUTH_CLIENT_SECRET=<paste the secret you just generated>
```

Verify `.env` is git-ignored (it should be — check `.gitignore` if uncertain).

### A.5 — One callback URL per OAuth App (important constraint)

GitHub's docs are explicit: *"OAuth apps cannot have multiple callback URLs, unlike GitHub Apps."* That means **a single OAuth App cannot serve both dev and prod**. The standard practice (and what we follow):

- **One OAuth App for dev** — callback `http://localhost:8000/api/v1/oauth/github/callback`. ✓ Done.
- **One OAuth App for prod** — callback `https://<your-domain>/api/v1/oauth/github/callback`. Register this later when you deploy; repeat A.1–A.4 with prod values. Name it `Repo-Manage (prod)`.

Don't try to edit the dev app's callback URL when going to production — create a second app and use its credentials in your production secret store.

### A.6 — Scopes are not configured on the app (they're requested at sign-in)

You won't see a "scopes" picker anywhere in the registration form. **Scopes are sent at authorize-URL time** in the `scope` query parameter — our backend handles this in `oauth/services/github.py`. The two scopes we request:

- **`read:user`** — *"Grants access to read a user's profile data."* (Identity data for `GitHubProfile`.)
- **`repo`** — *"Grants full access to public and private repositories including read and write access to code, commit statuses, repository invitations, collaborators, deployment statuses, and repository webhooks."* (Broader than strictly needed for read-only repo listing; `plan.md` §8 explains why we accept the breadth.)

You don't need to do anything to "enable" these — the user sees them on the consent screen the first time they sign in.

---

## Part B — Google OAuth 2.0 Client (Web application type)

Google has a much more involved setup. The UI was reorganized in 2024 — what older docs call the **"OAuth consent screen"** is now the **Google Auth Platform** with separate tabs: **Overview, Branding, Audience, Clients, Data Access, Verification Center**. If a tutorial sends you to "APIs & Services → OAuth consent screen", the equivalent today is **APIs & Services → Google Auth platform**, or directly <https://console.developers.google.com/auth/overview>.

The order matters — you must configure the Auth Platform *before* you can create an OAuth Client.

### B.1 — Create or select a Google Cloud project

Skip if you already have a project you want to use.

1. Open <https://console.cloud.google.com/>.
2. At the very top of the page, next to the "Google Cloud" logo, click the **project selector dropdown** (it shows either your current project name or "Select a project").
3. In the dialog that opens, click **NEW PROJECT** at the top-right of the modal.
4. Fill in:
   - **Project name** — `repo-manage-dev` (or whatever you prefer). Google auto-derives a unique **Project ID** from this; you can edit it once via the **EDIT** link, but the Project ID is **permanent** after creation.
   - **Organization** — leave as "No organization" for a personal Google account.
   - **Location** — leave as "No organization" or pick a folder if you're inside a Workspace org.
5. Click **CREATE**. Give it a minute. When the project selector at the top shows your new project, you're ready.

> **"Can't find your Google Workspace organization?" banner:** harmless. It just means you're on a personal account. Continue.

### B.2 — Configure the Google Auth Platform (one-time per project)

1. Open <https://console.developers.google.com/auth/overview>, or navigate via **Menu (hamburger icon) → APIs & Services → Google Auth platform**.
2. If this is the first time, the page shows *"Google Auth platform not configured yet"*. Click **GET STARTED**.

A four-screen wizard runs: **App Information → Audience → Contact Information → Finish**. After completion these become persistent tabs (Branding, Audience, etc.).

#### B.2.1 — App Information (becomes the "Branding" tab)

- **App name** — `Repo-Manage`. This is what users see on the consent screen.
  - Google's naming rules: must be distinctive; cannot combine Google product names with generic terms. *Acceptable: `Photo Browser`, `Inbox Assistant`. Not acceptable: `Google App`, `YouTube Mobile`.*
- **User support email** — your email (or any Google-registered email / Google Group you own).

Click **NEXT**.

#### B.2.2 — Audience

This is the most consequential choice. Pick one:

- **Internal** — *"Available only for projects within a Google Cloud Organization, this restricts authorization to organization members."* Internal apps skip verification entirely and have no 100-user cap, but are only selectable if your project lives inside a Google Workspace organization. If you signed up with a personal `@gmail.com`, this radio button will be disabled.
- **External** — *"Available to any user with a Google Account."* What you'll pick if you're on a personal Google account. External apps start in **Testing** publishing status (more on this in B.4).

Click **NEXT**.

#### B.2.3 — Contact Information

- **Email addresses** — where Google sends project notifications and security alerts. Use a monitored address.

Click **NEXT**.

#### B.2.4 — Finish

Check the box for **"I agree to the Google API Services: User Data Policy"**, click **CONTINUE**, then **CREATE**.

You're returned to the platform overview, now with persistent tabs along the top: **Overview, Branding, Audience, Clients, Data Access, Verification Center**.

### B.3 — Add the OAuth scopes (Data Access tab)

We need three sign-in scopes: `openid`, `email`, `profile`. All three are non-sensitive (no Google verification required).

1. Click the **Data Access** tab.
2. Click **ADD OR REMOVE SCOPES**. A side panel opens with a long, filterable list grouped into:
   - **Non-sensitive scopes (recommended)**
   - **Sensitive scopes**
   - **Restricted scopes**
3. Use the filter box to find each of the three. Check the box next to each one:
   - **`openid`** — the OpenID Connect trigger; gives us a signed `id_token` containing the user's stable `sub` identifier (`plan.md` §6).
   - **`https://www.googleapis.com/auth/userinfo.email`** — the user's verified primary email.
   - **`https://www.googleapis.com/auth/userinfo.profile`** — name and picture URL.
4. Click **UPDATE** at the bottom of the panel.
5. Click **SAVE** on the Data Access tab.

> **Why no verification step:** Google's verification process applies to **Sensitive** and **Restricted** scopes (e.g., reading Gmail, Drive contents). The three OpenID sign-in scopes are explicitly outside that bucket. Apps using only these three can run in **Testing** indefinitely without going through the verification submission. The cost: testing apps show a *"Google hasn't verified this app"* interstitial to anyone who isn't on the test-users list, and have a 100-user cap and 7-day refresh-token expiry.

### B.4 — Add test users (Audience tab)

While the app is in **Testing** publishing status, **only listed test users can complete the OAuth flow**. Everyone else hits a hard "Access blocked" page. Add yourself (and any teammates).

1. Click the **Audience** tab.
2. Scroll to the **Test users** section.
3. Click **+ ADD USERS**.
4. Type your Google account email (the one you'll use to sign in during dev). Press Enter. Add teammates the same way. Max 100 test users per project.
5. Click **SAVE**.

> **Should I publish the app instead?** For local dev, keep status as **Testing** — it requires nothing more than adding yourself as a test user. Publish later (B.8) when you deploy to prod and want any Google user to sign in.

### B.5 — Create the OAuth Client ID (Clients tab)

Now you create the actual credentials the backend uses to talk to Google.

1. Click the **Clients** tab — or open <https://console.developers.google.com/auth/clients> directly.
2. Click **+ CREATE CLIENT** at the top.
3. In the **Application type** dropdown, pick **Web application**.
4. **Name** — `Repo-Manage (dev)`. Internal label only; users never see it.
5. **Authorized JavaScript origins** — leave this **empty**.
   - Why empty: this field is for apps that call Google APIs *directly from browser JS*. We do everything server-side (the backend hits `oauth2.googleapis.com/token` over HTTPS). Adding a value here is harmless but unnecessary.
6. **Authorized redirect URIs** — click **+ ADD URI** and add:
   - `http://localhost:8000/api/v1/oauth/google/callback`
   - (Optional now, required at deploy time:) a production placeholder like `https://your-prod-domain.example.com/api/v1/oauth/google/callback`. You can also add the prod URI later — see B.8.
7. Click **CREATE**.

> **Redirect URI rules** (Google's validator enforces these):
> - HTTPS required, **except** `http://localhost*` and `http://127.0.0.1*` (loopback exemptions — that's why our dev URI works).
> - No raw IP addresses, except loopback.
> - No path traversal (`/..`), no fragments (`#…`), no wildcards, no userinfo (`user:pass@host`).
> - **Exact string match** with what the backend sends — including scheme, case, and trailing slash. Add `/` or `:8000/` somewhere wrong and you'll get `redirect_uri_mismatch`.

### B.6 — Capture the Client ID and Client Secret

Immediately after clicking **CREATE**, a modal titled **"OAuth client created"** appears showing:

- **Your Client ID** — a long string ending in `.apps.googleusercontent.com`.
- **Your Client Secret** — begins with `GOCSPX-` for clients created via the new platform.

Click **DOWNLOAD JSON** to save a `client_secret_<id>.json` file as a backup, and/or copy both values directly.

> Google's explicit warning: *"Your application's client secret will only be shown after you create the client. Store this information in a secure place such as Google Cloud Secret Manager because it will not be visible or accessible again."* The Client ID is visible later (Clients tab → click the client name), but the Client Secret cannot be re-revealed — only regenerated (which invalidates the old one).

### B.7 — Paste into `backend/.env`

Open `backend/.env` and fill in:

```
GOOGLE_OAUTH_CLIENT_ID=<paste Client ID, ends in .apps.googleusercontent.com>
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-<paste rest of secret>
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/v1/oauth/google/callback
```

The redirect URI must byte-for-byte match what you registered in B.5 — same scheme, host, port, path, casing, no trailing slash.

### B.8 — Going to production (for later)

When you deploy:

1. **Add the production redirect URI** to the same OAuth Client (or create a separate prod client — either works; one client with two URIs is simpler):
   - Clients tab → click your client name → **Authorized redirect URIs** → **+ ADD URI** → `https://<your-prod-domain>/api/v1/oauth/google/callback` → **SAVE**.
2. **Publish the app** (only if you want any Google user, not just test users, to sign in):
   - Audience tab → **PUBLISH APP**.
   - With only `openid email profile` scopes, no verification is required — publishing is one click.

> **Propagation delay — read this before debugging:** Google's docs explicitly say: *"It may take 5 minutes to a few hours for changes made to these settings to take effect."* If you add a redirect URI and immediately get `redirect_uri_mismatch`, **wait** before assuming your code is wrong.

---

## Part C — Verify everything works

### C.1 — Sanity check that the four env vars are loaded

From the repo root:

```bash
cd backend && ./venv/bin/python -c "
from django.conf import settings
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
print('GitHub configured:', bool(settings.GITHUB_OAUTH['CLIENT_ID']) and bool(settings.GITHUB_OAUTH['CLIENT_SECRET']))
print('Google configured:', bool(settings.GOOGLE_OAUTH['CLIENT_ID']) and bool(settings.GOOGLE_OAUTH['CLIENT_SECRET']))
"
```

Both lines should print `True`.

### C.2 — End-to-end test in a browser

1. From the repo root, in two terminals:
   ```bash
   make backend     # Django on :8000
   make frontend    # Vite on :5173
   ```
2. Open <http://localhost:5173>. You should see the Login page.
3. Click **Sign in with Google**:
   - You're redirected to `accounts.google.com`.
   - Sign in with the email you added as a test user in B.4.
   - You see the consent screen for `Repo-Manage` asking for `openid email profile`.
   - Click **Continue**. You're bounced back to `/auth/complete#access=…`. The SPA grabs the token and lands you on `/`.
4. Sign out (when you've added a logout flow) and click **Sign in with GitHub**:
   - You're redirected to `github.com/login/oauth/authorize`.
   - Sign in if needed. The consent screen says `Repo-Manage (dev)` wants `read:user`, `repo`.
   - Click **Authorize**. You're bounced back, sign-in completes, and a first-time GitHub user triggers an automatic repo sync.

If either flow fails, see [Common errors](#common-errors) below.

---

## Part D — Map to the original CHECKLIST.md §15

Cross-reference for `CHECKLIST.md` §15 items so you can tick them off as you go:

| Checklist item | Where in this guide |
|---|---|
| Google Cloud Console: OAuth client created | B.5 |
| Google: authorized redirect URI `http://localhost:8000/api/v1/oauth/google/callback` | B.5 step 6 |
| Google: production redirect URI added | B.8 step 1 |
| Google: consent screen configured (scopes, app name, support email) | B.2 + B.3 |
| GitHub OAuth App created | A.2 |
| GitHub: authorization callback URL `http://localhost:8000/api/v1/oauth/github/callback` | A.2 (the **Authorization callback URL** field) |
| GitHub: production callback URL added | A.5 |
| Client IDs in `.env.example` | Already done — `.env.example` exists with blank slots |
| Client secrets in dev `.env` (NOT committed) | A.4 + B.7 — and confirm `.gitignore` excludes `backend/.env` |

---

## Common errors

| Error | Root cause | Fix |
|---|---|---|
| `redirect_uri_mismatch` (Google) | The URI the backend sent doesn't byte-exactly match a registered URI. | Compare scheme, host, port, path, trailing slash. Wait 5–60 min if you just added a URI (B.8 note). |
| `The redirect_uri MUST match the registered callback URL` (GitHub) | Same idea; GitHub also does exact match. | Make sure you didn't append `/` and that you're on `http` (not `https`) for localhost. |
| `Access blocked: This app's request is invalid` (Google) | App is in Testing and you signed in as a non-test-user. | Add the email to **Audience → Test users** (B.4). Sign in again. |
| `invalid_client` (either provider) | Client ID or Client Secret in `.env` is wrong or missing. | Re-verify with the C.1 sanity check. Regenerate the secret if you lost it (A.3 / B.6). |
| Login completes but `GET /auth/me` returns 401 | Access token didn't reach the SPA. | Check browser DevTools — confirm the redirect ended at `/auth/complete#access=…` and the SPA cleared the fragment correctly. |
| Google sign-in completes but every subsequent API call says "session expired" within 7 days | Your refresh token expired because the app is in Testing status. | Either re-sign-in, or **publish** the app (B.8 step 2). This only applies if you wire up Google API calls later — we currently don't store/use Google's refresh token, so this isn't a practical issue. |

---

## Production credentials — the rule

Never use dev OAuth credentials in production. The reasons:

- **Compromise of dev credentials must not yield prod access.** If a dev `.env` leaks (it happens), prod must be unaffected.
- **GitHub OAuth Apps allow only one callback URL** — sharing is impossible there anyway.
- **Google clients pin a redirect-URI set** — you could share by listing both URIs, but coupling dev and prod credentials defeats the isolation principle.

Naming convention used throughout: `<app-name> (dev)` and `<app-name> (prod)`. Store prod credentials in your secrets manager (Vault / AWS Secrets Manager / Doppler / etc.), **never** in a committed file. `plan.md` §5 covers the broader token-storage policy.

---

## Sources

All citations are official 2026 documentation from Google and GitHub.

### Google
- [Get started with the Google Auth Platform](https://support.google.com/cloud/answer/15544987)
- [Manage OAuth App Branding](https://support.google.com/cloud/answer/15549049?hl=en)
- [Manage App Audience](https://support.google.com/cloud/answer/15549945?hl=en)
- [Manage OAuth Clients](https://support.google.com/cloud/answer/6158849?hl=en)
- [Verification requirements](https://support.google.com/cloud/answer/13464321?hl=en)
- [When verification is not needed](https://support.google.com/cloud/answer/13464323?hl=en)
- [Configure the OAuth consent screen and choose scopes](https://developers.google.com/workspace/guides/configure-oauth-consent)
- [Create a Google Cloud project](https://developers.google.com/workspace/guides/create-project)
- [Using OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [OpenID Connect](https://developers.google.com/identity/protocols/oauth2/openid-connect)
- [Get your Google API client ID](https://developers.google.com/identity/oauth2/web/guides/get-google-api-clientid)

### GitHub
- [Creating an OAuth app](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app)
- [Authorizing OAuth apps (authorize URL + scope format)](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps)
- [Scopes for OAuth Apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps)
- [Best practices for creating an OAuth app (secret storage and rotation)](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/best-practices-for-creating-an-oauth-app)
- [Differences between GitHub Apps and OAuth apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps)
- [Authenticating to the REST API with an OAuth app](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authenticating-to-the-rest-api-with-an-oauth-app)
- [GitHub Developer Settings — Register a new application (direct link)](https://github.com/settings/applications/new)
