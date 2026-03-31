# Runtime Surfaces

This document explains the practical differences between running Sigorjob in:

- a normal browser
- the packaged Tauri desktop app
- the mobile app

These surfaces share a lot of code, but they are not interchangeable.

## Overview

### Browser

- Best for local development and quick UI checks
- Behaves like a normal web app
- Can rely on standard browser behavior for links, clipboard, and tab navigation

### Tauri desktop app

- Best for packaged end-user desktop usage
- Runs the backend sidecar automatically in release builds
- Uses a runtime-selected local backend port instead of assuming `127.0.0.1:8000`
- Looks like a web UI, but browser assumptions do not always hold

### Mobile app

- Works as a paired remote surface for the desktop host
- Uses QR/manual pairing and loads the remote UI in a WebView
- Can also act as a lightweight mobile command entry surface
- Android currently has the more complete shared-text path

## Key Differences

### External links

Browser:

- `target="_blank"` and standard anchors usually behave as expected

Tauri:

- external links should go through a shared helper or Tauri command
- raw browser-style new-tab assumptions are risky

Mobile WebView:

- links stay inside the constrained remote UI unless intentionally handed off

Recommended rule:

- do not scatter raw external-link behavior throughout the UI
- use one shared `open external` helper

### Clipboard

Browser:

- `navigator.clipboard` often works naturally

Tauri:

- clipboard behavior can depend on focus, permission state, and WebView behavior

Mobile WebView:

- browser clipboard assumptions are even less reliable

Recommended rule:

- wrap clipboard actions behind a shared helper instead of using raw browser APIs everywhere

### Local API base URL

Browser dev flow:

- often assumes `http://127.0.0.1:8000`

Packaged Tauri:

- the backend port is dynamic
- the frontend should follow the injected runtime URL

Mobile:

- uses the paired desktop tunnel URL rather than a local loopback URL

Recommended rule:

- never hardcode `127.0.0.1:8000` as a universal truth

### Authentication

Browser local:

- loopback requests can work without pairing auth

Remote browser/mobile:

- requires pairing token bootstrap and then cookie/bearer auth

Recommended rule:

- always think about whether a request is local-only or remote-safe

## Current Practical Guidance

When adding UI behavior, ask:

1. Does this assume a normal browser?
2. Does this need to work in packaged Tauri too?
3. Does mobile WebView need the same behavior or a safer variant?

Common examples that need special care:

- opening external links
- clipboard copy
- new-window flows
- browser-only APIs
- hostname-based runtime detection

## Safe Direction

- Keep the shared UI, but isolate runtime-sensitive behavior in helpers
- Prefer capability-style helpers over direct browser globals
- Treat browser, Tauri, and mobile as three real runtime surfaces, not one
