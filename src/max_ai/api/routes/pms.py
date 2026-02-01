from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from max_ai.db import PMSCategoryModel, PMSStatementModel, get_db
from max_ai.models import (
    PMSCategory,
    PMSCategoryCreate,
    PMSCategoryUpdate,
    PMSCategoryWithStatements,
    PMSStatement,
    PMSStatementCreate,
    PMSStatementUpdate,
)

router = APIRouter()


# ============ Categories ============


@router.get("/categories", response_model=list[PMSCategoryWithStatements])
async def list_categories(db: AsyncSession = Depends(get_db)) -> list[PMSCategoryModel]:
    result = await db.execute(
        select(PMSCategoryModel)
        .options(selectinload(PMSCategoryModel.statements))
        .order_by(PMSCategoryModel.sort_order)
    )
    return list(result.scalars().all())


@router.get("/categories/{category_id}", response_model=PMSCategoryWithStatements)
async def get_category(
    category_id: UUID, db: AsyncSession = Depends(get_db)
) -> PMSCategoryModel:
    result = await db.execute(
        select(PMSCategoryModel)
        .options(selectinload(PMSCategoryModel.statements))
        .where(PMSCategoryModel.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


@router.post("/categories", response_model=PMSCategory, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: PMSCategoryCreate, db: AsyncSession = Depends(get_db)
) -> PMSCategoryModel:
    category = PMSCategoryModel(**data.model_dump())
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=PMSCategory)
async def update_category(
    category_id: UUID, data: PMSCategoryUpdate, db: AsyncSession = Depends(get_db)
) -> PMSCategoryModel:
    result = await db.execute(
        select(PMSCategoryModel).where(PMSCategoryModel.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)

    await db.flush()
    await db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(
        select(PMSCategoryModel).where(PMSCategoryModel.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    await db.delete(category)


# ============ Statements ============


@router.get("/statements", response_model=list[PMSStatement])
async def list_statements(
    category_id: UUID | None = None, db: AsyncSession = Depends(get_db)
) -> list[PMSStatementModel]:
    query = select(PMSStatementModel).order_by(PMSStatementModel.sort_order)
    if category_id:
        query = query.where(PMSStatementModel.category_id == category_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/statements/{statement_id}", response_model=PMSStatement)
async def get_statement(
    statement_id: UUID, db: AsyncSession = Depends(get_db)
) -> PMSStatementModel:
    result = await db.execute(
        select(PMSStatementModel).where(PMSStatementModel.id == statement_id)
    )
    statement = result.scalar_one_or_none()
    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found")
    return statement


@router.post("/statements", response_model=PMSStatement, status_code=status.HTTP_201_CREATED)
async def create_statement(
    data: PMSStatementCreate, db: AsyncSession = Depends(get_db)
) -> PMSStatementModel:
    # Verify category exists
    result = await db.execute(
        select(PMSCategoryModel).where(PMSCategoryModel.id == data.category_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    statement = PMSStatementModel(**data.model_dump())
    db.add(statement)
    await db.flush()
    await db.refresh(statement)
    return statement


@router.patch("/statements/{statement_id}", response_model=PMSStatement)
async def update_statement(
    statement_id: UUID, data: PMSStatementUpdate, db: AsyncSession = Depends(get_db)
) -> PMSStatementModel:
    result = await db.execute(
        select(PMSStatementModel).where(PMSStatementModel.id == statement_id)
    )
    statement = result.scalar_one_or_none()
    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found")

    update_data = data.model_dump(exclude_unset=True)

    # Verify new category exists if changing
    if "category_id" in update_data:
        result = await db.execute(
            select(PMSCategoryModel).where(PMSCategoryModel.id == update_data["category_id"])
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    for field, value in update_data.items():
        setattr(statement, field, value)

    await db.flush()
    await db.refresh(statement)
    return statement


@router.delete("/statements/{statement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_statement(statement_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(
        select(PMSStatementModel).where(PMSStatementModel.id == statement_id)
    )
    statement = result.scalar_one_or_none()
    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found")

    await db.delete(statement)
