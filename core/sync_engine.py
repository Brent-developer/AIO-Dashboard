from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.plugin_loader import load_driver
from core.security import BiometricTemplateSecurity
from core.translation_layer import TranslationLayer
from database.models import AttendanceLog, BiometricTemplate, Device, Employee, SyncJob, SyncStatus


class SynchronizationEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.template_security = BiometricTemplateSecurity(settings.biometric_master_key)

    async def run(self, job_id: uuid.UUID) -> SyncJob:
        job = await self.session.get(SyncJob, job_id)
        if not job:
            raise LookupError(f"Sync job {job_id} does not exist")
        device = await self.session.get(Device, job.device_id)
        if not device:
            raise LookupError(f"Device {job.device_id} does not exist")

        started = datetime.now(timezone.utc)
        job.status = SyncStatus.RUNNING
        job.started_at = started
        await self.session.commit()

        since = None if job.job_type == "full" else await self._last_success(device.id, job.id)
        options = json.loads(device.driver_options or "{}")
        if device.username:
            options["username"] = device.username
        if device.encrypted_password:
            options["password"] = self.template_security.decrypt_secret(str(device.id), device.encrypted_password)
        driver = load_driver(device.manufacturer, device.ip_address, device.port, **options)
        conflicts: list[dict[str, Any]] = []
        try:
            await driver.connect()
            remote_users = await driver.get_users(since=since)
            for remote in remote_users:
                conflict = await self._upsert_remote_user(remote)
                if conflict:
                    conflicts.append(conflict)
            raw_events = await driver.get_attendance_logs(since=since)
            for raw in raw_events:
                raw.setdefault("device_id", str(device.id))
                raw.setdefault("site_id", device.site_id)
                await self._store_event(device, raw)

            completed = datetime.now(timezone.utc)
            job.conflict_count = len(conflicts)
            job.conflict_log = json.dumps(conflicts, default=str) if conflicts else None
            job.last_sync_timestamp = completed
            job.completed_at = completed
            job.status = SyncStatus.SUCCESS
            device.online_status = True
            device.last_heartbeat = completed
            await self.session.commit()
            return job
        except Exception as exc:
            await self.session.rollback()
            job = await self.session.get(SyncJob, job_id)
            device = await self.session.get(Device, device.id)
            assert job is not None and device is not None
            job.status = SyncStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = str(exc)[:4000]
            device.online_status = False
            await self.session.commit()
            raise
        finally:
            try:
                await driver.disconnect()
            except Exception:
                # Preserve the original synchronization result/error. Disconnect
                # failures are reflected by the next health check.
                pass

    async def _last_success(self, device_id: uuid.UUID, current_job: uuid.UUID) -> datetime | None:
        statement = (
            select(SyncJob.last_sync_timestamp)
            .where(
                SyncJob.device_id == device_id,
                SyncJob.id != current_job,
                SyncJob.status == SyncStatus.SUCCESS,
                SyncJob.last_sync_timestamp.is_not(None),
            )
            .order_by(SyncJob.last_sync_timestamp.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)

    async def _upsert_remote_user(self, remote: dict[str, Any]) -> dict[str, Any] | None:
        number = str(remote.get("employee_number") or remote.get("user_id") or "").strip()
        if not number:
            return None
        employee = await self.session.scalar(select(Employee).where(Employee.employee_number == number))
        name = str(remote.get("name", "")).strip()
        first_name, _, surname = name.partition(" ")
        values = {
            "first_name": remote.get("first_name") or first_name or number,
            "surname": remote.get("surname") or surname or "",
            "department": remote.get("department"),
            "access_level": str(remote.get("access_level", "standard")),
            "pin": remote.get("pin"),
        }
        conflict = None
        if employee:
            changed = {key: {"local": getattr(employee, key), "remote": value} for key, value in values.items() if value is not None and getattr(employee, key) != value}
            if changed:
                conflict = {"employee_number": number, "resolution": "remote_wins", "fields": changed}
                for key, value in values.items():
                    if value is not None:
                        setattr(employee, key, value)
        else:
            employee = Employee(employee_number=number, **values)
            self.session.add(employee)
            await self.session.flush()

        template_groups = {
            "finger": remote.get("fingerprint_templates", []),
            "face": remote.get("face_templates", []),
            "palm": remote.get("palm_templates", []),
        }
        for template_type, templates in template_groups.items():
            for index, template in enumerate(templates or []):
                raw = template.encode() if isinstance(template, str) else bytes(template)
                vendor_id = f"{number}:{template_type}:{index}"
                existing = await self.session.scalar(select(BiometricTemplate).where(BiometricTemplate.vendor_specific_id == vendor_id))
                encrypted = self.template_security.encrypt(str(employee.id), raw)
                if existing:
                    existing.encrypted_template_data = encrypted
                else:
                    self.session.add(BiometricTemplate(employee_id=employee.id, template_type=template_type, vendor_specific_id=vendor_id, encrypted_template_data=encrypted))
        return conflict

    async def _store_event(self, device: Device, raw: dict[str, Any]) -> None:
        event = TranslationLayer.normalize_event(device.manufacturer, raw)
        if await self.session.scalar(select(AttendanceLog.id).where(AttendanceLog.event_id == event.event_id)):
            return
        employee = await self.session.scalar(select(Employee).where(Employee.employee_number == event.employee_id))
        self.session.add(AttendanceLog(
            event_id=event.event_id,
            device_id=device.id,
            employee_id=employee.id if employee else None,
            employee_number=event.employee_id,
            timestamp=event.timestamp,
            normalized_event_type=event.event_type,
            direction=event.direction,
            verification_method=event.verification_method,
            raw_vendor_data=json.dumps(event.raw_vendor_data, default=str),
        ))
