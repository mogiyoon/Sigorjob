from __future__ import annotations

from typing import Any

from config.store import config_store
from connections.base import Connection, ConnectionExecutionResult
from connections.drivers import list_connector_drivers
from connections.registry import list_connections


def _granted_permissions() -> set[str]:
    return set(config_store.get("granted_permissions", []))


def _connection_allows(connection: Connection, capability: str) -> bool:
    required_permissions = set(connection.get("required_permissions") or [])
    capability_permissions = set((connection.get("capability_permissions") or {}).get(capability, []))
    needed = required_permissions | capability_permissions
    granted = _granted_permissions()
    return needed.issubset(granted)


async def find_connection_for_capability(capability: str) -> Connection | None:
    for driver in list_connector_drivers():
        for connection in list_connections():
            if not driver.supports(connection, capability):
                continue
            if capability not in set(connection.get("capabilities") or []):
                continue
            if not _connection_allows(connection, capability):
                continue
            if await driver.is_ready(connection):
                return connection
    return None


async def execute_capability(capability: str, payload: dict[str, Any]) -> ConnectionExecutionResult:
    for driver in list_connector_drivers():
        for connection in list_connections():
            if not driver.supports(connection, capability):
                continue
            if capability not in set(connection.get("capabilities") or []):
                continue
            if not _connection_allows(connection, capability):
                continue
            if not await driver.is_ready(connection):
                continue
            result = await driver.execute(connection, capability, payload)
            if result.handled:
                return result
    return ConnectionExecutionResult(
        success=False,
        handled=False,
        error=f"no ready connection for capability: {capability}",
    )
