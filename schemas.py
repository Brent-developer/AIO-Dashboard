from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from database.models import EmployeeStatus, SyncStatus


class EmployeeBase(BaseModel):
    employee_number: str = Field(min_length=1, max_length=80)
    first_name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)
    department: str | None = None
    pin: str | None = None
    access_level: str = "standard"
    status: EmployeeStatus = EmployeeStatus.ACTIVE


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    employee_number: str | None = None
    first_name: str | None = None
    surname: str | None = None
    department: str | None = None
    pin: str | None = None
    access_level: str | None = None
    status: EmployeeStatus | None = None


class EmployeeRead(EmployeeBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DeviceBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    manufacturer: str = Field(min_length=1, max_length=50)
    model: str = ""
    ip_address: str
    port: int = Field(ge=1, le=65535)
    protocol: str = "tcp"
    polling_interval: int = Field(default=60, ge=1)
    site_id: str | None = None
    username: str | None = None
    driver_options: dict = Field(default_factory=dict)


class DeviceCreate(DeviceBase):
    password: str | None = None


class DeviceUpdate(BaseModel):
    name: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    ip_address: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    protocol: str | None = None
    polling_interval: int | None = Field(default=None, ge=1)
    site_id: str | None = None
    username: str | None = None
    password: str | None = None
    driver_options: dict | None = None


class DeviceRead(DeviceBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    online_status: bool
    last_heartbeat: datetime | None
    created_at: datetime
    updated_at: datetime


class AttendanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: str
    device_id: uuid.UUID
    employee_id: uuid.UUID | None
    employee_number: str
    timestamp: datetime
    normalized_event_type: str
    direction: str
    verification_method: str


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class SyncRequest(BaseModel):
    job_type: str = Field(default="incremental", pattern="^(incremental|full)$")


class SyncJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    device_id: uuid.UUID
    job_type: str
    status: SyncStatus
    last_sync_timestamp: datetime | None
    conflict_count: int
    error_message: str | None


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
