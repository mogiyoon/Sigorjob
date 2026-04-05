# Improve Harness — 자기 개선 AI 루프

사람 개입 없이 자동으로 제품의 갭을 발견하고 수정합니다.

---

## 아키텍처

```
python3 scripts/improve-harness.py --rounds N --commands M

큰 사이클 (× N라운드, 매번 새 명령 생성)
  │
  │  [1] 사용자 에이전트 (Claude API)
  │      실제 사용자가 할 법한 명령 M개 생성
  │
  └─→ 작은 사이클 (전부 통과하거나 최대 횟���까지 반복)
        │
        ├── [2] 실행 (로컬, route() → run())
        │       실제 파이프라인으로 각 명령 실행
        │
        ├── [3] 듀얼 평가 (Claude + Codex)
        │       둘 다 독립 평가, 나쁜 쪽 우선
        │
        ├── [4] 자동 수정 (dev-harness → Codex)
        │       실패별 스펙 생성 → Codex가 구현
        │
        ├── [5] 회귀 검증 (eval-harness)
        │       기존 37+ 시나리오 통과 확인
        │
        └── 같은 명령 재실행 → [2]로 돌아감
```

---

## 큰 사이클 vs 작은 사이클

| | 큰 사이클 | 작은 사이클 |
|---|---|---|
| 목적 | 새로운 갭 발견 | 알려진 갭 수정 |
| 명령 | 새로 생성 | 같은 명령 재실행 |
| 종료 조건 | 모든 라운드 완료 | 전부 통과 또는 최대 횟수 |

---

## 듀얼 평가

Claude와 Codex가 독립 평가. **나쁜 쪽이 우선** — 자기 평가 편향 방지.

---

## 사용법

```bash
python3 scripts/improve-harness.py                          # 1라운드, 10개
python3 scripts/improve-harness.py --rounds 3 --commands 20 # 3라운드, 20개씩
python3 scripts/improve-harness.py --no-fix                 # 평가만
python3 scripts/improve-harness.py --evaluator codex        # Codex만 평가
```

---

## 하네스 연결

```
improve-harness.py  ← 전체 오케스트레이터
    ├── 직접: route() → run()   (앱 파이프라인)
    ├── 호출: dev-harness.py    (Codex가 수정 구현)
    └── 호출: eval-harness.py   (회귀 검증)
```
