from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from max_ai.db import RecurringGoalModel, RoleModel, UniqueGoalModel, get_db
from max_ai.models import (
    RecurringGoal,
    RecurringGoalCreate,
    RecurringGoalUpdate,
    UniqueGoal,
    UniqueGoalCreate,
    UniqueGoalStatus,
    UniqueGoalUpdate,
)

router = APIRouter()


# ============ Recurring Goals ============


@router.get("/recurring", response_model=list[RecurringGoal])
async def list_recurring_goals(
    role_id: UUID | None = None,
    active: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[RecurringGoalModel]:
    query = select(RecurringGoalModel)
    if role_id:
        query = query.where(RecurringGoalModel.role_id == role_id)
    if active is not None:
        query = query.where(RecurringGoalModel.active == active)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/recurring/{goal_id}", response_model=RecurringGoal)
async def get_recurring_goal(
    goal_id: UUID, db: AsyncSession = Depends(get_db)
) -> RecurringGoalModel:
    result = await db.execute(
        select(RecurringGoalModel).where(RecurringGoalModel.id == goal_id)
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring goal not found")
    return goal


@router.post("/recurring", response_model=RecurringGoal, status_code=status.HTTP_201_CREATED)
async def create_recurring_goal(
    data: RecurringGoalCreate, db: AsyncSession = Depends(get_db)
) -> RecurringGoalModel:
    # Verify role exists
    result = await db.execute(select(RoleModel).where(RoleModel.id == data.role_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    goal = RecurringGoalModel(**data.model_dump())
    db.add(goal)
    await db.flush()
    await db.refresh(goal)
    return goal


@router.patch("/recurring/{goal_id}", response_model=RecurringGoal)
async def update_recurring_goal(
    goal_id: UUID, data: RecurringGoalUpdate, db: AsyncSession = Depends(get_db)
) -> RecurringGoalModel:
    result = await db.execute(
        select(RecurringGoalModel).where(RecurringGoalModel.id == goal_id)
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring goal not found")

    update_data = data.model_dump(exclude_unset=True)

    # Verify new role exists if changing
    if "role_id" in update_data:
        result = await db.execute(
            select(RoleModel).where(RoleModel.id == update_data["role_id"])
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    for field, value in update_data.items():
        setattr(goal, field, value)

    await db.flush()
    await db.refresh(goal)
    return goal


@router.delete("/recurring/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recurring_goal(goal_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(
        select(RecurringGoalModel).where(RecurringGoalModel.id == goal_id)
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring goal not found")

    await db.delete(goal)


# ============ Unique Goals ============


@router.get("/unique", response_model=list[UniqueGoal])
async def list_unique_goals(
    role_id: UUID | None = None,
    status: UniqueGoalStatus | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[UniqueGoalModel]:
    query = select(UniqueGoalModel)
    if role_id:
        query = query.where(UniqueGoalModel.role_id == role_id)
    if status:
        query = query.where(UniqueGoalModel.status == status.value)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/unique/{goal_id}", response_model=UniqueGoal)
async def get_unique_goal(
    goal_id: UUID, db: AsyncSession = Depends(get_db)
) -> UniqueGoalModel:
    result = await db.execute(
        select(UniqueGoalModel).where(UniqueGoalModel.id == goal_id)
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unique goal not found")
    return goal


@router.post("/unique", response_model=UniqueGoal, status_code=status.HTTP_201_CREATED)
async def create_unique_goal(
    data: UniqueGoalCreate, db: AsyncSession = Depends(get_db)
) -> UniqueGoalModel:
    # Verify role exists
    result = await db.execute(select(RoleModel).where(RoleModel.id == data.role_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    # Verify dependency exists if specified
    if data.depends_on:
        result = await db.execute(
            select(UniqueGoalModel).where(UniqueGoalModel.id == data.depends_on)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency goal not found")

    goal_data = data.model_dump()
    goal_data["status"] = goal_data["status"].value
    goal = UniqueGoalModel(**goal_data)
    db.add(goal)
    await db.flush()
    await db.refresh(goal)
    return goal


@router.patch("/unique/{goal_id}", response_model=UniqueGoal)
async def update_unique_goal(
    goal_id: UUID, data: UniqueGoalUpdate, db: AsyncSession = Depends(get_db)
) -> UniqueGoalModel:
    result = await db.execute(
        select(UniqueGoalModel).where(UniqueGoalModel.id == goal_id)
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unique goal not found")

    update_data = data.model_dump(exclude_unset=True)

    # Verify new role exists if changing
    if "role_id" in update_data:
        result = await db.execute(
            select(RoleModel).where(RoleModel.id == update_data["role_id"])
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    # Verify dependency exists if changing
    if "depends_on" in update_data and update_data["depends_on"]:
        result = await db.execute(
            select(UniqueGoalModel).where(UniqueGoalModel.id == update_data["depends_on"])
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency goal not found")

    for field, value in update_data.items():
        if field == "status" and value is not None:
            value = value.value
        setattr(goal, field, value)

    await db.flush()
    await db.refresh(goal)
    return goal


@router.delete("/unique/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unique_goal(goal_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(
        select(UniqueGoalModel).where(UniqueGoalModel.id == goal_id)
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unique goal not found")

    await db.delete(goal)
