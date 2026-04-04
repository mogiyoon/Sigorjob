# Cautions

This document collects practical cautions for using and extending Sigorjob.

## Product Behavior

- Sigorjob is designed to try non-AI execution first.
- If rules-based handling is weak or incomplete, AI fallback should take over.
- In practice, some requests may still fall back to partial results or fail if the required tool flow has not been implemented yet.
- A result that opens a useful page is better than a blind failure, but generic search fallbacks should not be treated as true task completion for complex automation requests.

## AI Fallback

- AI fallback only works when a valid API key is actually readable by the runtime.
- Seeing `AI connected` in the UI should mean the runtime can use the key, not just that a key was previously stored.
- If AI fallback is unavailable, some advanced requests may still fail even when the UI suggests AI is configured.
- AI should be treated as a recovery layer, not the default path for every request.
- When a request already matches a deterministic non-AI helper such as `calendar_helper`, that route should stay non-AI through execution and final summary.
- AI clarification, review, and continuation should only start after the non-AI route actually fails to match or cannot produce a usable plan.

## Remote and Mobile Access

- Local desktop, local web, and CLI usage do not require remote tunneling.
- Mobile access and remote web access depend on Cloudflare Tunnel.
- Quick Tunnel is easier for onboarding, but its URL can change after restart.
- Named Tunnel is more stable, but it requires additional Cloudflare setup.
- Mobile pairing depends on the desktop host being online and reachable.
- Packaged desktop builds now choose a local backend port dynamically, so old assumptions about `127.0.0.1:8000` are no longer reliable.

## Current Delivery Model

- Many “send” or “notify” style requests currently mean “prepare the result so it can be viewed from the app” rather than “push a native notification”.
- Some recurring workflows may create a schedule or schedule draft instead of directly delivering a push notification.
- If a result says it was prepared for the app, check the task list or schedule list rather than expecting a system push.
- If a result opens a page such as Google Calendar or mail compose, that is still a handoff step, not full completion inside Sigorjob.
- Calendar-style helper flows should still produce the final Google Calendar link in packaged desktop builds without requiring MCP or an AI tool path.

## Plugins and Extensions

- Plugins are the preferred way to add new non-AI helpers, AI guidance, and tool integrations.
- A plugin can improve intent handling without changing the core router.
- Plugins should prefer safe, deterministic behavior and only use AI as a fallback.
- New integrations should declare their required permissions clearly.

## Security

- Sensitive keys should not be exposed back to the frontend.
- Local-only setup routes should stay blocked from remote access.
- Destructive or high-risk actions should continue to require explicit approval.
- Browser-opening helpers should not be mistaken for full automation.

## User Expectations

- Users will often phrase requests as if speaking to a general AI agent.
- Users will also make typos and use natural shorthand, so intent handling should not depend on brittle exact phrases alone.
- If Sigorjob cannot truly complete such a request, it should respond honestly and use the best available fallback.
- Avoid making weak partial behavior look like success.
- “Opened a search page” is not the same as “completed the requested task”.

## Web vs Desktop Runtime

- A behavior that works in a normal browser is not automatically safe in Tauri.
- External links, clipboard flows, new-window assumptions, and browser-only APIs should be treated as runtime-sensitive.
- Prefer shared helpers for opening external URLs and other browser-assumed actions instead of sprinkling raw `target="_blank"` or browser globals throughout the UI.

## Recommended Direction

- Keep expanding common non-AI request bundles first.
- Use plugins for new lifestyle and assistant-style requests.
- Let AI handle ambiguous or underspecified cases after non-AI attempts.
- Prefer explicit summaries that explain what was actually completed.
