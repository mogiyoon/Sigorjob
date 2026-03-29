# 플러그인

Sigorjob은 [backend/plugins](/Users/nohgiyoon/Coding/AI/Agent/backend/plugins) 아래의 로컬 플러그인을 지원합니다.

플러그인마다 아래 파일을 선택적으로 넣을 수 있습니다.

- `plugin.py`: 커스텀 툴 등록
- `rules.yaml`: 비AI 규칙 추가
- `ai_instructions.md`: AI 플래너 추가 가이드
- `plugin.json`: 플러그인 이름과 설명

## 빠른 시작

스캐폴드 생성:

```bash
python3 backend/main.py plugins scaffold my_plugin --type hybrid
```

설치된 플러그인 목록 보기:

```bash
python3 backend/main.py plugins list --json
```

## 예제

[backend/plugins/example_echo](/Users/nohgiyoon/Coding/AI/Agent/backend/plugins/example_echo)를 참고하면 됩니다.

추가 예제:

- [backend/plugins/reservation_helper](/Users/nohgiyoon/Coding/AI/Agent/backend/plugins/reservation_helper)
- [backend/plugins/delivery_helper](/Users/nohgiyoon/Coding/AI/Agent/backend/plugins/delivery_helper)
- [backend/plugins/draft_helper](/Users/nohgiyoon/Coding/AI/Agent/backend/plugins/draft_helper)

테스트:

```bash
python3 backend/main.py run "echo plugin hello" --json
```
