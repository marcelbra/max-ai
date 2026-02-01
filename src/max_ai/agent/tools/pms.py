"""PMS (Personal Mission Statement) tools for the agent."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import RunContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from max_ai.db import PMSCategoryModel, PMSStatementModel


class AgentDeps(BaseModel):
    """Dependencies passed to agent tools."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    db: AsyncSession


# ============ Category Tools ============


async def list_pms_categories(ctx: RunContext[AgentDeps]) -> list[dict]:
    """
    List all PMS categories with their statements.

    Returns a list of categories, each containing:
    - id: UUID of the category
    - emoji: Emoji representing the category
    - name: Name of the category
    - sort_order: Display order
    - statements: List of mission statements in this category
    """
    db = ctx.deps.db
    result = await db.execute(
        select(PMSCategoryModel)
        .options(selectinload(PMSCategoryModel.statements))
        .order_by(PMSCategoryModel.sort_order)
    )
    categories = result.scalars().all()
    return [
        {
            "id": str(cat.id),
            "emoji": cat.emoji,
            "name": cat.name,
            "sort_order": cat.sort_order,
            "statements": [
                {
                    "id": str(stmt.id),
                    "statement": stmt.statement,
                    "sort_order": stmt.sort_order,
                }
                for stmt in cat.statements
            ],
        }
        for cat in categories
    ]


class CreatePMSCategoryInput(BaseModel):
    emoji: str = Field(..., description="Emoji representing the category")
    name: str = Field(..., description="Name of the category")
    sort_order: int = Field(default=0, description="Display order (lower = first)")


async def create_pms_category(
    ctx: RunContext[AgentDeps], input: CreatePMSCategoryInput
) -> dict:
    """
    Create a new PMS category.

    Args:
        input: Category details including emoji, name, and optional sort_order

    Returns the created category with its ID.
    """
    db = ctx.deps.db
    category = PMSCategoryModel(
        emoji=input.emoji,
        name=input.name,
        sort_order=input.sort_order,
    )
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return {
        "id": str(category.id),
        "emoji": category.emoji,
        "name": category.name,
        "sort_order": category.sort_order,
    }


class UpdatePMSCategoryInput(BaseModel):
    category_id: str = Field(..., description="UUID of the category to update")
    emoji: str | None = Field(default=None, description="New emoji")
    name: str | None = Field(default=None, description="New name")
    sort_order: int | None = Field(default=None, description="New sort order")


async def update_pms_category(
    ctx: RunContext[AgentDeps], input: UpdatePMSCategoryInput
) -> dict:
    """
    Update an existing PMS category.

    Args:
        input: Category ID and fields to update

    Returns the updated category.
    """
    db = ctx.deps.db
    result = await db.execute(
        select(PMSCategoryModel).where(PMSCategoryModel.id == UUID(input.category_id))
    )
    category = result.scalar_one_or_none()
    if not category:
        return {"error": "Category not found"}

    if input.emoji is not None:
        category.emoji = input.emoji
    if input.name is not None:
        category.name = input.name
    if input.sort_order is not None:
        category.sort_order = input.sort_order

    await db.flush()
    await db.refresh(category)
    return {
        "id": str(category.id),
        "emoji": category.emoji,
        "name": category.name,
        "sort_order": category.sort_order,
    }


class DeletePMSCategoryInput(BaseModel):
    category_id: str = Field(..., description="UUID of the category to delete")
    confirmed: bool = Field(
        default=False,
        description="Must be True to actually delete. If False, returns what would be deleted.",
    )


async def delete_pms_category(
    ctx: RunContext[AgentDeps], input: DeletePMSCategoryInput
) -> dict:
    """
    Delete a PMS category and all its statements.

    IMPORTANT: This is a destructive operation. Set confirmed=True to actually delete.
    If confirmed=False, returns a preview of what would be deleted.

    Args:
        input: Category ID and confirmation flag

    Returns confirmation of deletion or preview.
    """
    db = ctx.deps.db
    result = await db.execute(
        select(PMSCategoryModel)
        .options(selectinload(PMSCategoryModel.statements))
        .where(PMSCategoryModel.id == UUID(input.category_id))
    )
    category = result.scalar_one_or_none()
    if not category:
        return {"error": "Category not found"}

    if not input.confirmed:
        return {
            "preview": True,
            "message": f"Would delete category '{category.name}' ({category.emoji}) and {len(category.statements)} statements. Set confirmed=True to proceed.",
            "category": category.name,
            "statements_count": len(category.statements),
        }

    await db.delete(category)
    return {
        "deleted": True,
        "message": f"Deleted category '{category.name}' and {len(category.statements)} statements",
    }


# ============ Statement Tools ============


class CreatePMSStatementInput(BaseModel):
    category_id: str = Field(..., description="UUID of the parent category")
    statement: str = Field(..., description="The mission statement text")
    sort_order: int = Field(default=0, description="Display order within category")


async def create_pms_statement(
    ctx: RunContext[AgentDeps], input: CreatePMSStatementInput
) -> dict:
    """
    Create a new PMS statement within a category.

    Args:
        input: Statement details including parent category_id, text, and sort_order

    Returns the created statement with its ID.
    """
    db = ctx.deps.db

    # Verify category exists
    result = await db.execute(
        select(PMSCategoryModel).where(PMSCategoryModel.id == UUID(input.category_id))
    )
    if not result.scalar_one_or_none():
        return {"error": "Category not found"}

    statement = PMSStatementModel(
        category_id=UUID(input.category_id),
        statement=input.statement,
        sort_order=input.sort_order,
    )
    db.add(statement)
    await db.flush()
    await db.refresh(statement)
    return {
        "id": str(statement.id),
        "category_id": str(statement.category_id),
        "statement": statement.statement,
        "sort_order": statement.sort_order,
    }


class UpdatePMSStatementInput(BaseModel):
    statement_id: str = Field(..., description="UUID of the statement to update")
    statement: str | None = Field(default=None, description="New statement text")
    category_id: str | None = Field(default=None, description="Move to different category")
    sort_order: int | None = Field(default=None, description="New sort order")


async def update_pms_statement(
    ctx: RunContext[AgentDeps], input: UpdatePMSStatementInput
) -> dict:
    """
    Update an existing PMS statement.

    Args:
        input: Statement ID and fields to update

    Returns the updated statement.
    """
    db = ctx.deps.db
    result = await db.execute(
        select(PMSStatementModel).where(
            PMSStatementModel.id == UUID(input.statement_id)
        )
    )
    stmt = result.scalar_one_or_none()
    if not stmt:
        return {"error": "Statement not found"}

    if input.category_id is not None:
        # Verify new category exists
        cat_result = await db.execute(
            select(PMSCategoryModel).where(
                PMSCategoryModel.id == UUID(input.category_id)
            )
        )
        if not cat_result.scalar_one_or_none():
            return {"error": "Target category not found"}
        stmt.category_id = UUID(input.category_id)

    if input.statement is not None:
        stmt.statement = input.statement
    if input.sort_order is not None:
        stmt.sort_order = input.sort_order

    await db.flush()
    await db.refresh(stmt)
    return {
        "id": str(stmt.id),
        "category_id": str(stmt.category_id),
        "statement": stmt.statement,
        "sort_order": stmt.sort_order,
    }


class DeletePMSStatementInput(BaseModel):
    statement_id: str = Field(..., description="UUID of the statement to delete")
    confirmed: bool = Field(
        default=False,
        description="Must be True to actually delete. If False, returns what would be deleted.",
    )


async def delete_pms_statement(
    ctx: RunContext[AgentDeps], input: DeletePMSStatementInput
) -> dict:
    """
    Delete a PMS statement.

    IMPORTANT: This is a destructive operation. Set confirmed=True to actually delete.
    If confirmed=False, returns a preview of what would be deleted.

    Args:
        input: Statement ID and confirmation flag

    Returns confirmation of deletion or preview.
    """
    db = ctx.deps.db
    result = await db.execute(
        select(PMSStatementModel).where(
            PMSStatementModel.id == UUID(input.statement_id)
        )
    )
    stmt = result.scalar_one_or_none()
    if not stmt:
        return {"error": "Statement not found"}

    if not input.confirmed:
        preview_text = (
            stmt.statement[:50] + "..."
            if len(stmt.statement) > 50
            else stmt.statement
        )
        return {
            "preview": True,
            "message": f"Would delete statement: '{preview_text}'. Set confirmed=True to proceed.",
            "statement": stmt.statement,
        }

    await db.delete(stmt)
    return {"deleted": True, "message": "Statement deleted successfully"}
