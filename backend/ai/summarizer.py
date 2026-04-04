from ai.runtime import get_client, has_api_key
from logger.logger import get_logger

logger = get_logger(__name__)


async def summarize(command: str, results: list[dict], *, allow_ai: bool = True) -> str:
    """실행 결과를 자연어로 요약."""
    client = get_client()
    if not allow_ai or not has_api_key() or client is None:
        return _fallback_summary(results)

    results_text = "\n".join(
        f"- step {i+1}: {'success' if r.get('success') else 'failed'} — {r.get('data') or r.get('error')}"
        for i, r in enumerate(results)
    )
    prompt = f"User command: {command}\n\nExecution results:\n{results_text}\n\nSummarize the result in 1-2 sentences in Korean."

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.error(f"summarization failed: {e}")
        return _fallback_summary(results)


def _fallback_summary(results: list[dict]) -> str:
    if not results:
        return "실행 결과가 없습니다."

    first = results[0]
    if len(results) == 1:
        if first.get("success"):
            data = first.get("data") or {}
            quality = first.get("quality") or {}
            if quality.get("status") == "partial" and quality.get("message"):
                return str(quality["message"])
            if isinstance(data, dict) and data.get("links"):
                return "관련 링크를 찾아 바로 열어볼 수 있게 준비했습니다."
            if isinstance(data, dict) and data.get("action") == "schedule_created":
                name = str(data.get("name") or "반복 작업")
                source_name = str(data.get("source_name") or "지정한 페이지")
                return f"{name} 작업을 등록했습니다. {source_name} 확인 결과는 앱 작업 목록에서 볼 수 있습니다."
            if isinstance(data, dict) and data.get("action") == "schedule_draft":
                name = str(data.get("name") or "반복 작업")
                return f"{name} 초안을 만들었습니다. 현재 환경에서는 자동 저장이 막혀 있어 설정 화면이나 쓰기 가능한 환경에서 등록이 필요합니다."
            if isinstance(data, dict) and data.get("action") == "open_url":
                title = str(data.get("title") or "")
                url = str(data.get("url") or "")
                calendar = data.get("calendar") or {}
                if isinstance(calendar, dict) and calendar.get("summary"):
                    event_title = str(calendar.get("title") or "일정")
                    return (
                        f"{calendar['summary']} Google 캘린더에 추가하는 링크가 생성되었습니다. "
                        f"아래 링크를 클릭하여 일정을 최종 저장해 주세요! 🌸"
                    )
                if data.get("translation"):
                    return "번역 페이지를 바로 열 수 있게 준비했습니다."
                if data.get("shopping") and data.get("purchase_intent"):
                    return "구매를 이어갈 수 있도록 쇼핑 페이지를 준비했습니다. 결제 전 상품과 가격을 한 번 더 확인해주세요."
                if url.startswith("mailto:"):
                    return "메일 작성 화면을 바로 열 수 있게 준비했습니다."
                if url.startswith("tel:"):
                    return "전화 앱에서 바로 연결할 수 있게 준비했습니다."
                if url.startswith("sms:"):
                    return "문자 작성 화면을 바로 열 수 있게 준비했습니다."
                if "shopping" in url or "coupang" in url or "11st" in url or "gmarket" in url or "쇼핑" in title:
                    return "관련 상품을 바로 찾아볼 수 있도록 쇼핑 링크를 준비했습니다."
                if "google.com/maps" in url or "map.naver.com" in url or "지도" in title:
                    return "관련 장소를 바로 찾아볼 수 있도록 지도 링크를 준비했습니다."
                return "관련 페이지를 바로 열어볼 수 있게 준비했습니다."
            if isinstance(data, dict) and data.get("draft_type") == "email":
                return "이메일 초안을 준비했습니다."
            if isinstance(data, dict) and data.get("draft_type") == "message":
                return "메시지 초안을 준비했습니다."
            if isinstance(data, dict) and data.get("url"):
                return "웹 페이지를 읽어와 결과를 준비했습니다."
            return "요청한 작업을 완료했습니다."
        error = first.get("error") or "작업 실행에 실패했습니다."
        return str(error)

    success_count = sum(1 for r in results if r.get("success"))
    if success_count == len(results):
        return "요청한 작업을 모두 완료했습니다."
    if success_count == 0:
        return "요청한 작업을 처리하지 못했습니다."
    return "일부 작업은 완료했지만, 일부는 실패했습니다."
