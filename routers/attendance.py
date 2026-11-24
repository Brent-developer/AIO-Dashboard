from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, Query, Response
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import current_user
from database.models import AttendanceLog, Employee
from database.session import get_db
from schemas import AttendanceRead, Page


router = APIRouter(prefix="/api/v1/attendance", tags=["attendance"], dependencies=[Depends(current_user)])


def attendance_query(start_date: datetime | None, end_date: datetime | None, department: str | None):
    statement = select(AttendanceLog)
    if department:
        statement = statement.join(Employee, AttendanceLog.employee_id == Employee.id).where(Employee.department == department)
    if start_date:
        statement = statement.where(AttendanceLog.timestamp >= start_date)
    if end_date:
        statement = statement.where(AttendanceLog.timestamp <= end_date)
    return statement


@router.get("/", response_model=Page)
async def list_attendance(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    department: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> Page:
    statement = attendance_query(start_date, end_date, department)
    total = await db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = (await db.scalars(statement.order_by(AttendanceLog.timestamp.desc()).offset((page - 1) * page_size).limit(page_size))).all()
    return Page(items=[AttendanceRead.model_validate(row) for row in rows], total=total, page=page, page_size=page_size)


@router.get("/export")
async def export_attendance(
    format: str = Query("csv", pattern="^(csv|xlsx|pdf)$"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    department: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> Response:
    rows = (await db.scalars(attendance_query(start_date, end_date, department).order_by(AttendanceLog.timestamp))).all()
    data = [{"event_id": row.event_id, "employee_number": row.employee_number, "timestamp": row.timestamp.isoformat(), "event_type": row.normalized_event_type, "direction": row.direction, "verification_method": row.verification_method} for row in rows]
    frame = pd.DataFrame(data)
    if format == "csv":
        return Response(frame.to_csv(index=False), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=attendance.csv"})
    if format == "xlsx":
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False, sheet_name="Attendance")
        return Response(buffer.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=attendance.xlsx"})
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(30, height - 30, "Attendance Report")
    y = height - 55
    pdf.setFont("Helvetica", 8)
    for row in data:
        line = f"{row['timestamp'][:19]:19}  {row['employee_number'][:18]:18}  {row['event_type'][:18]:18}  {row['direction']:3}  {row['verification_method']}"
        pdf.drawString(30, y, line)
        y -= 12
        if y < 25:
            pdf.showPage(); pdf.setFont("Helvetica", 8); y = height - 30
    pdf.save()
    return Response(buffer.getvalue(), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=attendance.pdf"})
