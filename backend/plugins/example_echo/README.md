# Example Echo Plugin

This example shows the three extension points supported by Sigorjob plugins:

- `plugin.py`: register custom tools
- `rules.yaml`: add non-AI intent rules
- `ai_instructions.md`: give the AI planner plugin-specific hints

Try:

```bash
python3 backend/main.py run "echo plugin hello" --json
```
