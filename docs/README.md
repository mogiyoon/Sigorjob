# Documentation

This project now keeps documentation in both Korean and English.

Important runtime note:

- local desktop, local web, and CLI usage do not require Cloudflare Tunnel
- packaged desktop builds bundle `cloudflared` for remote/mobile access
- source-based remote web access and mobile pairing still require `cloudflared` on the host machine
- source-based execution still requires normal development dependencies
- packaged desktop builds now auto-pick an available local backend port

Current product direction:

- Sigorjob should behave like a general-purpose AI agent
- non-AI automation is still the first path whenever possible
- AI should stay lightweight and mostly act as a guardrail or recovery layer around the non-AI path
- successful AI flows should gradually move into plugins, rules, or user customization
- external services such as Gmail, Calendar, and future MCP tools should be managed through one shared connection model

한국어 문서:

- [Architecture](./ko/architecture.md)
- [API Spec](./ko/api-spec.md)
- [Modules](./ko/modules.md)
- [Folder Structure](./ko/folder-structure.md)
- [MVP](./ko/mvp.md)
- [Runtime Surfaces](./ko/runtime-surfaces.md)
- [Remote Access](./ko/remote-access.md)
- [Cautions](./ko/cautions.md)
- [Debug Regressions](./ko/debug-regressions.md)

English docs:

- [Architecture](./en/architecture.md)
- [API Spec](./en/api-spec.md)
- [Modules](./en/modules.md)
- [Folder Structure](./en/folder-structure.md)
- [MVP](./en/mvp.md)
- [Runtime Surfaces](./en/runtime-surfaces.md)
- [Remote Access](./en/remote-access.md)
- [Cautions](./en/cautions.md)
- [Debug Regressions](./en/debug-regressions.md)

Notes:

- The localized docs under `docs/ko` and `docs/en` are the preferred references going forward.
- Legacy top-level files in `docs/` may still exist during the transition.
