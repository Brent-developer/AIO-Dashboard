from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import httpx

from core.base_driver import BiometricDriver


class HikvisionDriver(BiometricDriver):
    NS = {"isapi": "http://www.isapi.org/ver20/XMLSchema"}

    def __init__(self, host: str, port: int = 80, **options: Any) -> None:
        super().__init__(host, port, **options)
        scheme = options.get("scheme", "https" if port == 443 else "http")
        self.client = httpx.AsyncClient(
            base_url=f"{scheme}://{host}:{port}",
            auth=httpx.DigestAuth(options.get("username", "admin"), options.get("password", "")),
            verify=options.get("verify_ssl", True),
            timeout=20,
        )

    async def connect(self) -> None:
        response = await self.client.get("/ISAPI/System/deviceInfo")
        response.raise_for_status()

    async def disconnect(self) -> None:
        await self.client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = await self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response

    @staticmethod
    def _text(element: ET.Element, name: str, default: str = "") -> str:
        node = element.find(f".//{{*}}{name}")
        return node.text.strip() if node is not None and node.text else default

    async def test_connection(self) -> bool:
        try:
            await self.connect()
            return True
        except httpx.HTTPError:
            return False

    async def get_users(self, since: datetime | None = None) -> list[dict[str, Any]]:
        body = """<UserInfoSearchCond version=\"2.0\" xmlns=\"http://www.isapi.org/ver20/XMLSchema\"><searchID>1</searchID><searchResultPosition>0</searchResultPosition><maxResults>1000</maxResults></UserInfoSearchCond>"""
        response = await self._request("POST", "/ISAPI/AccessControl/UserInfo/Search", content=body, headers={"Content-Type": "application/xml"})
        root = ET.fromstring(response.content)
        users = []
        for node in root.findall(".//{*}UserInfo"):
            users.append({
                "employee_number": self._text(node, "employeeNo"),
                "user_id": self._text(node, "employeeNo"),
                "name": self._text(node, "name"),
                "access_level": self._text(node, "userType", "normal"),
            })
        return users

    @staticmethod
    def _user_xml(user: dict[str, Any]) -> str:
        root = ET.Element("UserInfo", xmlns="http://www.isapi.org/ver20/XMLSchema", version="2.0")
        ET.SubElement(root, "employeeNo").text = str(user.get("employee_number") or user.get("user_id"))
        ET.SubElement(root, "name").text = str(user.get("name", ""))
        ET.SubElement(root, "userType").text = str(user.get("access_level", "normal"))
        return ET.tostring(root, encoding="unicode")

    async def create_user(self, user: dict[str, Any]) -> dict[str, Any]:
        await self._request("POST", "/ISAPI/AccessControl/UserInfo/Record", content=self._user_xml(user), headers={"Content-Type": "application/xml"})
        return user

    async def update_user(self, user_id: str, user: dict[str, Any]) -> dict[str, Any]:
        value = {**user, "employee_number": user_id}
        await self._request("PUT", "/ISAPI/AccessControl/UserInfo/Modify", content=self._user_xml(value), headers={"Content-Type": "application/xml"})
        return value

    async def delete_user(self, user_id: str) -> None:
        body = f"<UserInfoDelCond xmlns=\"http://www.isapi.org/ver20/XMLSchema\"><EmployeeNoList><employeeNo>{user_id}</employeeNo></EmployeeNoList></UserInfoDelCond>"
        await self._request("PUT", "/ISAPI/AccessControl/UserInfo/Delete", content=body, headers={"Content-Type": "application/xml"})

    async def get_attendance_logs(self, since: datetime | None = None) -> list[dict[str, Any]]:
        start = (since or datetime(1970, 1, 1, tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
        end = datetime.now(timezone.utc).isoformat()
        body = f"""<AcsEventCond version=\"2.0\" xmlns=\"http://www.isapi.org/ver20/XMLSchema\"><searchID>1</searchID><searchResultPosition>0</searchResultPosition><maxResults>1000</maxResults><major>0</major><minor>0</minor><startTime>{start}</startTime><endTime>{end}</endTime></AcsEventCond>"""
        response = await self._request("POST", "/ISAPI/AccessControl/AcsEvent", content=body, headers={"Content-Type": "application/xml"})
        root = ET.fromstring(response.content)
        events = []
        nodes = root.findall(".//{*}AcsEventInfo")
        if not nodes:
            nodes = root.findall(".//{*}InfoList")
        for node in nodes:
            events.append({
                "event_id": self._text(node, "serialNo"),
                "user_id": self._text(node, "employeeNoString"),
                "timestamp": self._text(node, "time"),
                "event_code": self._text(node, "minor", "1"),
                "verification_method": self._text(node, "currentVerifyMode", "unknown").lower(),
                "direction": "OUT" if self._text(node, "attendanceStatus").lower() in {"check_out", "break_out"} else "IN",
            })
        return events

    async def push_user(self, user: dict[str, Any]) -> dict[str, Any]:
        return await self.create_user(user)

    async def delete_template(self, user_id: str, template_id: str) -> None:
        body = f"<FDSearchDescription xmlns=\"http://www.isapi.org/ver20/XMLSchema\"><FPID>{user_id}</FPID><faceLibType>blackFD</faceLibType><FDID>{template_id}</FDID></FDSearchDescription>"
        await self._request("DELETE", "/ISAPI/Intelligent/FDLib/FDSearch", content=body, headers={"Content-Type": "application/xml"})

    async def push_card(self, user_id: str, card_number: str) -> None:
        body = f"<CardInfo xmlns=\"http://www.isapi.org/ver20/XMLSchema\"><employeeNo>{user_id}</employeeNo><cardNo>{card_number}</cardNo></CardInfo>"
        await self._request("POST", "/ISAPI/AccessControl/CardInfo/Record", content=body, headers={"Content-Type": "application/xml"})

    async def push_pin(self, user_id: str, pin: str) -> None:
        await self.update_user(user_id, {"pin": pin})

    async def sync_time(self, value: datetime | None = None) -> None:
        value = value or datetime.now(timezone.utc)
        body = f"<Time xmlns=\"http://www.isapi.org/ver20/XMLSchema\"><timeMode>manual</timeMode><localTime>{value.isoformat()}</localTime></Time>"
        await self._request("PUT", "/ISAPI/System/time", content=body, headers={"Content-Type": "application/xml"})

    async def restart_device(self) -> None:
        await self._request("PUT", "/ISAPI/System/reboot")

    async def get_device_info(self) -> dict[str, Any]:
        root = ET.fromstring((await self._request("GET", "/ISAPI/System/deviceInfo")).content)
        return {key: self._text(root, key) for key in ("deviceName", "deviceID", "model", "serialNumber", "firmwareVersion")}

    async def health_check(self) -> dict[str, Any]:
        return {"online": await self.test_connection(), "host": self.host, "port": self.port}
