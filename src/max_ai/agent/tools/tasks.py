"""Task tools for the agent."""

from datetime import date, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import RunContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from max_ai.db import RoleModel, TaskInstanceModel
from max_ai.models import TaskStatus


class AgentDeps(BaseModel):
    """Dependencies passed to agent tools."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    db: AsyncSession


def _task_to_dict(task: TaskInstanceModel) -> dict:
    """Convert a task model to a dictionary."""
    return {
        "id": str(task.id),
        "role_id": str(task.role_id) if task.role_id else None,
        "source_id": str(task.source_id) if task.source_id else None,
        "title": task.title,
        "scheduled_date": task.scheduled_date.isoformat(),
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "target_time": task.target_time,
        "status": task.status,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "context": task.context,
        "calendar_event_id": task.calendar_event_id,
    }


async def get_today_tasks(ctx: RunContext[AgentDeps]) -> list[dict]:
    """
    Get all tasks scheduled for today.

    Returns a list of tasks sorted by target time (descending).
    Each task includes:
    - id: UUID of the task
    - title: Task title
    - scheduled_date: Date the task is scheduled
    - status: pending, done, or skipped
    - target_time: Expected duration in minutes
    - role_id: Associated role (if any)
    """
    db = ctx.deps.db
    today = date.today()
    result = await db.execute(
        select(TaskInstanceModel)
        .where(TaskInstanceModel.scheduled_date == today)
        .order_by(TaskInstanceModel.target_time.desc().nulls_last())
    )
    tasks = result.scalars().all()
    return [_task_to_dict(task) for task in tasks]


async def get_week_tasks(
    ctx: RunContext[AgentDeps], week_start: date | None = None
) -> list[dict]:
    """
    Get all tasks for a week, starting from the given Monday.

    Args:
        week_start: Optional start date (Monday). Defaults to current week's Monday.

    Returns a list of tasks sorted by date and time.
    """
    db = ctx.deps.db
    if not week_start:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

    week_end = week_start + timedelta(days=6)

    result = await db.execute(
        select(TaskInstanceModel)
        .where(TaskInstanceModel.scheduled_date >= week_start)
        .where(TaskInstanceModel.scheduled_date <= week_end)
        .order_by(
            TaskInstanceModel.scheduled_date,
            TaskInstanceModel.target_time.desc().nulls_last(),
        )
    )
    tasks = result.scalars().all()
    return [_task_to_dict(task) for task in tasks]


class CreateTaskInput(BaseModel):
    title: str = Field(..., description="Task title")
    scheduled_date: date = Field(..., description="Date to schedule the task")
    role_id: str | None = Field(default=None, description="UUID of associated role")
    source_id: str | None = Field(
        default=None, description="UUID of source goal (recurring or unique)"
    )
    due_date: date | None = Field(default=None, description="Hard deadline date")
    target_time: int | None = Field(
        default=None, description="Expected duration in minutes"
    )
    context: str | None = Field(default=None, description="Additional context")
    calendar_event_id: str | None = Field(
        default=None, description="External calendar event ID"
    )


async def create_task(ctx: RunContext[AgentDeps], input: CreateTaskInput) -> dict:
    """
    Create a new task.

    Args:
        input: Task details including title, date, and optional fields

    Returns the created task with its ID.
    """
    db = ctx.deps.db

    # Verify role exists if specified
    if input.role_id:
        result = await db.execute(
            select(RoleModel).where(RoleModel.id == UUID(input.role_id))
        )
        if not result.scalar_one_or_none():
            return {"error": "Role not found"}

    task = TaskInstanceModel(
        title=input.title,
        scheduled_date=input.scheduled_date,
        role_id=UUID(input.role_id) if input.role_id else None,
        source_id=UUID(input.source_id) if input.source_id else None,
        due_date=input.due_date,
        target_time=input.target_time,
        status=TaskStatus.PENDING.value,
        context=input.context,
        calendar_event_id=input.calendar_event_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return _task_to_dict(task)


class UpdateTaskInput(BaseModel):
    task_id: str = Field(..., description="UUID of the task to update")
    title: str | None = Field(default=None, description="New title")
    scheduled_date: date | None = Field(default=None, description="New scheduled date")
    due_date: date | None = Field(default=None, description="New due date")
    target_time: int | None = Field(default=None, description="New duration in minutes")
    status: str | None = Field(
        default=None, description="New status: pending, done, skipped"
    )
    context: str | None = Field(default=None, description="New context")
    role_id: str | None = Field(default=None, description="New role")


async def update_task(ctx: RunContext[AgentDeps], input: UpdateTaskInput) -> dict:
    """
    Update an existing task.

    Args:
        input: Task ID and fields to update

    Returns the updated task.
    """
    db = ctx.deps.db
    result = await db.execute(
        select(TaskInstanceModel).where(TaskInstanceModel.id == UUID(input.task_id))
    )
    task = result.scalar_one_or_none()
    if not task:
        return {"error": "Task not found"}

    if input.role_id is not None:
        # Verify new role exists
        role_result = await db.execute(
            select(RoleModel).where(RoleModel.id == UUID(input.role_id))
        )
        if not role_result.scalar_one_or_none():
            return {"error": "Role not found"}
        task.role_id = UUID(input.role_id)

    if input.title is not None:
        task.title = input.title
    if input.scheduled_date is not None:
        task.scheduled_date = input.scheduled_date
    if input.due_date is not None:
        task.due_date = input.due_date
    if input.target_time is not None:
        task.target_time = input.target_time
    if input.status is not None:
        try:
            status_enum = TaskStatus(input.status)
            task.status = status_enum.value
            if status_enum == TaskStatus.DONE:
                task.completed_at = datetime.now()
        except ValueError:
            return {"error": f"Invalid status: {input.status}"}
    if input.context is not None:
        task.context = input.context

    await db.flush()
    await db.refresh(task)
    return _task_to_dict(task)


class DeleteTaskInput(BaseModel):
    task_id: str = Field(..., description="UUID of the task to delete")
    confirmed: bool = Field(
        default=False,
        description="Must be True to actually delete. If False, returns what would be deleted.",
    )


async def delete_task(ctx: RunContext[AgentDeps], input: DeleteTaskInput) -> dict:
    """
    Delete a task.

    IMPORTANT: This is a destructive operation. Set confirmed=True to actually delete.
    If confirmed=False, returns a preview of what would be deleted.

    Args:
        input: Task ID and confirmation flag

    Returns confirmation of deletion or preview.
    """
    db = ctx.deps.db
    result = await db.execute(
        select(TaskInstanceModel).where(TaskInstanceModel.id == UUID(input.task_id))
    )
    task = result.scalar_one_or_none()
    if not task:
        return {"error": "Task not found"}

    if not input.confirmed:
        return {
            "preview": True,
            "message": f"Would delete task: '{task.title}' (scheduled: {task.scheduled_date}, status: {task.status}). Set confirmed=True to proceed.",
            "title": task.title,
            "scheduled_date": task.scheduled_date.isoformat(),
            "status": task.status,
        }

    await db.delete(task)
    return {"deleted": True, "message": f"Deleted task: '{task.title}'"}


class CompleteTaskInput(BaseModel):
    task_id: str = Field(..., description="UUID of the task to complete")


async def complete_task(ctx: RunContext[AgentDeps], input: CompleteTaskInput) -> dict:
    """
    Mark a task as completed.

    Args:
        input: Task ID to complete

    Returns the updated task with completed status and timestamp.
    """
    db = ctx.deps.db
    result = await db.execute(
        select(TaskInstanceModel).where(TaskInstanceModel.id == UUID(input.task_id))
    )
    task = result.scalar_one_or_none()
    if not task:
        return {"error": "Task not found"}

    task.status = TaskStatus.DONE.value
    task.completed_at = datetime.now()

    await db.flush()
    await db.refresh(task)
    return _task_to_dict(task)


class SkipTaskInput(BaseModel):
    task_id: str = Field(..., description="UUID of the task to skip")


async def skip_task(ctx: RunContext[AgentDeps], input: SkipTaskInput) -> dict:
    """
    Mark a task as skipped.

    Args:
        input: Task ID to skip

    Returns the updated task with skipped status.
    """
    db = ctx.deps.db
    result = await db.execute(
        select(TaskInstanceModel).where(TaskInstanceModel.id == UUID(input.task_id))
    )
    task = result.scalar_one_or_none()
    if not task:
        return {"error": "Task not found"}

    task.status = TaskStatus.SKIPPED.value

    await db.flush()
    await db.refresh(task)
    return _task_to_dict(task)
