import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PMSCategoryModel(Base):
    __tablename__ = "pms_category"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    emoji: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0)

    # Relationships
    statements: Mapped[list["PMSStatementModel"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )
    roles: Mapped[list["RoleModel"]] = relationship(
        back_populates="pms_category", cascade="all, delete-orphan"
    )


class PMSStatementModel(Base):
    __tablename__ = "pms_statement"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pms_category.id", ondelete="CASCADE"), nullable=False
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0)

    # Relationships
    category: Mapped["PMSCategoryModel"] = relationship(back_populates="statements")


class RoleModel(Base):
    __tablename__ = "role"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pms_category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pms_category.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(nullable=False)
    pms_anchor: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_budget: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Relationships
    pms_category: Mapped["PMSCategoryModel"] = relationship(back_populates="roles")
    recurring_goals: Mapped[list["RecurringGoalModel"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    unique_goals: Mapped[list["UniqueGoalModel"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["TaskInstanceModel"]] = relationship(back_populates="role")


class RecurringGoalModel(Base):
    __tablename__ = "recurring_goal"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("role.id", ondelete="CASCADE"), nullable=False
    )
    activity: Mapped[str] = mapped_column(nullable=False)
    target_amount: Mapped[float] = mapped_column(nullable=False)
    target_time: Mapped[int] = mapped_column(nullable=False)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    role: Mapped["RoleModel"] = relationship(back_populates="recurring_goals")


class UniqueGoalModel(Base):
    __tablename__ = "unique_goal"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("role.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(nullable=False)
    deadline: Mapped[Optional[date]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(default="not_started")
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    depends_on: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("unique_goal.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    role: Mapped["RoleModel"] = relationship(back_populates="unique_goals")
    dependency: Mapped[Optional["UniqueGoalModel"]] = relationship(
        remote_side=[id], foreign_keys=[depends_on]
    )


class TaskInstanceModel(Base):
    __tablename__ = "task_instance"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    role_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("role.id", ondelete="SET NULL"), nullable=True
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    title: Mapped[str] = mapped_column(nullable=False)
    scheduled_date: Mapped[date] = mapped_column(nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    target_time: Mapped[Optional[int]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(default="pending")
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    calendar_event_id: Mapped[Optional[str]] = mapped_column(nullable=True)

    # Relationships
    role: Mapped[Optional["RoleModel"]] = relationship(back_populates="tasks")
