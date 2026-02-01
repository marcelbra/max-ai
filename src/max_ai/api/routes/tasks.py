from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from max_ai.db import RoleModel, TaskInstanceModel, get_db
from max_ai.models import (
    TaskInstance,
    TaskInstanceCreate,
    TaskInstanceUpdate,
    TaskStatus,
)

router = APIRouter()


@router.get("/today", response_model=list[TaskInstance])
async def get_today_tasks(db: AsyncSession = Depends(get_db)) -> list[TaskInstanceModel]:
    today = date.today()
    result = await db.execute(
        select(TaskInstanceModel)
        .where(TaskInstanceModel.scheduled_date == today)
        .order_by(TaskInstanceModel.target_time.desc().nulls_last())
    )
    return list(result.scalars().all())


@router.get("/week", response_model=list[TaskInstance])
async def get_week_tasks(
    week_start: date | None = None, db: AsyncSession = Depends(get_db)
) -> list[TaskInstanceModel]:
    if not week_start:
        # Default to current week's Monday
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

    week_end = week_start + timedelta(days=6)

    result = await db.execute(
        select(TaskInstanceModel)
        .where(TaskInstanceModel.scheduled_date >= week_start)
        .where(TaskInstanceModel.scheduled_date <= week_end)
        .order_by(TaskInstanceModel.scheduled_date, TaskInstanceModel.target_time.desc().nulls_last())
    )
    return list(result.scalars().all())


@router.get("", response_model=list[TaskInstance])
async def list_tasks(
    role_id: UUID | None = None,
    status: TaskStatus | None = None,
    scheduled_date: date | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[TaskInstanceModel]:
    query = select(TaskInstanceModel)
    if role_id:
        query = query.where(TaskInstanceModel.role_id == role_id)
    if status:
        query = query.where(TaskInstanceModel.status == status.value)
    if scheduled_date:
        query = query.where(TaskInstanceModel.scheduled_date == scheduled_date)
    query = query.order_by(TaskInstanceModel.scheduled_date.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{task_id}", response_model=TaskInstance)
async def get_task(task_id: UUID, db: AsyncSession = Depends(get_db)) -> TaskInstanceModel:
    result = await db.execute(
        select(TaskInstanceModel).where(TaskInstanceModel.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.post("", response_model=TaskInstance, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskInstanceCreate, db: AsyncSession = Depends(get_db)
) -> TaskInstanceModel:
    # Verify role exists if specified
    if data.role_id:
        result = await db.execute(select(RoleModel).where(RoleModel.id == data.role_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    task_data = data.model_dump()
    task_data["status"] = task_data["status"].value
    task = TaskInstanceModel(**task_data)
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskInstance)
async def update_task(
    task_id: UUID, data: TaskInstanceUpdate, db: AsyncSession = Depends(get_db)
) -> TaskInstanceModel:
    result = await db.execute(
        select(TaskInstanceModel).where(TaskInstanceModel.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    update_data = data.model_dump(exclude_unset=True)

    # Verify new role exists if changing
    if "role_id" in update_data and update_data["role_id"]:
        result = await db.execute(
            select(RoleModel).where(RoleModel.id == update_data["role_id"])
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    for field, value in update_data.items():
        if field == "status" and value is not None:
            value = value.value
        setattr(task, field, value)

    await db.flush()
    await db.refresh(task)
    return task


@router.post("/{task_id}/complete", response_model=TaskInstance)
async def complete_task(task_id: UUID, db: AsyncSession = Depends(get_db)) -> TaskInstanceModel:
    result = await db.execute(
        select(TaskInstanceModel).where(TaskInstanceModel.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task.status = TaskStatus.DONE.value
    task.completed_at = datetime.now()

    await db.flush()
    await db.refresh(task)
    return task


@router.post("/{task_id}/skip", response_model=TaskInstance)
async def skip_task(task_id: UUID, db: AsyncSession = Depends(get_db)) -> TaskInstanceModel:
    result = await db.execute(
        select(TaskInstanceModel).where(TaskInstanceModel.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task.status = TaskStatus.SKIPPED.value

    await db.flush()
    await db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(
        select(TaskInstanceModel).where(TaskInstanceModel.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    await db.delete(task)
