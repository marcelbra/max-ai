"""Role tools for the agent."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import RunContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from max_ai.db import PMSCategoryModel, RoleModel


class AgentDeps(BaseModel):
    """Dependencies passed to agent tools."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    db: AsyncSession


async def list_roles(
    ctx: RunContext[AgentDeps], pms_category_id: str | None = None
) -> list[dict]:
    """
    List all roles, optionally filtered by PMS category.

    Args:
        pms_category_id: Optional UUID to filter roles by category

    Returns a list of roles with:
    - id: UUID of the role
    - name: Name of the role
    - pms_category_id: Parent category UUID
    - pms_anchor: Connection to personal mission statement
    - current_state: Current situation description
    - context: Additional context
    - target_budget: Weekly minutes target
    """
    db = ctx.deps.db
    query = select(RoleModel).options(
        selectinload(RoleModel.recurring_goals),
        selectinload(RoleModel.unique_goals),
    )
    if pms_category_id:
        query = query.where(RoleModel.pms_category_id == UUID(pms_category_id))

    result = await db.execute(query)
    roles = result.scalars().all()
    return [
        {
            "id": str(role.id),
            "name": role.name,
            "pms_category_id": str(role.pms_category_id),
            "pms_anchor": role.pms_anchor,
            "current_state": role.current_state,
            "context": role.context,
            "target_budget": role.target_budget,
            "recurring_goals_count": len(role.recurring_goals),
            "unique_goals_count": len(role.unique_goals),
        }
        for role in roles
    ]


class CreateRoleInput(BaseModel):
    pms_category_id: str = Field(..., description="UUID of the parent PMS category")
    name: str = Field(..., description="Name of the role")
    pms_anchor: str | None = Field(
        default=None, description="How this role connects to your mission"
    )
    current_state: str | None = Field(
        default=None, description="Current situation in this role"
    )
    context: str | None = Field(default=None, description="Additional context")
    target_budget: int | None = Field(
        default=None, description="Weekly minutes target for this role"
    )


async def create_role(ctx: RunContext[AgentDeps], input: CreateRoleInput) -> dict:
    """
    Create a new role under a PMS category.

    Args:
        input: Role details including name, category, and optional fields

    Returns the created role with its ID.
    """
    db = ctx.deps.db

    # Verify category exists
    result = await db.execute(
        select(PMSCategoryModel).where(
            PMSCategoryModel.id == UUID(input.pms_category_id)
        )
    )
    if not result.scalar_one_or_none():
        return {"error": "PMS Category not found"}

    role = RoleModel(
        pms_category_id=UUID(input.pms_category_id),
        name=input.name,
        pms_anchor=input.pms_anchor,
        current_state=input.current_state,
        context=input.context,
        target_budget=input.target_budget,
    )
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return {
        "id": str(role.id),
        "name": role.name,
        "pms_category_id": str(role.pms_category_id),
        "pms_anchor": role.pms_anchor,
        "current_state": role.current_state,
        "context": role.context,
        "target_budget": role.target_budget,
    }


class UpdateRoleInput(BaseModel):
    role_id: str = Field(..., description="UUID of the role to update")
    name: str | None = Field(default=None, description="New name")
    pms_category_id: str | None = Field(
        default=None, description="Move to different category"
    )
    pms_anchor: str | None = Field(default=None, description="New PMS anchor")
    current_state: str | None = Field(default=None, description="New current state")
    context: str | None = Field(default=None, description="New context")
    target_budget: int | None = Field(default=None, description="New weekly minutes target")


async def update_role(ctx: RunContext[AgentDeps], input: UpdateRoleInput) -> dict:
    """
    Update an existing role.

    Args:
        input: Role ID and fields to update

    Returns the updated role.
    """
    db = ctx.deps.db
    result = await db.execute(
        select(RoleModel).where(RoleModel.id == UUID(input.role_id))
    )
    role = result.scalar_one_or_none()
    if not role:
        return {"error": "Role not found"}

    if input.pms_category_id is not None:
        # Verify new category exists
        cat_result = await db.execute(
            select(PMSCategoryModel).where(
                PMSCategoryModel.id == UUID(input.pms_category_id)
            )
        )
        if not cat_result.scalar_one_or_none():
            return {"error": "Target category not found"}
        role.pms_category_id = UUID(input.pms_category_id)

    if input.name is not None:
        role.name = input.name
    if input.pms_anchor is not None:
        role.pms_anchor = input.pms_anchor
    if input.current_state is not None:
        role.current_state = input.current_state
    if input.context is not None:
        role.context = input.context
    if input.target_budget is not None:
        role.target_budget = input.target_budget

    await db.flush()
    await db.refresh(role)
    return {
        "id": str(role.id),
        "name": role.name,
        "pms_category_id": str(role.pms_category_id),
        "pms_anchor": role.pms_anchor,
        "current_state": role.current_state,
        "context": role.context,
        "target_budget": role.target_budget,
    }


class DeleteRoleInput(BaseModel):
    role_id: str = Field(..., description="UUID of the role to delete")
    confirmed: bool = Field(
        default=False,
        description="Must be True to actually delete. If False, returns what would be deleted.",
    )


async def delete_role(ctx: RunContext[AgentDeps], input: DeleteRoleInput) -> dict:
    """
    Delete a role and all its associated goals and tasks.

    IMPORTANT: This is a destructive operation. Set confirmed=True to actually delete.
    If confirmed=False, returns a preview of what would be deleted.

    Args:
        input: Role ID and confirmation flag

    Returns confirmation of deletion or preview.
    """
    db = ctx.deps.db
    result = await db.execute(
        select(RoleModel)
        .options(
            selectinload(RoleModel.recurring_goals),
            selectinload(RoleModel.unique_goals),
        )
        .where(RoleModel.id == UUID(input.role_id))
    )
    role = result.scalar_one_or_none()
    if not role:
        return {"error": "Role not found"}

    if not input.confirmed:
        return {
            "preview": True,
            "message": (
                f"Would delete role '{role.name}' with "
                f"{len(role.recurring_goals)} recurring goals and "
                f"{len(role.unique_goals)} unique goals. "
                "Set confirmed=True to proceed."
            ),
            "role": role.name,
            "recurring_goals_count": len(role.recurring_goals),
            "unique_goals_count": len(role.unique_goals),
        }

    await db.delete(role)
    return {
        "deleted": True,
        "message": f"Deleted role '{role.name}' and all associated goals",
    }
