import asyncio
import shlex
from tools.base import BaseTool
from policy import engine as policy
from config.settings import settings
from logger.logger import get_logger

logger = get_logger(__name__)


class ShellTool(BaseTool):
    name = "shell"
    description = "허용된 쉘 명령 실행"

    async def run(self, params: dict) -> dict:
        command: str = params.get("command", "").strip()
        if not command:
            return {"success": False, "data": None, "error": "command is required"}

        # 정책 검사
        allowed, reason = policy.check_shell(command)
        if not allowed:
            logger.warning(f"blocked shell command: {command} — {reason}")
            return {"success": False, "data": None, "error": f"policy blocked: {reason}"}

        # 허용 명령어 목록 검사
        try:
            argv = shlex.split(command)
        except ValueError as e:
            return {"success": False, "data": None, "error": f"invalid command: {e}"}

        if not argv:
            return {"success": False, "data": None, "error": "command is required"}

        cmd_base = argv[0]
        if cmd_base not in settings.allowed_shell_commands:
            return {"success": False, "data": None, "error": f"command not in allowlist: {cmd_base}"}

        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode == 0:
                return {"success": True, "data": stdout.decode(), "error": None}
            else:
                return {"success": False, "data": stdout.decode(), "error": stderr.decode()}
        except asyncio.TimeoutError:
            return {"success": False, "data": None, "error": "command timed out (30s)"}
        except Exception as e:
            return {"success": False, "data": None, "error": str(e)}
