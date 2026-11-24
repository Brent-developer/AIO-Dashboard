from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from core.base_driver import BiometricDriver


class SupremaDriver(BiometricDriver):
    def __init__(self, host: str, port: int = 443, **options: Any) -> None:
        super().__init__(host, port, **options)
        scheme = options.get("scheme", "https" if port == 443 else "http")
        self.base_url = f"{scheme}://{host}:{port}"
        self.username = options.get("username", "admin")
        self.password = options.get("password", "")
        self.client = httpx.AsyncClient(base_url=self.base_url, verify=options.get("verify_ssl", True), timeout=20)
        self.session_id: str | None = None

    async def connect(self) -> None:
        response = await self.client.post(
            "/api/login", data={"username": self.username, "password": self.password}
        )
        response.raise_for_status()
        payload = response.json()
        self.session_id = str(payload.get("session_id") or payload.get("Response", {}).get("session_id") or "")
        if not self.session_id:
            raise ConnectionError("Suprema login response did not contain session_id")
        self.client.headers["BS-Session-ID"] = self.session_id

    async def disconnect(self) -> None:
        if self.session_id:
            try:
                await self.client.post("/api/logout")
            finally:
                self.session_id = None
        await self.client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if not self.session_id:
            await self.connect()
        response = await self.client.request(method, path, **kwargs)
        if response.status_code == 401:
            await self.connect()
            response = await self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response

    async def test_connection(self) -> bool:
        try:
            await self._request("GET", "/api/device")
            return True
        except (httpx.HTTPError, ConnectionError):
            return False

    @staticmethod
    def _parse_user(value: dict[str, Any]) -> dict[str, Any]:
        credentials = value.get("credentials") or {}
        return {
            "user_id": str(value.get("user_id", "")),
            "employee_number": str(value.get("user_id", "")),
            "name": value.get("name", ""),
            "fingerprint_templates": value.get("fingerprint_templates", []),
            "face_templates": credentials.get("face", []),
            "card_number": credentials.get("card"),
            "updated_at": value.get("updated_at"),
        }

    async def get_users(self, since: datetime | None = None) -> list[dict[str, Any]]:
        params = {"modified_since": since.astimezone(timezone.utc).isoformat()} if since else None
        payload = (await self._request("GET", "/api/users", params=params)).json()
        values = payload.get("users") or payload.get("UserCollection", {}).get("rows") or []
        return [self._parse_user(value) for value in values]

    async def create_user(self, user: dict[str, Any]) -> dict[str, Any]:
        return (await self._request("POST", "/api/users", json=user)).json()

    async def update_user(self, user_id: str, user: dict[str, Any]) -> dict[str, Any]:
        return (await self._request("PUT", f"/api/users/{user_id}", json=user)).json()

    async def delete_user(self, user_id: str) -> None:
        await self._request("DELETE", f"/api/users/{user_id}")

    async def get_attendance_logs(self, since: datetime | None = None) -> list[dict[str, Any]]:
        params = {"from": since.astimezone(timezone.utc).isoformat()} if since else None
        payload = (await self._request("GET", "/api/events", params=params)).json()
        return payload.get("events") or payload.get("EventCollection", {}).get("rows") or []

    async def push_user(self, user: dict[str, Any]) -> dict[str, Any]:
        return await self.create_user(user)

    async def delete_template(self, user_id: str, template_id: str) -> None:
        await self._request("DELETE", f"/api/users/{user_id}/templates/{template_id}")

    async def push_card(self, user_id: str, card_number: str) -> None:
        await self.update_user(user_id, {"credentials": {"card": card_number}})

    async def push_pin(self, user_id: str, pin: str) -> None:
        await self.update_user(user_id, {"credentials": {"pin": pin}})

    async def sync_time(self, value: datetime | None = None) -> None:
        value = value or datetime.now(timezone.utc)
        await self._request("PUT", "/api/device/time", json={"datetime": value.isoformat()})

    async def restart_device(self) -> None:
        await self._request("POST", "/api/device/reboot")

    async def get_device_info(self) -> dict[str, Any]:
        return (await self._request("GET", "/api/device")).json()

    async def health_check(self) -> dict[str, Any]:
        return {"online": await self.test_connection(), "host": self.host, "session": bool(self.session_id)}
