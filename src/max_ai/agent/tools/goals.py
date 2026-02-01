"""Goal tools for the agent (recurring and unique goals)."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import RunContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from max_ai.db import RecurringGoalModel, RoleModel, UniqueGoalModel
from max_ai.models import UniqueGoalStatus


class AgentDeps(BaseModel):
    """Dependencies passed to agent tools."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    db: AsyncSession


# ============ Recurring Goal Tools ============


async def list_recurring_goals(
    ctx: RunContext[AgentDeps],
    role_id: str | None = None,
    active: bool | None = None,
) -> list[dict]:
    """
    List recurring goals, optionally filtered by role or active status.

    Args:
        role_id: Optional UUID to filter by role
        active: Optional boolean to filter by active status

    Returns a list of recurring goals with:
    - id: UUID of the goal
    - role_id: Parent role UUID
    - activity: The recurring activity
    - target_amount: Frequency per week (e.g., 0.25 for monthly)
    - target_time: Duration per occurrence in minutes
    - context: Additional context
    - active: Whether the goal is active
    """
    db = ctx.deps.db
    query = select(RecurringGoalModel)
    if role_id:
        query = query.where(RecurringGoalModel.role_id == UUID(role_id))
    if active is not None:
        query = query.where(RecurringGoalModel.active == active)

    result = await db.execute(query)
    goals = result.scalars().all()
    return [
        {
            "id": str(goal.id),
            "role_id": str(goal.role_id),
            "activity": goal.activity,
            "target_amount": goal.target_amount,
            "target_time": goal.target_time,
            "context": goal.context,
            "active": goal.active,
        }
        for goal in goals
    ]


class CreateRecurringGoalInput(BaseModel):
    role_id: str = Field(..., description="UUID of the parent role")
    activity: str = Field(..., description="The recurring activity name")
    target_amount: float = Field(
        ..., description="Frequency per week (e.g., 3.0 for 3x/week, 0.25 for monthly)"
    )
    target_time: int = Field(..., description="Duration per occurrence in minutes")
    context: str | None = Field(default=None, description="Additional context")
    active: bool = Field(default=True, description="Whether the goal is active")


async def create_recurring_goal(
    ctx: RunContext[AgentDeps], input: CreateRecurringGoalInput
) -> dict:
    """
    Create a new recurring goal.

    Args:
        input: Goal details including role, activity, frequency, and duration

    Returns the created goal with its ID.
    """
    db = ctx.deps.db

    # Verify role exists
    result = await db.execute(
        select(RoleModel).where(RoleModel.id == UUID(input.role_id))
    )
    if not result.scalar_one_or_none():
        return {"error": "Role not found"}

    goal = RecurringGoalModel(
        role_id=UUID(input.role_id),
        activity=input.activity,
        target_amount=input.target_amount,
        target_time=input.target_time,
        context=input.context,
        active=input.active,
    )
    db.add(goal)
    await db.flush()
    await db.refresh(goal)
    return {
        "id": str(goal.id),
        "role_id": str(goal.role_id),
        "activity": goal.activity,
        "target_amount": goal.target_amount,
        "target_time": goal.target_time,
        "context": goal.context,
        "active": goal.active,
    }


class UpdateRecurringGoalInput(BaseModel):
    goal_id: str = Field(..., description="UUID of the goal to update")
    activity: str | None = Field(default=None, description="New activity name")
    target_amount: float | None = Field(default=None, description="New frequency")
    target_time: int | None = Field(default=None, description="New duration in minutes")
    context: str | None = Field(default=None, description="New context")
    active: bool | None = Field(default=None, description="New active status")
    role_id: str | None = Field(default=None, description="Move to different role")


async def update_recurring_goal(
    ctx: RunContext[AgentDeps], input: UpdateRecurringGoalInput
) -> dict:
    """
    Update an existing recurring goal.

    Args:
        input: Goal ID and fields to update

    Returns the updated goal.
    """
    db = ctx.deps.db
    result = await db.execute(
        select(RecurringGoalModel).where(
            RecurringGoalModel.id == UUID(input.goal_id)
        )
    )
    goal = result.scalar_one_or_none()
    if not goal:
        return {"error": "Recurring goal not found"}

    if input.role_id is not None:
        # Verify new role exists
        role_result = await db.execute(
            select(RoleModel).where(RoleModel.id == UUID(input.role_id))
        )
        if not role_result.scalar_one_or_none():
            return {"error": "Target role not found"}
        goal.role_id = UUID(input.role_id)

    if input.activity is not None:
        goal.activity = input.activity
    if input.target_amount is not None:
        goal.target_amount = input.target_amount
    if input.target_time is not None:
        goal.target_time = input.target_time
    if input.context is not None:
        goal.context = input.context
    if input.active is not None:
        goal.active = input.active

    await db.flush()
    await db.refresh(goal)
    return {
        "id": str(goal.id),
        "role_id": str(goal.role_id),
        "activity": goal.activity,
        "target_amount": goal.target_amount,
        "target_time": goal.target_time,
        "context": goal.context,
        "active": goal.active,
    }


class DeleteRecurringGoalInput(BaseModel):
    goal_id: str = Field(..., description="UUID of the goal to delete")
    confirmed: bool = Field(
        default=False,
        description="Must be True to actually delete. If False, returns what would be deleted.",
    )


async def delete_recurring_goal(
    ctx: RunContext[AgentDeps], input: DeleteRecurringGoalInput
) -> dict:
    """
    Delete a recurring goal.

    IMPORTANT: This is a destructive operation. Set confirmed=True to actually delete.
    If confirmed=False, returns a preview of what would be deleted.

    Args:
        input: Goal ID and confirmation flag

    Returns confirmation of deletion or preview.
    """
    db = ctx.deps.db
    result = await db.execute(
        select(RecurringGoalModel).where(
            RecurringGoalModel.id == UUID(input.goal_id)
        )
    )
    goal = result.scalar_one_or_none()
    if not goal:
        return {"error": "Recurring goal not found"}

    if not input.confirmed:
        return {
            "preview": True,
            "message": f"Would delete recurring goal: '{goal.activity}' ({goal.target_amount}x/week, {goal.target_time} min). Set confirmed=True to proceed.",
            "activity": goal.activity,
        }

    await db.delete(goal)
    return {"deleted": True, "message": f"Deleted recurring goal: '{goal.activity}'"}


# ============ Unique Goal Tools ============


async def list_unique_goals(
    ctx: RunContext[AgentDeps],
    role_id: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """
    List unique (one-time) goals, optionally filtered by role or status.

    Args:
        role_id: Optional UUID to filter by role
        status: Optional status filter (not_started, in_progress, completed, cancelled, at_risk)

    Returns a list of unique goals with:
    - id: UUID of the goal
    - role_id: Parent role UUID
    - title: Goal title
    - deadline: Optional deadline date
    - status: Current status
    - context: Additional context
    - depends_on: UUID of blocking goal (if any)
    """
    db = ctx.deps.db
    query = select(UniqueGoalModel)
    if role_id:
        query = query.where(UniqueGoalModel.role_id == UUID(role_id))
    if status:
        query = query.where(UniqueGoalModel.status == status)

    result = await db.execute(query)
    goals = result.scalars().all()
    return [
        {
            "id": str(goal.id),
            "role_id": str(goal.role_id),
            "title": goal.title,
            "deadline": goal.deadline.isoformat() if goal.deadline else None,
            "status": goal.status,
            "context": goal.context,
            "depends_on": str(goal.depends_on) if goal.depends_on else None,
        }
        for goal in goals
    ]


class CreateUniqueGoalInput(BaseModel):
    role_id: str = Field(..., description="UUID of the parent role")
    title: str = Field(..., description="Goal title")
    deadline: date | None = Field(default=None, description="Optional deadline date")
    status: str = Field(
        default="not_started",
        description="Status: not_started, in_progress, completed, cancelled, at_risk",
    )
    context: str | None = Field(default=None, description="Additional context")
    depends_on: str | None = Field(
        default=None, description="UUID of goal that must complete first"
    )


async def create_unique_goal(
    ctx: RunContext[AgentDeps], input: CreateUniqueGoalInput
) -> dict:
    """
    Create a new unique (one-time) goal.

    Args:
        input: Goal details including role, title, deadline, and status

    Returns the created goal with its ID.
    """
    db = ctx.deps.db

    # Verify role exists
    result = await db.execute(
        select(RoleModel).where(RoleModel.id == UUID(input.role_id))
    )
    if not result.scalar_one_or_none():
        return {"error": "Role not found"}

    # Verify dependency exists if specified
    if input.depends_on:
        dep_result = await db.execute(
            select(UniqueGoalModel).where(
                UniqueGoalModel.id == UUID(input.depends_on)
            )
        )
        if not dep_result.scalar_one_or_none():
            return {"error": "Dependency goal not found"}

    # Validate status
    try:
        status_enum = UniqueGoalStatus(input.status)
    except ValueError:
        return {"error": f"Invalid status: {input.status}"}

    goal = UniqueGoalModel(
        role_id=UUID(input.role_id),
        title=input.title,
        deadline=input.deadline,
        status=status_enum.value,
        context=input.context,
        depends_on=UUID(input.depends_on) if input.depends_on else None,
    )
    db.add(goal)
    await db.flush()
    await db.refresh(goal)
    return {
        "id": str(goal.id),
        "role_id": str(goal.role_id),
        "title": goal.title,
        "deadline": goal.deadline.isoformat() if goal.deadline else None,
        "status": goal.status,
        "context": goal.context,
        "depends_on": str(goal.depends_on) if goal.depends_on else None,
    }


class UpdateUniqueGoalInput(BaseModel):
    goal_id: str = Field(..., description="UUID of the goal to update")
    title: str | None = Field(default=None, description="New title")
    deadline: date | None = Field(default=None, description="New deadline")
    status: str | None = Field(default=None, description="New status")
    context: str | None = Field(default=None, description="New context")
    depends_on: str | None = Field(default=None, description="New dependency")
    role_id: str | None = Field(default=None, description="Move to different role")


async def update_unique_goal(
    ctx: RunContext[AgentDeps], input: UpdateUniqueGoalInput
) -> dict:
    """
    Update an existing unique goal.

    Args:
        input: Goal ID and fields to update

    Returns the updated goal.
    """
    db = ctx.deps.db
    result = await db.execute(
        select(UniqueGoalModel).where(UniqueGoalModel.id == UUID(input.goal_id))
    )
    goal = result.scalar_one_or_none()
    if not goal:
        return {"error": "Unique goal not found"}

    if input.role_id is not None:
        # Verify new role exists
        role_result = await db.execute(
            select(RoleModel).where(RoleModel.id == UUID(input.role_id))
        )
        if not role_result.scalar_one_or_none():
            return {"error": "Target role not found"}
        goal.role_id = UUID(input.role_id)

    if input.depends_on is not None:
        # Verify dependency exists
        dep_result = await db.execute(
            select(UniqueGoalModel).where(
                UniqueGoalModel.id == UUID(input.depends_on)
            )
        )
        if not dep_result.scalar_one_or_none():
            return {"error": "Dependency goal not found"}
        goal.depends_on = UUID(input.depends_on)

    if input.title is not None:
        goal.title = input.title
    if input.deadline is not None:
        goal.deadline = input.deadline
    if input.status is not None:
        try:
            status_enum = UniqueGoalStatus(input.status)
            goal.status = status_enum.value
        except ValueError:
            return {"error": f"Invalid status: {input.status}"}
    if input.context is not None:
        goal.context = input.context

    await db.flush()
    await db.refresh(goal)
    return {
        "id": str(goal.id),
        "role_id": str(goal.role_id),
        "title": goal.title,
        "deadline": goal.deadline.isoformat() if goal.deadline else None,
        "status": goal.status,
        "context": goal.context,
        "depends_on": str(goal.depends_on) if goal.depends_on else None,
    }


class DeleteUniqueGoalInput(BaseModel):
    goal_id: str = Field(..., description="UUID of the goal to delete")
    confirmed: bool = Field(
        default=False,
        description="Must be True to actually delete. If False, returns what would be deleted.",
    )


async def delete_unique_goal(
    ctx: RunContext[AgentDeps], input: DeleteUniqueGoalInput
) -> dict:
    """
    Delete a unique goal.

    IMPORTANT: This is a destructive operation. Set confirmed=True to actually delete.
    If confirmed=False, returns a preview of what would be deleted.

    Args:
        input: Goal ID and confirmation flag

    Returns confirmation of deletion or preview.
    """
    db = ctx.deps.db
    result = await db.execute(
        select(UniqueGoalModel).where(UniqueGoalModel.id == UUID(input.goal_id))
    )
    goal = result.scalar_one_or_none()
    if not goal:
        return {"error": "Unique goal not found"}

    if not input.confirmed:
        return {
            "preview": True,
            "message": f"Would delete unique goal: '{goal.title}' (status: {goal.status}). Set confirmed=True to proceed.",
            "title": goal.title,
            "status": goal.status,
        }

    await db.delete(goal)
    return {"deleted": True, "message": f"Deleted unique goal: '{goal.title}'"}
