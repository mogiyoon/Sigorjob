import re

from ai import runtime
from logger.logger import get_logger
from tools.base import BaseTool

logger = get_logger(__name__)

DEFAULT_MAX_LENGTH = 200
MAX_INPUT_CHARS = 10000
FALLBACK_SENTENCE_COUNT = 3


class SummarizeTool(BaseTool):
    name = "summarize"
    description = "텍스트를 AI로 요약하고, 키가 없으면 앞부분을 추출 요약합니다."

    async def run(self, params: dict) -> dict:
        text = str(params.get("text") or "").strip()
        if not text:
            return {"success": False, "data": None, "error": "missing text"}

        language = str(params.get("language") or "auto-detect")
        max_length = self._coerce_max_length(params.get("max_length"))

        client = runtime.get_client()
        if not runtime.has_api_key() or client is None:
            return self._fallback_result(text, language)

        truncated_text = text[:MAX_INPUT_CHARS]
        prompt = self._build_prompt(
            text=truncated_text,
            language=language,
            max_length=max_length,
        )

        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = message.content[0].text.strip()
            return {
                "success": True,
                "data": {"summary": summary, "language": language},
                "error": None,
            }
        except Exception as exc:
            logger.error(f"summarize tool failed, using fallback: {exc}")
            return self._fallback_result(text, language)

    def _build_prompt(self, *, text: str, language: str, max_length: int) -> str:
        response_language = (
            "the same language as the input"
            if language == "auto-detect"
            else language
        )
        return (
            "Summarize the following text.\n"
            f"Respond in {response_language}.\n"
            f"Keep the summary within about {max_length} characters.\n\n"
            "Text to summarize:\n"
            f"{text}"
        )

    def _fallback_result(self, text: str, language: str) -> dict:
        return {
            "success": True,
            "data": {
                "summary": self._extractive_summary(text),
                "language": language,
            },
            "error": None,
        }

    def _extractive_summary(self, text: str) -> str:
        normalized = " ".join(text.split()).strip()
        if not normalized:
            return ""

        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?。！？])\s+", normalized)
            if sentence.strip()
        ]
        if not sentences:
            return normalized
        return " ".join(sentences[:FALLBACK_SENTENCE_COUNT])

    def _coerce_max_length(self, value: object) -> int:
        try:
            max_length = int(value)
        except (TypeError, ValueError):
            return DEFAULT_MAX_LENGTH
        return max_length if max_length > 0 else DEFAULT_MAX_LENGTH
