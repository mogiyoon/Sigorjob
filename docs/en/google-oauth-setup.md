# Google OAuth Setup Guide

This guide walks you through setting up Google OAuth credentials
so the system can access Google Calendar and Gmail on your behalf.

---

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Name it (e.g., "Sigorjob Agent") and create

---

## Step 2: Enable APIs

In your project, enable these APIs:

1. Go to "APIs & Services" → "Library"
2. Search and enable:
   - **Google Calendar API**
   - **Gmail API**

---

## Step 3: Create OAuth Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. If prompted, configure the OAuth consent screen first:
   - User Type: "External" (or "Internal" if using Google Workspace)
   - App name: "Sigorjob Agent"
   - Scopes: add `calendar`, `gmail.compose`, `gmail.readonly`
4. Application type: "Web application"
5. Authorized redirect URIs: add `http://localhost:8000/oauth/callback`
   - For remote access: also add your tunnel URL + `/oauth/callback`
6. Click "Create"
7. Copy the **Client ID** and **Client Secret**

---

## Step 4: Configure in Sigorjob

### Option A: Via Setup UI

1. Open Sigorjob in your browser
2. Go to Setup page
3. In the "External Connections" section, find Google Calendar or Gmail
4. Enter the Client ID and Client Secret
5. Click "Connect" — this opens Google's OAuth consent page
6. Authorize the permissions
7. The connection status should change to "Connected"

### Option B: Via API

```bash
# Store OAuth credentials
curl -X POST http://localhost:8000/setup/connections/google_calendar \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {
      "client_id": "YOUR_CLIENT_ID",
      "client_secret": "YOUR_CLIENT_SECRET"
    }
  }'

# Start OAuth flow
curl -X POST http://localhost:8000/setup/connections/google_calendar/authorize

# Response: {"auth_url": "https://accounts.google.com/..."}
# Open this URL in your browser, authorize, then:

curl -X POST http://localhost:8000/setup/connections/google_calendar/callback \
  -H "Content-Type: application/json" \
  -d '{"code": "AUTH_CODE_FROM_REDIRECT", "state": "STATE_FROM_URL"}'
```

### Option C: Via config store (development)

```python
from config.store import config_store
config_store.set("google_oauth_client_id", "YOUR_CLIENT_ID")
config_store.set("google_oauth_client_secret", "YOUR_CLIENT_SECRET")
config_store.set("google_oauth_redirect_uri", "http://localhost:8000/oauth/callback")
```

---

## Step 5: Verify

Test that the connection works:

```bash
# Should return connected status
curl http://localhost:8000/setup/status | python3 -m json.tool
```

Or use the system directly:

```
"내일 오후 3시에 팀 회의 캘린더에 추가해줘"
→ Should create a real event in Google Calendar
```

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| "redirect_uri_mismatch" | Check that the redirect URI in Google Cloud Console matches exactly |
| "invalid_client" | Verify Client ID and Secret are correct |
| "access_denied" | User denied the consent — try again |
| "Token refresh failed" | Token may have been revoked — disconnect and reconnect |
| Connection shows "not verified" | The OAuth callback was not completed — try clicking Connect again |

---

## Security Notes

- OAuth tokens are stored in macOS Keychain (via `secret_store`), not in plain files
- Client ID and Secret are stored in `config_store` — keep your config directory private
- Tokens auto-refresh silently when they expire
- You can disconnect at any time to revoke access
