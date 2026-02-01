from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from max_ai.db import PMSCategoryModel, RoleModel, get_db
from max_ai.models import (
    Role,
    RoleCreate,
    RoleUpdate,
    RoleWithGoals,
)

router = APIRouter()


@router.get("", response_model=list[Role])
async def list_roles(
    pms_category_id: UUID | None = None, db: AsyncSession = Depends(get_db)
) -> list[RoleModel]:
    query = select(RoleModel)
    if pms_category_id:
        query = query.where(RoleModel.pms_category_id == pms_category_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{role_id}", response_model=RoleWithGoals)
async def get_role(role_id: UUID, db: AsyncSession = Depends(get_db)) -> RoleModel:
    result = await db.execute(
        select(RoleModel)
        .options(
            selectinload(RoleModel.recurring_goals),
            selectinload(RoleModel.unique_goals),
        )
        .where(RoleModel.id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


@router.post("", response_model=Role, status_code=status.HTTP_201_CREATED)
async def create_role(data: RoleCreate, db: AsyncSession = Depends(get_db)) -> RoleModel:
    # Verify category exists
    result = await db.execute(
        select(PMSCategoryModel).where(PMSCategoryModel.id == data.pms_category_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    role = RoleModel(**data.model_dump())
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return role


@router.patch("/{role_id}", response_model=Role)
async def update_role(
    role_id: UUID, data: RoleUpdate, db: AsyncSession = Depends(get_db)
) -> RoleModel:
    result = await db.execute(select(RoleModel).where(RoleModel.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    update_data = data.model_dump(exclude_unset=True)

    # Verify new category exists if changing
    if "pms_category_id" in update_data:
        result = await db.execute(
            select(PMSCategoryModel).where(PMSCategoryModel.id == update_data["pms_category_id"])
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    for field, value in update_data.items():
        setattr(role, field, value)

    await db.flush()
    await db.refresh(role)
    return role


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(select(RoleModel).where(RoleModel.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    await db.delete(role)
