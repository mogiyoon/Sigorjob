from dataclasses import dataclass, asdict


@dataclass
class QualityEvaluation:
    status: str
    message: str
    issues: list[str]
    needs_ai_review: bool = False
    blocking: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


INTERSTITIAL_MARKERS = (
    "몇 초 안에 이동하지 않는 경우",
    "click here",
    "google search",
    "if you're having trouble accessing google search",
    "unusual traffic",
    "captcha",
    "access denied",
)


def evaluate(tool: str, params: dict, result: dict) -> QualityEvaluation:
    if not result.get("success"):
        return QualityEvaluation(
            status="failed",
            message=str(result.get("error") or "작업 실행에 실패했습니다."),
            issues=[],
            blocking=True,
        )

    if tool == "crawler":
        return _evaluate_crawler(params, result)
    if tool == "browser":
        return _evaluate_browser(result)
    if tool == "file":
        return _evaluate_file(params, result)
    if tool == "shell":
        return _evaluate_shell(result)

    return QualityEvaluation(status="sufficient", message="결과 품질이 충분합니다.", issues=[])


def _evaluate_crawler(params: dict, result: dict) -> QualityEvaluation:
    data = result.get("data") or {}
    text = str(data.get("text") or "").strip()
    links = data.get("links") or []
    lower_text = text.lower()

    issues: list[str] = []
    if any(marker in lower_text for marker in INTERSTITIAL_MARKERS):
        issues.append("검색 엔진 중간 안내문 또는 차단 페이지로 보이는 내용이 포함되어 있습니다.")

    if links:
        if len(links) >= 3:
            if issues:
                return QualityEvaluation(
                    status="partial",
                    message="관련 링크는 찾았지만, 결과 일부에 안내문 성격의 내용이 섞여 있습니다.",
                    issues=issues,
                    needs_ai_review=False,
                )
            return QualityEvaluation(
                status="sufficient",
                message="관련 링크를 충분히 찾았습니다.",
                issues=[],
            )
        return QualityEvaluation(
            status="partial",
            message="관련 링크는 찾았지만 수가 적습니다.",
            issues=issues + ["관련 링크 수가 3개 미만입니다."],
            needs_ai_review=False,
        )

    if issues:
        return QualityEvaluation(
            status="insufficient",
            message="검색 결과 대신 안내문이나 차단 페이지가 표시되어 원하는 결과를 충분히 얻지 못했습니다.",
            issues=issues,
            needs_ai_review=True,
            blocking=True,
        )

    if len(text) < 80:
        return QualityEvaluation(
            status="insufficient",
            message="가져온 본문이 너무 짧아서 원하는 결과를 충분히 담고 있지 않습니다.",
            issues=["본문 길이가 너무 짧습니다."],
            needs_ai_review=True,
            blocking=True,
        )

    return QualityEvaluation(
        status="sufficient",
        message="본문 텍스트를 충분히 가져왔습니다.",
        issues=[],
    )


def _evaluate_browser(result: dict) -> QualityEvaluation:
    data = result.get("data") or {}
    action = data.get("action")
    url = str(data.get("url") or "")
    if action != "open_url" or not url.startswith(("http://", "https://", "mailto:", "tel:", "sms:")):
        return QualityEvaluation(
            status="insufficient",
            message="열기 동작에 필요한 링크 정보가 올바르지 않습니다.",
            issues=["open_url 액션 또는 URL 정보가 누락되었습니다."],
            blocking=True,
        )
    return QualityEvaluation(status="sufficient", message="열기 링크를 준비했습니다.", issues=[])


def _evaluate_file(params: dict, result: dict) -> QualityEvaluation:
    operation = params.get("operation")
    data = result.get("data")

    if operation == "read":
        content = str(data or "").strip()
        if not content:
            return QualityEvaluation(
                status="partial",
                message="파일은 읽었지만 내용이 비어 있습니다.",
                issues=["읽은 파일 내용이 비어 있습니다."],
            )
        return QualityEvaluation(status="sufficient", message="파일 내용을 읽었습니다.", issues=[])

    return QualityEvaluation(status="sufficient", message="파일 작업을 완료했습니다.", issues=[])


def _evaluate_shell(result: dict) -> QualityEvaluation:
    output = str(result.get("data") or "").strip()
    if not output:
        return QualityEvaluation(
            status="partial",
            message="명령은 실행했지만 출력은 비어 있습니다.",
            issues=["stdout 출력이 비어 있습니다."],
        )
    return QualityEvaluation(status="sufficient", message="명령 결과를 얻었습니다.", issues=[])
