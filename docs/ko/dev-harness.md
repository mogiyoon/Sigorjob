# 개발 하네스

## 개요

개발 하네스는 **스펙 → 구현 → 테스트 → 리뷰 → PR** 루프를 자동화하는 오케스트레이터 스크립트입니다.
Codex CLI를 호출하여 코드를 구현하고, 테스트로 검증하고, 선택적으로 코드 리뷰를 실행합니다 — 수동 개입 없이.

SWE-bench / SWE-Agent 패턴을 따릅니다:
**오케스트레이터가 구조화된 입력 → 에이전트가 샌드박스에서 실행 → 테스트가 검증 → 오케스트레이터가 판단 → 재시도 또는 완료.**

---

## 아키텍처

```text
Claude Code (기획)
    │
    │  스펙 JSON 작성
    ↓
scripts/dev-harness.py
    │
    ├── 1. SETUP     git checkout -b {branch}
    │
    ├── 2. IMPLEMENT  codex exec --full-auto --json --ephemeral
    │                  (AGENTS.md + 스펙을 프롬프트로 전송)
    │
    ├── 3. TEST       python3 -m unittest (포커스 + 전체)
    │
    ├── 4. REVIEW     codex exec review --uncommitted (선택)
    │
    └── 5. JUDGE
            ├── 통과 → git commit → (선택) gh pr create
            └── 실패 → 실패 상세 포함 재시도 프롬프트 → 2번으로
                       (최대 N회)
```

---

## 하네스 = 구조화된 입출력 제어 루프

하네스는 다음 패턴으로 정의됩니다:

```
오케스트레이터 ──구조화된 입력──→ 실행기
     ↑                              │
     └────구조화된 출력────────────────┘
     → 판단 → 다음 지시 or 종료
```

실행기가 Codex든, Claude 서브에이전트든, 다른 도구든 상관없습니다.
핵심은: **구조화된 데이터 입력, 구조화된 데이터 출력, 오케스트레이터가 다음을 결정.**

---

## 파일 구조

```
scripts/
  dev-harness.py              # 하네스 메인 스크립트 (~400줄, stdlib만 사용)
  harness-specs/              # 입력 스펙 JSON 파일
  harness-results/            # 출력 결과 (gitignore 대상)
```

---

## 사용법

```bash
# 드라이런 — Codex에 보낼 프롬프트 확인
python3 scripts/dev-harness.py --spec scripts/harness-specs/my-spec.json --dry-run

# 구현 + 테스트 실행 (리뷰 생략)
python3 scripts/dev-harness.py --spec scripts/harness-specs/my-spec.json --no-review

# 전체 실행 (리뷰 포함)
python3 scripts/dev-harness.py --spec scripts/harness-specs/my-spec.json

# 실행 + PR 생성
python3 scripts/dev-harness.py --spec scripts/harness-specs/my-spec.json --pr
```

---

## 재시도 로직

테스트 실패 또는 리뷰 거부 시:
1. 하네스가 재시도 프롬프트를 생성:
   - 원본 AGENTS.md + 스펙
   - 실패 유형 (test_failed 또는 review_rejected)
   - 실패 상세 (pytest 출력 또는 리뷰 피드백)
   - 명시적 지시: "수정하라, 처음부터 다시 쓰지 마라"
2. Codex가 이전 시도의 파일을 읽고 (디스크에 남아있음) 패치
3. 테스트 재실행

---

## 개발 워크플로우와의 연동

하네스는 3자 협업 워크플로우(`docs/ko/dev-workflow.md`)에 통합됩니다:

1. **Claude Code (기획)** — 스펙 JSON 작성
2. **하네스** — Codex를 구현자+리뷰어로 실행
3. **결과** — 커밋된 브랜치 또는 PR (최종 사람 리뷰 대기)

하네스는 기획자와 구현자 사이의 수동 복사-붙여넣기를 대체합니다.
