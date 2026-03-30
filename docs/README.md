# Documentation

This project now keeps documentation in both Korean and English.

Important runtime note:

- local desktop, local web, and CLI usage do not require Cloudflare Tunnel
- remote web access and mobile pairing require `cloudflared` on the host machine
- source-based execution still requires normal development dependencies

Current product direction:

- Sigorjob should behave like a general-purpose AI agent
- non-AI automation is still the first path whenever possible
- successful AI flows should gradually move into plugins, rules, or user customization
- external services such as Gmail, Calendar, and future MCP tools should be managed through one shared connection model

한국어 문서:

- [Architecture](./ko/architecture.md)
- [API Spec](./ko/api-spec.md)
- [Modules](./ko/modules.md)
- [Folder Structure](./ko/folder-structure.md)
- [MVP](./ko/mvp.md)

English docs:

- [Architecture](./en/architecture.md)
- [API Spec](./en/api-spec.md)
- [Modules](./en/modules.md)
- [Folder Structure](./en/folder-structure.md)
- [MVP](./en/mvp.md)
- [Remote Access](./en/remote-access.md)
- [Cautions](./en/cautions.md)

Notes:

- The localized docs under `docs/ko` and `docs/en` are the preferred references going forward.
- Legacy top-level files in `docs/` may still exist during the transition.
