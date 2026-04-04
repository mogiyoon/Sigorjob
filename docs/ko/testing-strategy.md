# 테스트 전략

## 목적

이 프로젝트의 테스트는 특정 회귀 방지 계약을 위해 존재합니다.
오늘 AI 없이 작동하는 규칙 기반 경로가, 어떤 변경 후에도 AI 없이 작동한다는 것을
테스트가 증명해야 합니다.
이것은 단순한 코드 품질이 아니라 제품의 핵심 정체성을 보호하는 것입니다.

---

## 테스트 카테고리

### 1. 의도 정규화 테스트 (`test_intent_router.py`)

`detect_intent`, `normalize_command`, `build_last_resort_intent`,
`allows_browser_fallback`이 주어진 한국어/영어 입력에 대해 올바른 출력을 반환하는지 검증합니다.

순수 단위 테스트 — DB, AI, async 없음.

### 2. 라우터 테스트 (`test_intent_router.py`, `test_plugins.py`)

`intent_router.route(command)`가 올바른 `Task` 구조를 반환하는지 검증합니다:
- `task.steps[0].tool`에 올바른 툴
- `task.steps[0].params`에 올바른 params
- 비AI 라우팅 명령은 모두 `task.used_ai == False`

`IsolatedAsyncioTestCase`를 사용한 비동기 테스트.
AI 호출과 trace 기록은 반드시 스텁 처리.

### 3. 플러그인 테스트 (`test_plugins.py`)

- `load_plugins()`로 플러그인 로드됨
- `describe_plugins()`에 플러그인 노출됨
- 플러그인 `run()`이 기대하는 데이터 형태 반환

### 4. 오케스트레이터 테스트 (`test_orchestrator_ai_review.py`)

- 툴 실행이 오케스트레이터를 통해 올바르게 흐름
- `quality.needs_ai_review == True`일 때만 AI 리뷰 호출됨
- 재시도 스텝이 올바르게 삽입됨
- 에러 경로에서 `task.status`가 올바르게 설정됨

### 5. API / 통합 테스트 (`test_api.py`, `test_connection_manager.py`)

- HTTP 엔드포인트가 올바른 상태 코드 반환
- 커넥션 매니저가 연결 상태를 저장하고 조회함

### 6. 품질/결과 테스트 (`test_result_quality.py`, `test_shopping_helper.py`)

- `result_quality.evaluate()`가 올바른 품질 상태 반환
- 플러그인 출력이 품질 평가를 통과함

---

## 커버리지 현황

### 현재 커버되는 항목

| 모듈 | 테스트 파일 | 커버리지 |
|------|-----------|---------|
| `intent/normalizer.py` | `test_intent_router.py` | 높음 |
| `intent/router.py` | `test_intent_router.py`, `test_plugins.py` | 높음 |
| `plugins/*/plugin.py` | `test_plugins.py` | 중간 (라우팅만) |
| `plugins/calendar_helper` | `test_plugins.py` | 높음 (run + 라우팅) |
| `plugins/shopping_helper` | `test_shopping_helper.py` | 중간 |
| `orchestrator/result_quality.py` | `test_result_quality.py` | 중간 |
| `orchestrator/engine.py` | `test_orchestrator_ai_review.py` | 부분적 |
| `connections/manager.py` | `test_connection_manager.py` | 중간 |

### 현재 누락된 항목 (우선순위 순)

| 모듈 | 테스트해야 할 것 | 우선순위 |
|------|--------------|---------|
| `policy/engine.py` | 차단 명령 차단; 허용 명령 통과; 쉘 패턴 차단 | 높음 |
| `orchestrator/engine.py` | 전체 순차 실행; 승인 필요 흐름; 모바일 알림 | 높음 |
| `intent/risk_evaluator.py` | 툴별 위험 레벨 올바르게 할당 | 높음 |
| `custom_commands.py` | `contains` 및 `exact` 매치 타입으로 `match_custom_command` | 높음 |
| `ai/summarizer.py` | `allow_ai=False`일 때 요약 반환; AI 미호출 검증 | 중간 |
| `tools/file/tool.py` | 읽기, 쓰기, 복사, 이동, 삭제 | 중간 |
| `tools/shell/tool.py` | 허용 명령 실행; 차단 명령 오류 | 중간 |
| `tools/crawler/tool.py` | URL 페치 결과 반환 | 중간 |
| `scheduler/service.py` | 스케줄 생성; 스케줄 실행 시 라우트 호출 | 낮음 |

---

## 테스트 패턴

### AI 스텁 처리 (`route()` 호출하는 모든 테스트에 필수)

```python
async def asyncSetUp(self):
    self._orig_plan = intent_router.ai_agent.plan
    self._orig_record = intent_router.record_task_trace

    async def noop_record(*args, **kwargs):
        return None

    intent_router.record_task_trace = noop_record

async def asyncTearDown(self):
    intent_router.ai_agent.plan = self._orig_plan
    intent_router.record_task_trace = self._orig_record
```

### 설정 스토어 스텁

```python
self.config_data: dict = {}
config_store.get = lambda key, default=None: self.config_data.get(key, default)
config_store.set = lambda key, value: self.config_data.__setitem__(key, value)
config_store.delete = lambda key: self.config_data.pop(key, None)
config_store.all = lambda: dict(self.config_data)
```

### 비AI 라우팅 단언

```python
task = await intent_router.route("내일 오후 3시 팀 회의 캘린더에 일정 추가해줘")
self.assertEqual(task.steps[0].tool, "calendar_helper")
self.assertFalse(task.used_ai)  # 이것이 핵심 단언
```

### AI가 호출되지 않았음을 단언

```python
async def fail_if_called(command, history):
    raise AssertionError("AI should not have been called")

intent_router.ai_agent.request_clarification = fail_if_called
task = await intent_router.route("4월 11일 16시에 벚꽃 일정 추가해줘")
# 여기까지 오면 AI가 호출되지 않은 것
self.assertEqual(task.steps[0].tool, "calendar_helper")
```

---

## 새 테스트 작성 규칙

1. **모든 새 플러그인은 `used_ai=False`를 증명하는 라우팅 테스트를 포함해야 합니다.**
   비AI 우선 계약의 핵심 회귀 방지 장치입니다.

2. **모든 새 플러그인은 `run()` 테스트를 포함해야 합니다.**
   현실적인 params로 성공 케이스를 테스트합니다.
   필수 param 누락 또는 잘못된 상태의 실패 케이스를 테스트합니다.

3. **`rules.yaml`의 모든 새 규칙은 패턴 매칭 테스트와 비매칭 테스트를 포함해야 합니다.**
   패턴 매칭 테스트: 트리거 문구가 올바른 툴로 라우팅됨.
   비매칭 테스트: 유사하지만 다른 문구가 매칭되지 않음.

4. **모든 라우터 테스트에서 AI를 스텁 처리해야 합니다.**
   라우터 테스트는 실제 API 호출을 해서는 안 됩니다.

5. **테스트는 외부 서비스에 의존해서는 안 됩니다.**
   실제 HTTP 호출, 실제 DB 쓰기 없음 (인메모리 스텁 또는 `persist=False` 사용).

6. **`tearDown` / `asyncTearDown`에서 스텁을 복원해야 합니다.**
   테스트 간 오염을 방지하기 위해 항상 원본을 복원합니다.

---

## 테스트 실행

```bash
cd backend
python -m pytest tests/ -v

# 특정 파일 실행
python -m pytest tests/test_plugins.py -v

# 특정 테스트 실행
python -m pytest tests/test_plugins.py::PluginRouteTests::test_calendar_plugin_route -v
```

모든 테스트는 PR 머지 전에 통과해야 합니다.
