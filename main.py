from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text

from config import settings
from core.auth import decode_token
from database.models import AttendanceLog, Device, SyncJob, SyncStatus
from database.session import Base, async_session_factory, engine
from routers import attendance, auth, devices, employees


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="Universal Biometric Integration Platform", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(devices.router)
app.include_router(attendance.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}


@app.websocket("/ws/dashboard")
async def dashboard_socket(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing access token")
        return
    try:
        decode_token(token, "access")
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid access token")
        return
    await websocket.accept()
    try:
        while True:
            one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
            async with async_session_factory() as session:
                total_devices = await session.scalar(select(func.count()).select_from(Device)) or 0
                online_devices = await session.scalar(select(func.count()).select_from(Device).where(Device.online_status.is_(True))) or 0
                events_per_minute = await session.scalar(select(func.count()).select_from(AttendanceLog).where(AttendanceLog.timestamp >= one_minute_ago)) or 0
                active_sync_jobs = await session.scalar(select(func.count()).select_from(SyncJob).where(SyncJob.status.in_([SyncStatus.PENDING, SyncStatus.RUNNING]))) or 0
            await websocket.send_json({
                "total_devices": total_devices,
                "online_devices": online_devices,
                "events_per_minute": events_per_minute,
                "active_sync_jobs": active_sync_jobs,
            })
            await asyncio.sleep(1)
    except (WebSocketDisconnect, RuntimeError):
        return
