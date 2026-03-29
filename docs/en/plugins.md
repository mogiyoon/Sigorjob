# Plugins

Sigorjob supports local plugins under [backend/plugins](/Users/nohgiyoon/Coding/AI/Agent/backend/plugins).

Each plugin can provide one or more of these files:

- `plugin.py`: register custom tools
- `rules.yaml`: add non-AI intent rules
- `ai_instructions.md`: add extra AI planner guidance
- `plugin.json`: plugin name and description

## Quick Start

Create a scaffold:

```bash
python3 backend/main.py plugins scaffold my_plugin --type hybrid
```

List installed plugins:

```bash
python3 backend/main.py plugins list --json
```

## Example

See [backend/plugins/example_echo](/Users/nohgiyoon/Coding/AI/Agent/backend/plugins/example_echo).

More starter examples:

- [backend/plugins/reservation_helper](/Users/nohgiyoon/Coding/AI/Agent/backend/plugins/reservation_helper)
- [backend/plugins/delivery_helper](/Users/nohgiyoon/Coding/AI/Agent/backend/plugins/delivery_helper)
- [backend/plugins/draft_helper](/Users/nohgiyoon/Coding/AI/Agent/backend/plugins/draft_helper)

You can test it with:

```bash
python3 backend/main.py run "echo plugin hello" --json
```
