from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from config import settings
from core.base_driver import BiometricDriver
from core.plugin_loader import load_driver
from core.security import BiometricTemplateSecurity
from database.models import Device


class DeviceSessionManager:
    """Keeps explicitly opened diagnostic driver sessions alive until disconnected."""

    def __init__(self) -> None:
        self._sessions: dict[uuid.UUID, BiometricDriver] = {}
        self._lock = asyncio.Lock()
        self._security = BiometricTemplateSecurity(settings.biometric_master_key)

    def _driver_options(self, device: Device) -> dict[str, Any]:
        options = json.loads(device.driver_options or "{}")
        if device.username:
            options["username"] = device.username
        if device.encrypted_password:
            options["password"] = self._security.decrypt_secret(str(device.id), device.encrypted_password)
        return options

    async def connect(self, device: Device) -> BiometricDriver:
        async with self._lock:
            existing = self._sessions.get(device.id)
            if existing:
                return existing
            driver = load_driver(device.manufacturer, device.ip_address, device.port, **self._driver_options(device))
            await driver.connect()
            self._sessions[device.id] = driver
            return driver

    async def disconnect(self, device_id: uuid.UUID) -> bool:
        async with self._lock:
            driver = self._sessions.pop(device_id, None)
            if not driver:
                return False
            await driver.disconnect()
            return True

    def get(self, device_id: uuid.UUID) -> BiometricDriver | None:
        return self._sessions.get(device_id)

    def is_connected(self, device_id: uuid.UUID) -> bool:
        return device_id in self._sessions


device_sessions = DeviceSessionManager()
