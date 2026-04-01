from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


Connection = dict[str, Any]


@dataclass
class ConnectionExecutionResult:
    success: bool
    handled: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseConnectorDriver(ABC):
    driver_id: str = ""
    connection_ids: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()

    def supports(self, connection: Connection, capability: str) -> bool:
        return (
            (
                connection.get("driver_id") == self.driver_id
                or connection.get("id") in self.connection_ids
            )
            and capability in self.capabilities
        )

    @abstractmethod
    async def is_ready(self, connection: Connection) -> bool:
        ...

    @abstractmethod
    async def execute(
        self,
        connection: Connection,
        capability: str,
        payload: dict[str, Any],
    ) -> ConnectionExecutionResult:
        ...
