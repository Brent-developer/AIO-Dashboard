from __future__ import annotations

import json
import uuid
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.auth import current_user
from core.plugin_loader import load_driver
from core.device_sessions import device_sessions
from core.security import BiometricTemplateSecurity
from database.models import Device, SyncJob
from database.session import get_db
from schemas import DeviceCreate, DeviceRead, DeviceUpdate, Page, SyncJobRead, SyncRequest
from tasks.sync_tasks import sync_device


router = APIRouter(prefix="/api/v1/devices", tags=["devices"], dependencies=[Depends(current_user)])
security = BiometricTemplateSecurity(settings.biometric_master_key)


def serialize_device(device: Device) -> dict:
    return {
        key: getattr(device, key)
        for key in ("id", "name", "manufacturer", "model", "ip_address", "port", "protocol", "polling_interval", "online_status", "last_heartbeat", "site_id", "username", "created_at", "updated_at")
    } | {"driver_options": json.loads(device.driver_options or "{}")}


@router.get("/", response_model=Page)
async def list_devices(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500), db: AsyncSession = Depends(get_db)) -> Page:
    total = await db.scalar(select(func.count()).select_from(Device)) or 0
    devices = (await db.scalars(select(Device).order_by(Device.name).offset((page - 1) * page_size).limit(page_size))).all()
    return Page(items=[DeviceRead.model_validate(serialize_device(item)) for item in devices], total=total, page=page, page_size=page_size)


@router.post("/", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
async def create_device(payload: DeviceCreate, db: AsyncSession = Depends(get_db)) -> dict:
    values = payload.model_dump(exclude={"password", "driver_options"})
    device = Device(**values, driver_options=json.dumps(payload.driver_options))
    db.add(device)
    await db.flush()
    if payload.password:
        device.encrypted_password = security.encrypt_secret(str(device.id), payload.password)
    await db.commit()
    await db.refresh(device)
    return serialize_device(device)


@router.get("/{device_id}", response_model=DeviceRead)
async def get_device(device_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return serialize_device(device)


@router.post("/{device_id}/connection-test")
async def test_device_connection(device_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    """Open a short-lived driver session to verify remote TCP/device access."""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    options = json.loads(device.driver_options or "{}")
    if device.username:
        options["username"] = device.username
    if device.encrypted_password:
        options["password"] = security.decrypt_secret(str(device.id), device.encrypted_password)

    driver = None
    connected = False
    error_message: str | None = None
    try:
        driver = load_driver(device.manufacturer, device.ip_address, device.port, **options)
        connected = await driver.test_connection()
    except Exception as exc:
        error_message = str(exc)[:500]
    finally:
        if driver is not None:
            try:
                await driver.disconnect()
            except Exception:
                pass

    now = datetime.now(timezone.utc)
    device.online_status = connected
    if connected:
        device.last_heartbeat = now
    await db.commit()
    return {
        "device_id": str(device.id),
        "host": device.ip_address,
        "port": device.port,
        "protocol": device.protocol,
        "connected": connected,
        "checked_at": now,
        "error": error_message,
    }


@router.post("/{device_id}/connect")
async def connect_device(device_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    try:
        await device_sessions.connect(device)
    except Exception as exc:
        device.online_status = False
        await db.commit()
        raise HTTPException(status_code=502, detail=str(exc)[:500]) from exc
    now = datetime.now(timezone.utc)
    device.online_status = True
    device.last_heartbeat = now
    await db.commit()
    return {"device_id": str(device.id), "connected": True, "host": device.ip_address, "port": device.port, "connected_at": now}


@router.post("/{device_id}/clone")
async def clone_device_to_sandbox(device_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    """Read the connected device identity and return a sandbox-safe clone profile."""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    driver = device_sessions.get(device.id)
    if not driver:
        raise HTTPException(status_code=409, detail="Connect to the device before cloning it")
    try:
        device_info = await driver.get_device_info()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not read device info: {str(exc)[:400]}") from exc
    return {
        "device_id": str(device.id),
        "clone_source": {"name": device.name, "manufacturer": device.manufacturer, "model": device.model, "host": device.ip_address, "port": device.port, "protocol": device.protocol},
        "device_info": device_info,
        "sandbox": {"scenario": "healthy", "offline": False, "source": "live-device"},
    }


@router.post("/{device_id}/disconnect")
async def disconnect_device(device_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    await device_sessions.disconnect(device.id)
    device.online_status = False
    await db.commit()
    return {"device_id": str(device.id), "connected": False}


@router.post("/{device_id}/emulate")
async def emulate_device_issue(device_id: uuid.UUID, issue: str = "healthy", db: AsyncSession = Depends(get_db)) -> dict:
    """Run a controlled diagnostic scenario against an already-open device session."""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    driver = device_sessions.get(device.id)
    if not driver:
        raise HTTPException(status_code=409, detail="Connect to the device before starting emulation")
    if issue == "latency":
        await asyncio.sleep(2)
        result = {"simulated": True, "latency_ms": 2000, "message": "Artificial network latency injected"}
    elif issue == "offline":
        await device_sessions.disconnect(device.id)
        device.online_status = False
        result = {"simulated": True, "connected": False, "message": "Device disconnected for offline simulation"}
    elif issue == "malformed":
        result = {"simulated": True, "raw_response": "<malformed-device-payload>", "message": "Malformed response fixture returned"}
    else:
        health = await driver.health_check()
        result = {"simulated": False, "health": health, "message": "Live session is healthy"}
    await db.commit()
    return {"device_id": str(device.id), "issue": issue, **result}


@router.patch("/{device_id}", response_model=DeviceRead)
async def update_device(device_id: uuid.UUID, payload: DeviceUpdate, db: AsyncSession = Depends(get_db)) -> dict:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    values = payload.model_dump(exclude_unset=True, exclude={"password", "driver_options"})
    for key, value in values.items():
        setattr(device, key, value)
    if payload.driver_options is not None:
        device.driver_options = json.dumps(payload.driver_options)
    if payload.password is not None:
        device.encrypted_password = security.encrypt_secret(str(device.id), payload.password)
    await db.commit()
    await db.refresh(device)
    return serialize_device(device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(device_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Response:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    await db.delete(device)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{device_id}/sync", response_model=SyncJobRead, status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(device_id: uuid.UUID, request: SyncRequest, db: AsyncSession = Depends(get_db)) -> SyncJob:
    if not await db.get(Device, device_id):
        raise HTTPException(status_code=404, detail="Device not found")
    job = SyncJob(device_id=device_id, job_type=request.job_type)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    sync_device.delay(str(job.id))
    return job
