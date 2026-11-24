from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import current_user
from database.models import Employee
from database.session import get_db
from schemas import EmployeeCreate, EmployeeRead, EmployeeUpdate, Page


router = APIRouter(prefix="/api/v1/employees", tags=["employees"], dependencies=[Depends(current_user)])


@router.get("/", response_model=Page)
async def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    department: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> Page:
    filters = [Employee.department == department] if department else []
    total = await db.scalar(select(func.count()).select_from(Employee).where(*filters)) or 0
    rows = (await db.scalars(select(Employee).where(*filters).order_by(Employee.employee_number).offset((page - 1) * page_size).limit(page_size))).all()
    return Page(items=[EmployeeRead.model_validate(row) for row in rows], total=total, page=page, page_size=page_size)


@router.post("/", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
async def create_employee(payload: EmployeeCreate, db: AsyncSession = Depends(get_db)) -> Employee:
    if await db.scalar(select(Employee.id).where(Employee.employee_number == payload.employee_number)):
        raise HTTPException(status_code=409, detail="Employee number already exists")
    employee = Employee(**payload.model_dump())
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return employee


@router.get("/{employee_id}", response_model=EmployeeRead)
async def get_employee(employee_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Employee:
    employee = await db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.patch("/{employee_id}", response_model=EmployeeRead)
async def update_employee(employee_id: uuid.UUID, payload: EmployeeUpdate, db: AsyncSession = Depends(get_db)) -> Employee:
    employee = await get_employee(employee_id, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(employee, key, value)
    await db.commit()
    await db.refresh(employee)
    return employee


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(employee_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Response:
    employee = await get_employee(employee_id, db)
    await db.delete(employee)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
