import re

from tools.ai_process.tool import AIProcessTool, MAX_INPUT_CHARS
from tools.base import BaseTool

DEFAULT_MAX_LENGTH = 200
FALLBACK_SENTENCE_COUNT = 3


class SummarizeTool(BaseTool):
    name = "summarize"
    description = "텍스트를 AI로 요약하고, 키가 없으면 앞부분을 추출 요약합니다."

    def __init__(self) -> None:
        self.ai_process_tool = AIProcessTool()

    async def run(self, params: dict) -> dict:
        text = str(params.get("text") or "").strip()
        if not text:
            return {"success": False, "data": None, "error": "missing text"}

        language = str(params.get("language") or "auto-detect")
        max_length = self._coerce_max_length(params.get("max_length"))
        instruction = self._build_instruction(language=language, max_length=max_length)

        result = await self.ai_process_tool.run(
            {
                "text": text,
                "instruction": instruction,
                "language": None if language == "auto-detect" else language,
            }
        )
        if not result["success"]:
            return result

        processed_result = str(result["data"]["result"])
        if processed_result.startswith("AI processing unavailable"):
            summary = self._extractive_summary(text)
        else:
            summary = processed_result

        return {
            "success": True,
            "data": {"summary": summary, "language": language},
            "error": None,
        }

    def _build_instruction(self, *, language: str, max_length: int) -> str:
        response_language = (
            "the same language as the input"
            if language == "auto-detect"
            else language
        )
        return (
            "Summarize this text concisely.\n"
            f"Respond in {response_language}.\n"
            f"Keep the summary within about {max_length} characters."
        )

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
