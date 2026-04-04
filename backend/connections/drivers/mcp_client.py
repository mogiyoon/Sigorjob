from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import json
from typing import Any, Awaitable, Callable


TransportFactory = Callable[[dict[str, Any]], Awaitable[Any] | Any]


class MCPClient:
    def __init__(
        self,
        server_config: dict[str, Any],
        transport_factory: TransportFactory | None = None,
    ) -> None:
        self.server_config = server_config
        self._transport_factory = transport_factory
        self._transport: Any | None = None

    async def list_tools(self) -> list[dict[str, Any]]:
        transport = await self._get_transport()
        response = await transport.request("tools/list", {})
        tools = response.get("tools", [])
        return [
            {
                "name": item.get("name"),
                "description": item.get("description", ""),
                "inputSchema": item.get("inputSchema", {}),
            }
            for item in tools
            if isinstance(item, dict) and item.get("name")
        ]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        transport = await self._get_transport()
        response = await transport.request(
            "tools/call",
            {"name": tool_name, "arguments": arguments or {}},
        )
        if "result" in response:
            return response["result"]
        return response

    async def close(self) -> None:
        if self._transport is None:
            return
        close = getattr(self._transport, "close", None)
        if close is not None:
            maybe_awaitable = close()
            if asyncio.iscoroutine(maybe_awaitable):
                await maybe_awaitable
        self._transport = None

    async def _get_transport(self) -> Any:
        if self._transport is not None:
            return self._transport

        factory = self._transport_factory
        if factory is None:
            factory = self._default_transport_factory

        transport = factory(self.server_config)
        if asyncio.iscoroutine(transport):
            transport = await transport
        self._transport = transport
        return transport

    def _default_transport_factory(self, server_config: dict[str, Any]) -> Any:
        if importlib.util.find_spec("mcp") is not None:
            transport = _StdioMCPTransport(server_config)
            return transport

        transport = _StdioMCPTransport(server_config)
        return transport


class _StdioMCPTransport:
    def __init__(self, server_config: dict[str, Any]) -> None:
        self.server_config = server_config
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._lock = asyncio.Lock()
        self._initialized = False

    async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            await self._ensure_initialized()
            self._request_id += 1
            request_id = self._request_id
            await self._write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params,
                }
            )
            while True:
                message = await self._read_message()
                if message.get("id") != request_id:
                    continue
                error = message.get("error")
                if error:
                    raise RuntimeError(error.get("message") or "mcp request failed")
                return message.get("result", {})

    async def close(self) -> None:
        if self._process is None:
            return
        if self._process.returncode is None:
            self._process.terminate()
            with contextlib.suppress(ProcessLookupError):
                await self._process.wait()
        self._process = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        transport = str(self.server_config.get("transport") or "stdio").strip().lower()
        if transport != "stdio":
            raise RuntimeError(f"unsupported mcp transport: {transport}")

        command = str(self.server_config.get("command") or "").strip()
        if not command:
            raise RuntimeError("mcp server command is not configured")

        args = self.server_config.get("args") or []
        env = self.server_config.get("env") or None
        self._process = await asyncio.create_subprocess_exec(
            command,
            *[str(arg) for arg in args],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        await self._write_message(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "agent-mcp-client", "version": "1.0.0"},
                },
            }
        )
        response = await self._read_message()
        error = response.get("error")
        if error:
            raise RuntimeError(error.get("message") or "mcp initialize failed")
        await self._write_message(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )
        self._initialized = True

    async def _write_message(self, message: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("mcp server process is not running")
        payload = json.dumps(message).encode("utf-8")
        header = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
        self._process.stdin.write(header + payload)
        await self._process.stdin.drain()

    async def _read_message(self) -> dict[str, Any]:
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("mcp server process is not running")

        content_length: int | None = None
        while True:
            line = await self._process.stdout.readline()
            if line == b"":
                raise RuntimeError("mcp server closed the connection")
            if line in {b"\r\n", b"\n"}:
                break
            decoded = line.decode("ascii").strip()
            if decoded.lower().startswith("content-length:"):
                _, value = decoded.split(":", 1)
                content_length = int(value.strip())

        if content_length is None:
            raise RuntimeError("missing content length from mcp server")

        payload = await self._process.stdout.readexactly(content_length)
        return json.loads(payload.decode("utf-8"))
