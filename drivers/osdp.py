from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from core.base_driver import BiometricDriver


class OSDPDriver(BiometricDriver):
    """Async adapter around the optional `osdp` package for an RS-485 PD."""

    def __init__(self, host: str, port: int = 9600, **options: Any) -> None:
        super().__init__(host, port, **options)
        self.serial_port = options.get("serial_port", host)
        self.baud_rate = int(options.get("baud_rate", port))
        self.address = int(options.get("address", 0))
        scbk = options.get("scbk")
        self.scbk = bytes.fromhex(scbk) if isinstance(scbk, str) else scbk
        if self.scbk is not None and len(self.scbk) != 16:
            raise ValueError("OSDP SCBK must be an AES-128 (16-byte) key")
        self._connection: Any = None

    def _load_library(self) -> Any:
        try:
            import osdp  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Install the optional 'osdp' package to use the OSDP driver") from exc
        return osdp

    def establish_secure_channel(self, server_random: bytes, client_random: bytes) -> bytes:
        if not self.scbk:
            raise ValueError("SCBK is required for OSDP Secure Channel")
        if len(server_random) != 8 or len(client_random) != 8:
            raise ValueError("OSDP random challenges must be 8 bytes each")
        cipher = Cipher(algorithms.AES(self.scbk), modes.ECB()).encryptor()
        return cipher.update(server_random + client_random) + cipher.finalize()

    async def connect(self) -> None:
        library = self._load_library()
        constructor = getattr(library, "ControlPanel", None) or getattr(library, "OSDP", None)
        if constructor is None:
            raise RuntimeError("Installed osdp package has no ControlPanel/OSDP entry point")
        self._connection = await asyncio.to_thread(
            constructor,
            port=self.serial_port,
            baud_rate=self.baud_rate,
            address=self.address,
            scbk=self.scbk,
        )
        start = getattr(self._connection, "start", None)
        if start:
            await asyncio.to_thread(start)

    async def disconnect(self) -> None:
        if self._connection:
            close = getattr(self._connection, "close", None) or getattr(self._connection, "stop", None)
            if close:
                await asyncio.to_thread(close)
        self._connection = None

    async def _call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        if not self._connection:
            await self.connect()
        method = getattr(self._connection, name, None)
        if not method:
            raise NotImplementedError(f"The installed osdp library does not expose {name}()")
        return await asyncio.to_thread(method, *args, **kwargs)

    async def test_connection(self) -> bool:
        try:
            result = await self._call("poll")
            return result is not False
        except (OSError, RuntimeError, NotImplementedError):
            return False

    async def get_users(self, since: datetime | None = None) -> list[dict[str, Any]]:
        return list(await self._call("get_users", since=since))

    async def create_user(self, user: dict[str, Any]) -> dict[str, Any]:
        await self._call("set_user", user)
        return user

    async def update_user(self, user_id: str, user: dict[str, Any]) -> dict[str, Any]:
        return await self.create_user({**user, "user_id": user_id})

    async def delete_user(self, user_id: str) -> None:
        await self._call("delete_user", user_id)

    async def get_attendance_logs(self, since: datetime | None = None) -> list[dict[str, Any]]:
        return list(await self._call("get_events", since=since))

    async def push_user(self, user: dict[str, Any]) -> dict[str, Any]:
        return await self.create_user(user)

    async def delete_template(self, user_id: str, template_id: str) -> None:
        await self._call("delete_template", user_id, template_id)

    async def push_card(self, user_id: str, card_number: str) -> None:
        await self._call("set_credential", user_id, "card", card_number)

    async def push_pin(self, user_id: str, pin: str) -> None:
        await self._call("set_credential", user_id, "pin", pin)

    async def sync_time(self, value: datetime | None = None) -> None:
        await self._call("set_time", value or datetime.now(timezone.utc))

    async def restart_device(self) -> None:
        await self._call("reset")

    async def get_device_info(self) -> dict[str, Any]:
        return dict(await self._call("get_device_info"))

    async def health_check(self) -> dict[str, Any]:
        return {"online": await self.test_connection(), "secure_channel": bool(self.scbk), "address": self.address}
