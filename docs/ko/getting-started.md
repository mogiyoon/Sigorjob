# 시작 가이드

자동화 플랫폼을 처음부터 설정하고 실행하는 방법.

---

## 사전 요구사항

- Python 3.12+
- Node.js 18+ (프론트엔드용)
- macOS 또는 Linux

---

## 1. 백엔드 설정

```bash
cd backend
pip install -r requirements.txt

# 선택: 브라우저 자동화를 위한 Playwright 설치
pip install playwright
playwright install chromium
```

---

## 2. 서버 시작

```bash
# 개발 모드 (백엔드 + 프론트엔드)
./scripts/dev.sh

# 백엔드만
cd backend && python3 main.py serve

# CLI 모드 (단일 명령)
cd backend && python3 main.py run "현재 시간 알려줘"
```

서버: `http://localhost:8000`

---

## 3. 설정 페이지

`http://localhost:8000` → Setup (톱니바퀴) 클릭.

### AI 설정
- Anthropic API 키 입력 → "Verify" 클릭
- 이게 없으면 규칙 기반(비AI) 경로만 사용 가능

### Google 서비스 (선택)
- [Google OAuth 설정 가이드](google-oauth-setup.md)를 따라 자격증명 발급
- Google Calendar 또는 Gmail 옆의 "Connect" 클릭
- Google 동의 페이지에서 권한 부여

### MCP 서버 (선택)
- MCP Presets 섹션에서 Google Calendar 또는 Gmail "Install" 클릭
- AI 에이전트가 외부 도구를 사용할 수 있게 됨

### Playwright (선택)
- Tools 섹션에서 Playwright 상태 확인
- 미설치 시 "Install" 클릭 (수 분 소요)
- JavaScript 사이트 브라우저 자동화 활성화

---

## 4. 명령 예시

### 비AI (즉시, 무료)
```
현재 시간 알려줘
/tmp 폴더 목록 보여줘
https://example.com 읽어와
네이버 열어줘
```

### 플러그인 (즉시, 무료)
```
내일 오후 3시 팀 회의 캘린더에 추가해줘
성수 카페 추천해줘
네이버에서 드럼스틱 사줘
강남역까지 길찾아줘
```

### AI 보조 (API 키 필요)
```
토스 상장 관련 뉴스 검색해서 요약해줘
오늘 일정 정리해줘
이 파일 분석해서 결과 알려줘
```

---

## 5. 모바일 접속 (선택)

1. 모바일 앱 설치
2. 데스크톱에서 Setup → Pair
3. QR 코드를 모바일 앱으로 스캔
4. 모바일 명령이 데스크톱 백엔드로 전송됨

---

## 6. 스케줄 작업

```bash
curl -X POST http://localhost:8000/schedule \
  -H "Content-Type: application/json" \
  -d '{"command": "아침 날씨 알림", "cron": "0 8 * * *"}'
```

---

## 개발

### 테스트 실행
```bash
cd backend && python3 -m unittest discover -s tests -v
```

### 개발 하네스 (자동 코딩 파이프라인)
```bash
python3 scripts/dev-harness.py --spec scripts/harness-specs/example-spec.json --dry-run
```

상세 문서: [개발 하네스](dev-harness.md) | [개발 워크플로우](dev-workflow.md)
