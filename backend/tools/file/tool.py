from tools.base import BaseTool
from policy import engine as policy
import aiofiles
import shutil
from pathlib import Path
from logger.logger import get_logger

logger = get_logger(__name__)


class FileTool(BaseTool):
    name = "file"
    description = "로컬 파일 읽기/쓰기/복사/이동/삭제"

    async def run(self, params: dict) -> dict:
        operation = params.get("operation")  # read | write | copy | move | delete

        if operation == "read":
            return await self._read(params["path"])
        elif operation == "write":
            return await self._write(params["path"], params["content"])
        elif operation == "copy":
            return await self._copy(params["src"], params["dst"])
        elif operation == "move":
            return await self._move(params["src"], params["dst"])
        elif operation == "delete":
            return await self._delete(params["path"])
        else:
            return {"success": False, "data": None, "error": f"unknown operation: {operation}"}

    async def _read(self, path: str) -> dict:
        allowed, reason = policy.check_file(path, "read")
        if not allowed:
            return {"success": False, "data": None, "error": reason}
        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                content = await f.read()
            return {"success": True, "data": content, "error": None}
        except Exception as e:
            return {"success": False, "data": None, "error": str(e)}

    async def _write(self, path: str, content: str) -> dict:
        allowed, reason = policy.check_file(path, "write")
        if not allowed:
            return {"success": False, "data": None, "error": reason}
        try:
            Path(path).expanduser().resolve(strict=False).parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(content)
            return {"success": True, "data": f"written to {path}", "error": None}
        except Exception as e:
            return {"success": False, "data": None, "error": str(e)}

    async def _copy(self, src: str, dst: str) -> dict:
        allowed, reason = policy.check_file(src, "read")
        if not allowed:
            return {"success": False, "data": None, "error": reason}
        allowed, reason = policy.check_file(dst, "copy_dst")
        if not allowed:
            return {"success": False, "data": None, "error": reason}
        try:
            Path(dst).expanduser().resolve(strict=False).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return {"success": True, "data": f"copied {src} → {dst}", "error": None}
        except Exception as e:
            return {"success": False, "data": None, "error": str(e)}

    async def _move(self, src: str, dst: str) -> dict:
        allowed, reason = policy.check_file(src, "read")
        if not allowed:
            return {"success": False, "data": None, "error": reason}
        allowed, reason = policy.check_file(dst, "move_dst")
        if not allowed:
            return {"success": False, "data": None, "error": reason}
        try:
            Path(dst).expanduser().resolve(strict=False).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
            return {"success": True, "data": f"moved {src} → {dst}", "error": None}
        except Exception as e:
            return {"success": False, "data": None, "error": str(e)}

    async def _delete(self, path: str) -> dict:
        allowed, reason = policy.check_file(path, "delete")
        if not allowed:
            return {"success": False, "data": None, "error": reason}
        try:
            resolved = Path(path).expanduser().resolve(strict=False)
            if not resolved.exists():
                return {"success": False, "data": None, "error": f"file not found: {path}"}
            if resolved.is_dir():
                return {"success": False, "data": None, "error": "directory deletion is not supported"}
            resolved.unlink()
            return {"success": True, "data": f"deleted {path}", "error": None}
        except Exception as e:
            return {"success": False, "data": None, "error": str(e)}
