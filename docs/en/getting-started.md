# Getting Started

Set up and run the automation platform from scratch.

---

## Prerequisites

- Python 3.12+
- Node.js 18+ (for frontend)
- macOS or Linux

---

## 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt  # or pip3

# Optional: install Playwright for browser automation
pip install playwright
playwright install chromium
```

---

## 2. Start the Server

```bash
# Development mode (backend + frontend)
./scripts/dev.sh

# Backend only
cd backend && python3 main.py serve

# CLI mode (single command)
cd backend && python3 main.py run "현재 시간 알려줘"
```

The server starts at `http://localhost:8000`.

---

## 3. Setup Page

Open `http://localhost:8000` → click Setup (gear icon).

### AI Configuration
- Enter your Anthropic API key
- Click "Verify" to confirm it works
- Without this, the system can only use rule-based (non-AI) paths

### Google Services (Optional)
- Follow [Google OAuth Setup Guide](google-oauth-setup.md) to get credentials
- Click "Connect" next to Google Calendar or Gmail
- Authorize in the Google consent page

### MCP Servers (Optional)
- In the MCP Presets section, click "Install" for Google Calendar or Gmail
- This registers the MCP server config so the AI agent can use external tools

### Playwright (Optional)
- Check the Playwright status in the Tools section
- Click "Install" if not yet installed (takes a few minutes)
- This enables browser automation for JavaScript-heavy sites

---

## 4. Try Commands

### Non-AI (instant, free)
```
현재 시간 알려줘
/tmp 폴더 목록 보여줘
https://example.com 읽어와
네이버 열어줘
```

### Plugin-routed (instant, free)
```
내일 오후 3시 팀 회의 캘린더에 추가해줘
성수 카페 추천해줘
네이버에서 드럼스틱 사줘
강남역까지 길찾아줘
```

### AI-assisted (needs API key)
```
토스 상장 관련 뉴스 검색해서 요약해줘
오늘 일정 정리해줘
이 파일 분석해서 결과 알려줘
```

---

## 5. Mobile Access (Optional)

1. Install the mobile app
2. On the desktop, go to Setup → Pair
3. Scan the QR code with the mobile app
4. Commands from mobile are sent to the desktop backend

---

## 6. Scheduled Tasks

```bash
# Via API
curl -X POST http://localhost:8000/schedule \
  -H "Content-Type: application/json" \
  -d '{"command": "아침 날씨 알림", "cron": "0 8 * * *"}'
```

Or use the UI to create schedules.

---

## Architecture Quick Reference

```
User command
  → Intent Router (rules first, AI fallback)
  → Orchestrator (execute steps, quality check)
  → Tools (file, shell, crawler, browser_auto, mcp)
  → Result + Summary
```

For details: [Agent Workflow](agent-workflow.md)

---

## Development

### Run tests
```bash
cd backend && python3 -m unittest discover -s tests -v
```

### Dev harness (automated coding pipeline)
```bash
python3 scripts/dev-harness.py --spec scripts/harness-specs/example-spec.json --dry-run
```

For details: [Dev Harness](dev-harness.md) | [Dev Workflow](dev-workflow.md)
