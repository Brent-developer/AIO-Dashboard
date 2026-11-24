from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NormalizedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    device_id: str
    employee_id: str
    timestamp: datetime
    event_type: str
    verification_method: str
    direction: str = Field(pattern="^(IN|OUT)$")
    site_id: str | None = None
    raw_vendor_data: dict[str, Any]

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class TranslationLayer:
    EVENT_CODES = {
        "zkteco": {"0": "CHECK_IN"},
        "suprema": {"0": "NORMAL"},
        "hikvision": {"1": "NORMAL_OPEN"},
        "osdp": {},
    }
    VERIFICATION_METHODS = {
        "zkteco": {"15": "FACE", "1": "FINGERPRINT", "2": "PIN", "3": "CARD"},
        "suprema": {"3": "FACE", "1": "FINGERPRINT", "2": "CARD"},
        "hikvision": {"face": "FACE", "fingerprint": "FINGERPRINT", "card": "CARD"},
        "osdp": {"card": "CARD", "pin": "PIN"},
    }

    @classmethod
    def normalize_event(cls, vendor: str, raw_event: dict[str, Any]) -> NormalizedEvent:
        vendor = vendor.lower()
        if vendor not in cls.EVENT_CODES:
            raise ValueError(f"Unsupported vendor: {vendor}")
        timestamp = cls._timestamp(raw_event.get("timestamp") or raw_event.get("time"))
        employee_id = str(raw_event.get("employee_id") or raw_event.get("user_id") or "")
        device_id = str(raw_event.get("device_id") or "")
        event_code = str(raw_event.get("event_code", raw_event.get("status", "0")))
        verify_code = str(raw_event.get("verification_method", raw_event.get("verify_mode", "UNKNOWN")))
        direction = str(raw_event.get("direction", "IN")).upper()
        if direction not in {"IN", "OUT"}:
            direction = "OUT" if direction in {"1", "EXIT", "OUTBOUND"} else "IN"
        event_id = raw_event.get("event_id")
        if not event_id:
            identity = f"{vendor}|{device_id}|{employee_id}|{timestamp.isoformat()}|{event_code}"
            event_id = hashlib.sha256(identity.encode()).hexdigest()
        return NormalizedEvent(
            event_id=str(event_id),
            device_id=device_id,
            employee_id=employee_id,
            timestamp=timestamp,
            event_type=cls.EVENT_CODES[vendor].get(event_code, f"UNKNOWN_{event_code}"),
            verification_method=cls.VERIFICATION_METHODS[vendor].get(verify_code.lower(), cls.VERIFICATION_METHODS[vendor].get(verify_code, "UNKNOWN")),
            direction=direction,
            site_id=raw_event.get("site_id"),
            raw_vendor_data=json.loads(json.dumps(raw_event, default=str)),
        )

    @staticmethod
    def _timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.now(timezone.utc)
