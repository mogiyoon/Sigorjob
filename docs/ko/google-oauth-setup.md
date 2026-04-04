# Google OAuth 설정 가이드

Google Calendar과 Gmail을 실제로 사용하기 위한 OAuth 자격증명 설정 방법.

---

## 1단계: Google Cloud 프로젝트 생성

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. "프로젝트 선택" → "새 프로젝트"
3. 이름 입력 (예: "Sigorjob Agent") → 만들기

---

## 2단계: API 활성화

1. "API 및 서비스" → "라이브러리"
2. 검색 후 활성화:
   - **Google Calendar API**
   - **Gmail API**

---

## 3단계: OAuth 자격증명 생성

1. "API 및 서비스" → "사용자 인증 정보"
2. "사용자 인증 정보 만들기" → "OAuth 클라이언트 ID"
3. 동의 화면 설정 요청 시:
   - 사용자 유형: "외부"
   - 앱 이름: "Sigorjob Agent"
   - 범위: `calendar`, `gmail.compose`, `gmail.readonly` 추가
4. 애플리케이션 유형: "웹 애플리케이션"
5. 승인된 리디렉션 URI: `http://localhost:8000/oauth/callback`
6. "만들기" 클릭
7. **클라이언트 ID**와 **클라이언트 보안 비밀번호** 복사

---

## 4단계: Sigorjob에 설정

### Setup UI에서 설정 (권장)

1. Sigorjob 웹 열기
2. Setup 페이지 이동
3. "External Connections"에서 Google Calendar 또는 Gmail 찾기
4. Client ID와 Client Secret 입력
5. "Connect" 클릭 → Google 동의 페이지에서 권한 부여
6. 연결 상태가 "Connected"로 변경되면 완료

---

## 5단계: 확인

```
"내일 오후 3시에 팀 회의 캘린더에 추가해줘"
→ 실제 Google Calendar에 이벤트가 생성되어야 합니다
```

---

## 문제 해결

| 문제 | 해결 |
|------|------|
| "redirect_uri_mismatch" | Cloud Console의 리디렉션 URI가 정확히 일치하는지 확인 |
| "invalid_client" | Client ID, Secret이 맞는지 확인 |
| "access_denied" | 사용자가 동의를 거부함 — 다시 시도 |
| 토큰 갱신 실패 | 연결 해제 후 재연결 |

---

## 보안

- OAuth 토큰은 macOS Keychain에 저장 (일반 파일 아님)
- Client ID/Secret은 config_store에 저장 — 설정 디렉토리 보안 유지 필요
- 토큰은 만료 시 자동 갱신
- 언제든 Disconnect로 접근 취소 가능
