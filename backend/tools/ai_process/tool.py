from ai import runtime
from logger.logger import get_logger
from tools.base import BaseTool

logger = get_logger(__name__)

MODEL_NAME = "claude-sonnet-4-6"
MAX_TOKENS = 2048
MAX_INPUT_CHARS = 10000
FALLBACK_CHARS = 500
SYSTEM_PROMPT = (
    "Process the given text according to the instruction. "
    "Return only the processed result."
)


class AIProcessTool(BaseTool):
    name = "ai_process"
    description = "텍스트와 지시문을 받아 범용 AI 텍스트 처리를 수행합니다."

    async def run(self, params: dict) -> dict:
        text = str(params.get("text") or "").strip()
        if not text:
            return {"success": False, "data": None, "error": "missing text"}

        instruction = str(params.get("instruction") or "").strip()
        if not instruction:
            return {"success": False, "data": None, "error": "missing instruction"}

        language = str(params.get("language") or "").strip() or None
        truncated_text = text[:MAX_INPUT_CHARS]

        client = runtime.get_client()
        if not runtime.has_api_key() or client is None:
            return self._fallback_result(
                text=truncated_text,
                instruction=instruction,
            )

        try:
            message = client.messages.create(
                model=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": self._build_user_prompt(
                            text=truncated_text,
                            instruction=instruction,
                            language=language,
                        ),
                    }
                ],
            )
            result = message.content[0].text.strip()
            return {
                "success": True,
                "data": {"result": result, "instruction": instruction},
                "error": None,
            }
        except Exception as exc:
            logger.error(f"ai_process tool failed, using fallback: {exc}")
            return self._fallback_result(
                text=truncated_text,
                instruction=instruction,
            )

    def _build_user_prompt(
        self,
        *,
        text: str,
        instruction: str,
        language: str | None,
    ) -> str:
        prompt = f"Instruction: {instruction}\n"
        if language:
            prompt += f"Respond in {language}.\n"
        prompt += f"\nText:\n{text}"
        return prompt

    def _fallback_result(self, *, text: str, instruction: str) -> dict:
        return {
            "success": True,
            "data": {
                "result": f"AI processing unavailable\n\n{text[:FALLBACK_CHARS]}",
                "instruction": instruction,
            },
            "error": None,
        }
