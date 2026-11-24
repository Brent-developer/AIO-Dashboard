from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class BiometricDriver(ABC):
    """Async contract implemented by every manufacturer integration."""

    def __init__(self, host: str, port: int, **options: Any) -> None:
        self.host = host
        self.port = port
        self.options = options

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def test_connection(self) -> bool: ...

    @abstractmethod
    async def get_users(self, since: datetime | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def create_user(self, user: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def update_user(self, user_id: str, user: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def delete_user(self, user_id: str) -> None: ...

    @abstractmethod
    async def get_attendance_logs(self, since: datetime | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def push_user(self, user: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def delete_template(self, user_id: str, template_id: str) -> None: ...

    @abstractmethod
    async def push_card(self, user_id: str, card_number: str) -> None: ...

    @abstractmethod
    async def push_pin(self, user_id: str, pin: str) -> None: ...

    @abstractmethod
    async def sync_time(self, value: datetime | None = None) -> None: ...

    @abstractmethod
    async def restart_device(self) -> None: ...

    @abstractmethod
    async def get_device_info(self) -> dict[str, Any]: ...

    @abstractmethod
    async def health_check(self) -> dict[str, Any]: ...
