from __future__ import annotations

import asyncio
import json
import struct
from datetime import datetime, timezone
from typing import Any

from core.base_driver import BiometricDriver


class ZKTecoDriver(BiometricDriver):
    CMD_CONNECT = 1000
    CMD_EXIT = 1001
    CMD_RESTART = 1004
    CMD_GET_TIME = 201
    CMD_SET_TIME = 202
    CMD_GET_USERS = 9
    CMD_SET_USER = 8
    CMD_DELETE_USER = 18
    CMD_GET_ATTENDANCE = 1503
    CMD_DELETE_TEMPLATE = 19
    CMD_DEVICE_INFO = 11
    CMD_ACK_OK = 2000
    HEADER = struct.Struct("<HHHH")

    def __init__(self, host: str, port: int = 4370, **options: Any) -> None:
        super().__init__(host, port, **options)
        self.timeout = float(options.get("timeout", 10))
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._session_id = 0
        self._reply_id = 0

    @staticmethod
    def _checksum(data: bytes) -> int:
        total = sum(struct.unpack(f"<{len(data) // 2}H", data[: len(data) & ~1]))
        if len(data) % 2:
            total += data[-1]
        total = (total & 0xFFFF) + (total >> 16)
        total = (total & 0xFFFF) + (total >> 16)
        return (~total) & 0xFFFF

    def _packet(self, command: int, payload: bytes = b"") -> bytes:
        header_without_checksum = self.HEADER.pack(command, 0, self._session_id, self._reply_id)
        checksum = self._checksum(header_without_checksum + payload)
        return self.HEADER.pack(command, checksum, self._session_id, self._reply_id) + payload

    async def _command(self, command: int, payload: bytes = b"") -> bytes:
        if not self._reader or not self._writer:
            raise ConnectionError("ZKTeco device is not connected")
        self._reply_id = (self._reply_id + 1) & 0xFFFF
        self._writer.write(self._packet(command, payload))
        await self._writer.drain()
        header = await asyncio.wait_for(self._reader.readexactly(self.HEADER.size), self.timeout)
        response_command, checksum, session_id, reply_id = self.HEADER.unpack(header)
        self._session_id, self._reply_id = session_id, reply_id
        # ZK devices may return one response packet per TCP read; consume the currently
        # available response body without inventing a proprietary length prefix.
        await asyncio.sleep(0)
        body = b""
        while True:
            try:
                chunk = await asyncio.wait_for(self._reader.read(65535), timeout=0.05)
            except TimeoutError:
                break
            if not chunk:
                break
            body += chunk
            if len(chunk) < 65535:
                break
        expected = self._checksum(self.HEADER.pack(response_command, 0, session_id, reply_id) + body)
        if checksum not in (0, expected):
            raise ValueError("ZKTeco response checksum mismatch")
        if response_command not in (self.CMD_ACK_OK, command):
            raise RuntimeError(f"ZKTeco command {command} failed with response {response_command}")
        return body

    async def connect(self) -> None:
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), self.timeout
        )
        await self._command(self.CMD_CONNECT)

    async def disconnect(self) -> None:
        if self._writer:
            try:
                await self._command(self.CMD_EXIT)
            finally:
                self._writer.close()
                await self._writer.wait_closed()
        self._reader = self._writer = None

    async def test_connection(self) -> bool:
        try:
            if not self._writer:
                await self.connect()
            await self.get_device_info()
            return True
        except (OSError, TimeoutError, RuntimeError, ValueError):
            return False

    async def get_users(self, since: datetime | None = None) -> list[dict[str, Any]]:
        data = await self._command(self.CMD_GET_USERS)
        users: list[dict[str, Any]] = []
        # Common ZK user records: uid(2), privilege(1), password(8), name(24),
        # card(4), group(1), timezone(2), user_id(9).
        record_size = 51
        for offset in range(0, len(data) - record_size + 1, record_size):
            record = data[offset : offset + record_size]
            employee_number = record[42:51].split(b"\0", 1)[0].decode("ascii", "ignore")
            if not employee_number:
                continue
            users.append({
                "employee_number": employee_number,
                "user_id": employee_number,
                "name": record[11:35].split(b"\0", 1)[0].decode("utf-8", "ignore"),
                "pin": record[3:11].split(b"\0", 1)[0].decode("ascii", "ignore"),
                "access_level": str(record[2]),
                "card_number": str(struct.unpack("<I", record[35:39])[0]),
            })
        return users

    @staticmethod
    def _user_payload(user: dict[str, Any]) -> bytes:
        uid = int(user.get("uid", 0))
        privilege = int(user.get("privilege", 0))
        pin = str(user.get("pin", "")).encode()[:8].ljust(8, b"\0")
        name = str(user.get("name", "")).encode()[:24].ljust(24, b"\0")
        card = int(user.get("card_number", 0))
        user_id = str(user.get("employee_number") or user.get("user_id", "")).encode()[:9].ljust(9, b"\0")
        return struct.pack("<HB", uid, privilege) + pin + name + struct.pack("<IBH", card, 0, 0) + user_id

    async def create_user(self, user: dict[str, Any]) -> dict[str, Any]:
        await self._command(self.CMD_SET_USER, self._user_payload(user))
        return user

    async def update_user(self, user_id: str, user: dict[str, Any]) -> dict[str, Any]:
        return await self.create_user({**user, "employee_number": user_id})

    async def delete_user(self, user_id: str) -> None:
        await self._command(self.CMD_DELETE_USER, user_id.encode("ascii")[:9].ljust(9, b"\0"))

    async def get_attendance_logs(self, since: datetime | None = None) -> list[dict[str, Any]]:
        data = await self._command(self.CMD_GET_ATTENDANCE)
        records: list[dict[str, Any]] = []
        for offset in range(0, len(data) - 13, 14):
            record = data[offset : offset + 14]
            user_id = record[:9].split(b"\0", 1)[0].decode("ascii", "ignore")
            unix_time = struct.unpack("<I", record[9:13])[0]
            timestamp = datetime.fromtimestamp(unix_time, timezone.utc)
            if since and timestamp <= since:
                continue
            records.append({
                "user_id": user_id,
                "timestamp": timestamp,
                "status": str(record[13]),
                "event_code": str(record[13]),
                "verify_mode": str(record[13]),
            })
        return records

    async def push_user(self, user: dict[str, Any]) -> dict[str, Any]:
        return await self.create_user(user)

    async def delete_template(self, user_id: str, template_id: str) -> None:
        await self._command(self.CMD_DELETE_TEMPLATE, f"{user_id}:{template_id}".encode())

    async def push_card(self, user_id: str, card_number: str) -> None:
        await self.update_user(user_id, {"card_number": card_number})

    async def push_pin(self, user_id: str, pin: str) -> None:
        await self.update_user(user_id, {"pin": pin})

    async def sync_time(self, value: datetime | None = None) -> None:
        value = (value or datetime.now(timezone.utc)).astimezone(timezone.utc)
        await self._command(self.CMD_SET_TIME, struct.pack("<I", int(value.timestamp())))

    async def restart_device(self) -> None:
        await self._command(self.CMD_RESTART)

    async def get_device_info(self) -> dict[str, Any]:
        data = await self._command(self.CMD_DEVICE_INFO)
        try:
            return json.loads(data.rstrip(b"\0"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"manufacturer": "ZKTeco", "raw": data.hex()}

    async def health_check(self) -> dict[str, Any]:
        online = await self.test_connection()
        return {"online": online, "host": self.host, "port": self.port}
