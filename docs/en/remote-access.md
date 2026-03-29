# Remote Access

## Overview

Remote access is optional.
Local desktop, local web, and CLI workflows can work without it.

Remote web access and mobile pairing require:

- a running local backend
- `cloudflared` available to the runtime
- either Quick Tunnel mode or a configured Cloudflare tunnel token

Normal product direction:

- packaged desktop builds bundle `cloudflared` for end users
- source-based development and local packaging can still use a host-installed `cloudflared` or `CLOUDFLARED_PATH`

## Installing `cloudflared`

Packaged desktop builds are intended to include `cloudflared`, so end users should not need to install it separately.

The instructions below are mainly for developers, source-based environments, or packaging machines.

### macOS

Recommended:

```bash
brew install cloudflared
```

Alternative:

- Download the official macOS binary from Cloudflare's download page.
- If you install it outside your normal shell `PATH`, set `CLOUDFLARED_PATH` manually.

### Windows

Recommended:

- Download the official `cloudflared.exe` from Cloudflare's download page.

Alternative:

```powershell
winget install Cloudflare.cloudflared
```

If the executable is not on `PATH`, point the app to it with `CLOUDFLARED_PATH`.

### Verification

After installation, confirm that the host can find it:

```bash
cloudflared --version
```

If that command does not work, set `CLOUDFLARED_PATH` to the full executable path.

## Readiness Check

Use the local readiness check for packaging and host prerequisites:

```bash
./scripts/check-dist-readiness.sh --with-remote
```

Use the runtime remote-flow check after the backend is running:

```bash
./scripts/check-remote-flow.sh
```

You can also pass a different local base URL:

```bash
./scripts/check-remote-flow.sh http://127.0.0.1:8000
```

## Local Setup Flow

1. Start the backend or desktop app.
2. Open the local setup page.
3. Confirm that `cloudflared` is available.
4. Choose one remote mode:
   - Quick Tunnel: start immediately with no token
   - Named Cloudflare Tunnel: paste the tunnel token from Cloudflare Zero Trust
5. Wait for the tunnel URL to appear.
6. Open the local pairing page.
7. Copy the pairing token or complete mobile pairing.

## Remote Modes

### Quick Tunnel

- No Cloudflare account or token is required.
- The app asks `cloudflared` for a temporary `trycloudflare.com` URL.
- This is the lowest-friction path for testing and simple remote access.
- The URL can change after restart, so it is not ideal when you want a long-lived stable address.

### Named Cloudflare Tunnel

- Requires a Cloudflare tunnel token from Zero Trust.
- Requires a public hostname or route to be configured in Cloudflare.
- Better when you want a stable remote address over time.
- Higher setup friction than Quick Tunnel.

## Common States

### `cloudflared` missing

- Remote access is not available yet.
- In packaged desktop builds, this usually means the app bundle is incomplete.
- In source-based environments, install `cloudflared` or set `CLOUDFLARED_PATH`.

### No named tunnel token configured

- Local usage still works.
- Quick Tunnel can still be used.
- Named-tunnel remote/mobile access will stay unavailable until the tunnel token is saved.

### Tunnel configured but inactive

- If you are using Quick Tunnel, retry the connection and recheck local network access.
- If you are using a named tunnel, recheck the token.
- For named tunnels, also recheck the public hostname or route in Cloudflare.
- Recheck local network conditions.
- Reopen the setup page and inspect the reported tunnel error.

### Pairing ready

- The local machine has a tunnel URL.
- The mobile app can connect with the pairing token.

## Security Notes

- Setup and pairing APIs are local-only.
- Remote requests require the pairing token.
- The first remote load may bootstrap through `?_token=`.
- After that, the server continues through auth cookie or bearer token.

## Official References

- Cloudflare downloads: https://developers.cloudflare.com/tunnel/downloads/
- Cloudflare tunnel run token: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/cloudflared-parameters/run-parameters/
