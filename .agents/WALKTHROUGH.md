# Oplyra Walkthrough

Step-by-step guides for verifying major platform workflows.

---

## Core Workflow — Register to First Asset

The primary daily journey for a solo marketer.

1. **Register** at `/register`. On signup, a personal Organization + Membership
   are provisioned automatically, so every workflow has a tenant from action one.
2. **Home (`/`)** shows Today's Work: onboarding tasks and the most important next action.
3. **Create a Client** — Clients page → Create Client Portfolio (name required).
4. **Create a Campaign** under the client (nested per the product rules).
5. **Generate content** — AI Assistant / generate page:
   - Pick a client, a content type (blog, email, social post, review, ad copy, etc.), fill required fields, Generate.
   - A full-screen spinner shows during generation; errors surface in an inline banner (no silent failures).
   - Generation routes through the central `AIGateway` (model `gemini-2.5-flash`, overridable via `GEMINI_MODEL`).
   - With a placeholder `GEMINI_API_KEY` (`your_...`), the gateway returns deterministic mock copy so the flow works offline.
6. **Review** the generated asset, run SEO analysis, edit, and export to PDF/DOCX.

### Verifying without a live Gemini key

Set `GEMINI_API_KEY=your_gemini_api_key_here` in `.env`. Content generation
returns mock copy end-to-end (no network). Tests run in this mode automatically.

---

## Sprint 5A — Connected Apps (GSC + GA4)

Read-only marketing integrations with manual sync and campaign import.

### Prerequisites

1. Copy `.env.example` to `.env` and set:
   ```env
   GOOGLE_OAUTH_CLIENT_ID=<from Google Cloud Console>
   GOOGLE_OAUTH_CLIENT_SECRET=<from Google Cloud Console>
   GOOGLE_OAUTH_REDIRECT_URI=http://localhost:5000/integrations/callback/google
   INTEGRATIONS_MOCK_MODE=false
   ```
2. Enable APIs in Google Cloud: **Search Console API**, **Google Analytics Data API**, **Google Analytics Admin API**.
3. Start the app: `flask run`
4. Log in and stay logged in during OAuth redirects.

### Mock mode (no Google credentials)

Set `INTEGRATIONS_MOCK_MODE=true` or leave OAuth client ID as placeholder. Connect flows use fixture properties and skip Google consent.

---

### 1. Connect Google Search Console

1. Go to **Settings → Manage Connected Apps** (or `/integrations/`).
2. Under **Google Search Console**, optionally pick a Client, click **Connect**.
3. **Mock:** Property selector shows two mock sites.
4. **Live:** Google consent screen → redirect back → **Select Default Property** page.
5. Choose the site to sync → **Save Selection**.
6. Card shows **connected** with your selected site name.

### 2. Connect Google Analytics 4

1. Repeat for **Google Analytics 4** (separate OAuth — different scope).
2. On property selector, choose the GA4 property for sync.
3. Confirm card shows connected status.

### 3. Change default property

1. On a connected card, click **Change Property**.
2. Select a different site/property → **Save Selection**.
3. Future syncs use the new selection (stored in `PlatformConnection.connection_metadata`).

### 4. Manual Sync

1. Click **Sync Now** on a connected integration.
2. Button shows spinner while syncing.
3. **Last Sync** timestamp updates; **Sync Status** shows `success` or `error`.
4. Errors appear inline under the card (red text).

### 5. Verify metrics stored

After sync, metrics are saved in `synced_metrics` (via app DB). Re-sync does not duplicate rows for the same period.

### 6. Campaign Import

1. Scroll to **Campaign Import** section.
2. Pick Connection → External Campaign (populated after sync) → Target Client.
3. Click **Import Campaign**.
4. Success message links to the Client page; one Campaign is created.

### 7. Duplicate import prevention

Import the same external campaign again → message indicates already imported; no second Campaign row.

### 8. Disconnect and reconnect

1. **Disconnect** clears tokens and sets status `disconnected`.
2. **Sync Now** on disconnected integration fails with "disconnected".
3. **Connect** again → property selector → sync succeeds.

### 9. Expired / revoked token

1. Revoke app access in [Google Account → Security → Third-party access](https://myaccount.google.com/permissions).
2. **Sync Now** → error mentions token refresh failure; status may show `token_expired` or `error`.
3. **Disconnect** → **Connect** to re-authorize.

### 10. Empty Google account

If the Google account has no GSC sites or GA4 properties, OAuth completes but the property selector shows an empty state with a back link — no connection is saved until a property exists.

### Automated tests

```powershell
cd "c:\Users\Akshay\genny ai"
.\venv\Scripts\python.exe -m unittest tests.sprint5_integrations_test tests.sprint5_live_validation_test -v
```

### Live validation harness

```powershell
.\venv\Scripts\python.exe scratch\validate_sprint5a_live.py
```

---

## Sprint 5B / 5C (Not started)

Deferred: Google Ads, Meta Ads, Client Snapshot, Report Autofill, Notification Engine, Background Scheduler.
