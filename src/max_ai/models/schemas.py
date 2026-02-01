from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Enums
class UniqueGoalStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    AT_RISK = "at_risk"


class TaskStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    SKIPPED = "skipped"


# Base config for all models
class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ============ PMS Category ============
class PMSCategoryBase(BaseSchema):
    emoji: str = Field(..., max_length=10)
    name: str = Field(..., max_length=100)
    sort_order: int = Field(default=0)


class PMSCategoryCreate(PMSCategoryBase):
    pass


class PMSCategoryUpdate(BaseSchema):
    emoji: str | None = Field(default=None, max_length=10)
    name: str | None = Field(default=None, max_length=100)
    sort_order: int | None = None


class PMSCategory(PMSCategoryBase):
    id: UUID


class PMSCategoryWithStatements(PMSCategory):
    statements: list["PMSStatement"] = []


# ============ PMS Statement ============
class PMSStatementBase(BaseSchema):
    category_id: UUID
    statement: str
    sort_order: int = Field(default=0)


class PMSStatementCreate(PMSStatementBase):
    pass


class PMSStatementUpdate(BaseSchema):
    category_id: UUID | None = None
    statement: str | None = None
    sort_order: int | None = None


class PMSStatement(PMSStatementBase):
    id: UUID


# ============ Role ============
class RoleBase(BaseSchema):
    pms_category_id: UUID
    name: str = Field(..., max_length=100)
    pms_anchor: str | None = None
    current_state: str | None = None
    context: str | None = None
    target_budget: int | None = Field(default=None, description="Weekly minutes target")


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseSchema):
    pms_category_id: UUID | None = None
    name: str | None = Field(default=None, max_length=100)
    pms_anchor: str | None = None
    current_state: str | None = None
    context: str | None = None
    target_budget: int | None = None


class Role(RoleBase):
    id: UUID


class RoleWithGoals(Role):
    recurring_goals: list["RecurringGoal"] = []
    unique_goals: list["UniqueGoal"] = []


# ============ Recurring Goal ============
class RecurringGoalBase(BaseSchema):
    role_id: UUID
    activity: str = Field(..., max_length=200)
    target_amount: float = Field(..., description="Frequency per week (e.g., 0.25 for monthly)")
    target_time: int = Field(..., description="Duration per occurrence in minutes")
    context: str | None = None
    active: bool = True


class RecurringGoalCreate(RecurringGoalBase):
    pass


class RecurringGoalUpdate(BaseSchema):
    role_id: UUID | None = None
    activity: str | None = Field(default=None, max_length=200)
    target_amount: float | None = None
    target_time: int | None = None
    context: str | None = None
    active: bool | None = None


class RecurringGoal(RecurringGoalBase):
    id: UUID


# ============ Unique Goal ============
class UniqueGoalBase(BaseSchema):
    role_id: UUID
    title: str = Field(..., max_length=200)
    deadline: date | None = None
    status: UniqueGoalStatus = UniqueGoalStatus.NOT_STARTED
    context: str | None = None
    depends_on: UUID | None = None


class UniqueGoalCreate(UniqueGoalBase):
    pass


class UniqueGoalUpdate(BaseSchema):
    role_id: UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    deadline: date | None = None
    status: UniqueGoalStatus | None = None
    context: str | None = None
    depends_on: UUID | None = None


class UniqueGoal(UniqueGoalBase):
    id: UUID


# ============ Task Instance ============
class TaskInstanceBase(BaseSchema):
    role_id: UUID | None = None
    source_id: UUID | None = Field(default=None, description="FK to recurring_goal or unique_goal")
    title: str = Field(..., max_length=200)
    scheduled_date: date
    due_date: date | None = None
    target_time: int | None = Field(default=None, description="Expected duration in minutes")
    status: TaskStatus = TaskStatus.PENDING
    context: str | None = None
    calendar_event_id: str | None = None


class TaskInstanceCreate(TaskInstanceBase):
    pass


class TaskInstanceUpdate(BaseSchema):
    role_id: UUID | None = None
    source_id: UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    scheduled_date: date | None = None
    due_date: date | None = None
    target_time: int | None = None
    status: TaskStatus | None = None
    context: str | None = None
    calendar_event_id: str | None = None


class TaskInstance(TaskInstanceBase):
    id: UUID
    completed_at: datetime | None = None


# Rebuild models to resolve forward references
PMSCategoryWithStatements.model_rebuild()
RoleWithGoals.model_rebuild()
