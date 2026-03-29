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

## Remote and Mobile Access

- Local desktop, local web, and CLI usage do not require remote tunneling.
- Mobile access and remote web access depend on Cloudflare Tunnel.
- Quick Tunnel is easier for onboarding, but its URL can change after restart.
- Named Tunnel is more stable, but it requires additional Cloudflare setup.
- Mobile pairing depends on the desktop host being online and reachable.

## Current Delivery Model

- Many “send” or “notify” style requests currently mean “prepare the result so it can be viewed from the app” rather than “push a native notification”.
- Some recurring workflows may create a schedule or schedule draft instead of directly delivering a push notification.
- If a result says it was prepared for the app, check the task list or schedule list rather than expecting a system push.

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
- If Sigorjob cannot truly complete such a request, it should respond honestly and use the best available fallback.
- Avoid making weak partial behavior look like success.
- “Opened a search page” is not the same as “completed the requested task”.

## Recommended Direction

- Keep expanding common non-AI request bundles first.
- Use plugins for new lifestyle and assistant-style requests.
- Let AI handle ambiguous or underspecified cases after non-AI attempts.
- Prefer explicit summaries that explain what was actually completed.
