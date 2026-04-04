# Calendar Helper Plugin

Examples:

```bash
python3 backend/main.py run "내일 오후 3시 팀 회의 캘린더에 일정 추가해줘" --json
python3 backend/main.py run "모레 오전 10시 병원 예약 일정 넣어줘" --json
python3 backend/main.py run "4월 11일 16시에 벚꽃 일정 추가해줘" --json
```

Expected behavior:

- This helper should work as a deterministic non-AI route when the request already matches the calendar rule.
- Explicit dates such as `4월 11일 16시` should be preserved in the generated Google Calendar link.
- Packaged desktop builds should keep producing the same final Google Calendar handoff link without requiring MCP or AI continuation.
