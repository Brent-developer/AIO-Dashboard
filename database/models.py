from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class SyncStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(100), default="")
    ip_address: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    protocol: Mapped[str] = mapped_column(String(30), default="tcp")
    polling_interval: Mapped[int] = mapped_column(Integer, default=60)
    online_status: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    site_id: Mapped[str | None] = mapped_column(String(100))
    username: Mapped[str | None] = mapped_column(String(255))
    encrypted_password: Mapped[bytes | None] = mapped_column(LargeBinary)
    driver_options: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    logs: Mapped[list[AttendanceLog]] = relationship(back_populates="device", cascade="all, delete-orphan")
    sync_jobs: Mapped[list[SyncJob]] = relationship(back_populates="device", cascade="all, delete-orphan")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    employee_number: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    surname: Mapped[str] = mapped_column(String(100))
    department: Mapped[str | None] = mapped_column(String(120), index=True)
    pin: Mapped[str | None] = mapped_column(String(255))
    access_level: Mapped[str] = mapped_column(String(80), default="standard")
    status: Mapped[EmployeeStatus] = mapped_column(
        Enum(EmployeeStatus, native_enum=False), default=EmployeeStatus.ACTIVE
    )
    remote_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    templates: Mapped[list[BiometricTemplate]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
    attendance_logs: Mapped[list[AttendanceLog]] = relationship(back_populates="employee")


class BiometricTemplate(Base):
    __tablename__ = "biometric_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    template_type: Mapped[str] = mapped_column(String(20))
    vendor_specific_id: Mapped[str | None] = mapped_column(String(255))
    encrypted_template_data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    employee: Mapped[Employee] = relationship(back_populates="templates")


class AttendanceLog(Base):
    __tablename__ = "attendance_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), index=True)
    employee_number: Mapped[str] = mapped_column(String(80), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    normalized_event_type: Mapped[str] = mapped_column(String(50))
    direction: Mapped[str] = mapped_column(String(10))
    verification_method: Mapped[str] = mapped_column(String(30))
    raw_vendor_data: Mapped[str | None] = mapped_column(Text)

    device: Mapped[Device] = relationship(back_populates="logs")
    employee: Mapped[Employee | None] = relationship(back_populates="attendance_logs")


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    job_type: Mapped[str] = mapped_column(String(20), default="incremental")
    status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, native_enum=False), default=SyncStatus.PENDING, index=True
    )
    last_sync_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    conflict_count: Mapped[int] = mapped_column(Integer, default=0)
    conflict_log: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    device: Mapped[Device] = relationship(back_populates="sync_jobs")
