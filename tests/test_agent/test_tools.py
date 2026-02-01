"""Tests for agent tools."""

from dataclasses import dataclass
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from max_ai.db import (
    Base,
    PMSCategoryModel,
    PMSStatementModel,
    RecurringGoalModel,
    RoleModel,
    TaskInstanceModel,
    UniqueGoalModel,
)
from max_ai.agent.tools.pms import (
    CreatePMSCategoryInput,
    CreatePMSStatementInput,
    DeletePMSCategoryInput,
    UpdatePMSCategoryInput,
    create_pms_category,
    create_pms_statement,
    delete_pms_category,
    list_pms_categories,
    update_pms_category,
)
from max_ai.agent.tools.roles import (
    CreateRoleInput,
    DeleteRoleInput,
    UpdateRoleInput,
    create_role,
    delete_role,
    list_roles,
    update_role,
)
from max_ai.agent.tools.goals import (
    CreateRecurringGoalInput,
    CreateUniqueGoalInput,
    DeleteRecurringGoalInput,
    UpdateRecurringGoalInput,
    create_recurring_goal,
    create_unique_goal,
    delete_recurring_goal,
    list_recurring_goals,
    list_unique_goals,
    update_recurring_goal,
)
from max_ai.agent.tools.tasks import (
    CompleteTaskInput,
    CreateTaskInput,
    DeleteTaskInput,
    SkipTaskInput,
    UpdateTaskInput,
    complete_task,
    create_task,
    delete_task,
    get_today_tasks,
    get_week_tasks,
    skip_task,
    update_task,
)


@dataclass
class MockAgentDeps:
    """Mock dependencies for agent tool tests."""

    db: AsyncSession


class MockRunContext:
    """Mock RunContext for tool testing."""

    def __init__(self, deps: MockAgentDeps):
        self.deps = deps


@pytest.fixture
async def db():
    """Create an async in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session


@pytest.fixture
def ctx(db):
    """Create a mock context with database session."""
    return MockRunContext(MockAgentDeps(db=db))


# ============ PMS Category Tests ============


class TestPMSCategoryTools:
    async def test_list_empty_categories(self, ctx):
        """Test listing categories when none exist."""
        result = await list_pms_categories(ctx)
        assert result == []

    async def test_create_category(self, ctx):
        """Test creating a PMS category."""
        input_data = CreatePMSCategoryInput(
            emoji="💪",
            name="Health",
            sort_order=1,
        )
        result = await create_pms_category(ctx, input_data)

        assert "id" in result
        assert result["emoji"] == "💪"
        assert result["name"] == "Health"
        assert result["sort_order"] == 1

    async def test_update_category(self, ctx):
        """Test updating a PMS category."""
        # Create first
        create_input = CreatePMSCategoryInput(emoji="💪", name="Health")
        created = await create_pms_category(ctx, create_input)

        # Update
        update_input = UpdatePMSCategoryInput(
            category_id=created["id"],
            name="Wellness",
        )
        result = await update_pms_category(ctx, update_input)

        assert result["name"] == "Wellness"
        assert result["emoji"] == "💪"  # Unchanged

    async def test_delete_category_preview(self, ctx):
        """Test delete preview without confirmation."""
        # Create category
        create_input = CreatePMSCategoryInput(emoji="💪", name="Health")
        created = await create_pms_category(ctx, create_input)

        # Delete without confirmation
        delete_input = DeletePMSCategoryInput(
            category_id=created["id"],
            confirmed=False,
        )
        result = await delete_pms_category(ctx, delete_input)

        assert result["preview"] is True
        assert "Would delete" in result["message"]

    async def test_delete_category_confirmed(self, ctx):
        """Test confirmed delete."""
        # Create category
        create_input = CreatePMSCategoryInput(emoji="💪", name="Health")
        created = await create_pms_category(ctx, create_input)

        # Delete with confirmation
        delete_input = DeletePMSCategoryInput(
            category_id=created["id"],
            confirmed=True,
        )
        result = await delete_pms_category(ctx, delete_input)

        assert result["deleted"] is True

        # Verify it's gone
        categories = await list_pms_categories(ctx)
        assert len(categories) == 0


# ============ Role Tests ============


class TestRoleTools:
    @pytest.fixture
    async def category(self, ctx):
        """Create a category for role tests."""
        input_data = CreatePMSCategoryInput(emoji="💼", name="Career")
        result = await create_pms_category(ctx, input_data)
        return result

    async def test_create_role(self, ctx, category):
        """Test creating a role."""
        input_data = CreateRoleInput(
            pms_category_id=category["id"],
            name="Software Engineer",
            pms_anchor="Building great software",
            target_budget=600,
        )
        result = await create_role(ctx, input_data)

        assert "id" in result
        assert result["name"] == "Software Engineer"
        assert result["target_budget"] == 600

    async def test_list_roles(self, ctx, category):
        """Test listing roles."""
        # Create role
        input_data = CreateRoleInput(
            pms_category_id=category["id"],
            name="Engineer",
        )
        await create_role(ctx, input_data)

        result = await list_roles(ctx)
        assert len(result) == 1
        assert result[0]["name"] == "Engineer"

    async def test_update_role(self, ctx, category):
        """Test updating a role."""
        # Create
        create_input = CreateRoleInput(
            pms_category_id=category["id"],
            name="Developer",
        )
        created = await create_role(ctx, create_input)

        # Update
        update_input = UpdateRoleInput(
            role_id=created["id"],
            name="Senior Developer",
            target_budget=480,
        )
        result = await update_role(ctx, update_input)

        assert result["name"] == "Senior Developer"
        assert result["target_budget"] == 480


# ============ Recurring Goal Tests ============


class TestRecurringGoalTools:
    @pytest.fixture
    async def role(self, ctx):
        """Create category and role for goal tests."""
        cat_input = CreatePMSCategoryInput(emoji="💪", name="Health")
        category = await create_pms_category(ctx, cat_input)

        role_input = CreateRoleInput(
            pms_category_id=category["id"],
            name="Runner",
        )
        return await create_role(ctx, role_input)

    async def test_create_recurring_goal(self, ctx, role):
        """Test creating a recurring goal."""
        input_data = CreateRecurringGoalInput(
            role_id=role["id"],
            activity="Morning Run",
            target_amount=3.0,
            target_time=30,
        )
        result = await create_recurring_goal(ctx, input_data)

        assert "id" in result
        assert result["activity"] == "Morning Run"
        assert result["target_amount"] == 3.0
        assert result["target_time"] == 30

    async def test_list_recurring_goals(self, ctx, role):
        """Test listing recurring goals."""
        input_data = CreateRecurringGoalInput(
            role_id=role["id"],
            activity="Run",
            target_amount=3.0,
            target_time=30,
        )
        await create_recurring_goal(ctx, input_data)

        result = await list_recurring_goals(ctx)
        assert len(result) == 1

    async def test_update_recurring_goal(self, ctx, role):
        """Test updating a recurring goal."""
        # Create
        create_input = CreateRecurringGoalInput(
            role_id=role["id"],
            activity="Run",
            target_amount=3.0,
            target_time=30,
        )
        created = await create_recurring_goal(ctx, create_input)

        # Update
        update_input = UpdateRecurringGoalInput(
            goal_id=created["id"],
            target_amount=4.0,
            target_time=45,
        )
        result = await update_recurring_goal(ctx, update_input)

        assert result["target_amount"] == 4.0
        assert result["target_time"] == 45


# ============ Task Tests ============


class TestTaskTools:
    async def test_create_task(self, ctx):
        """Test creating a task."""
        input_data = CreateTaskInput(
            title="Test Task",
            scheduled_date=date.today(),
            target_time=30,
        )
        result = await create_task(ctx, input_data)

        assert "id" in result
        assert result["title"] == "Test Task"
        assert result["status"] == "pending"

    async def test_get_today_tasks(self, ctx):
        """Test getting today's tasks."""
        # Create task for today
        input_data = CreateTaskInput(
            title="Today's Task",
            scheduled_date=date.today(),
        )
        await create_task(ctx, input_data)

        result = await get_today_tasks(ctx)
        assert len(result) == 1
        assert result[0]["title"] == "Today's Task"

    async def test_complete_task(self, ctx):
        """Test completing a task."""
        # Create
        create_input = CreateTaskInput(
            title="Task to Complete",
            scheduled_date=date.today(),
        )
        created = await create_task(ctx, create_input)

        # Complete
        complete_input = CompleteTaskInput(task_id=created["id"])
        result = await complete_task(ctx, complete_input)

        assert result["status"] == "done"
        assert result["completed_at"] is not None

    async def test_skip_task(self, ctx):
        """Test skipping a task."""
        # Create
        create_input = CreateTaskInput(
            title="Task to Skip",
            scheduled_date=date.today(),
        )
        created = await create_task(ctx, create_input)

        # Skip
        skip_input = SkipTaskInput(task_id=created["id"])
        result = await skip_task(ctx, skip_input)

        assert result["status"] == "skipped"

    async def test_delete_task_preview(self, ctx):
        """Test delete preview without confirmation."""
        # Create
        create_input = CreateTaskInput(
            title="Task to Delete",
            scheduled_date=date.today(),
        )
        created = await create_task(ctx, create_input)

        # Delete without confirmation
        delete_input = DeleteTaskInput(
            task_id=created["id"],
            confirmed=False,
        )
        result = await delete_task(ctx, delete_input)

        assert result["preview"] is True

    async def test_update_task(self, ctx):
        """Test updating a task."""
        # Create
        create_input = CreateTaskInput(
            title="Original Title",
            scheduled_date=date.today(),
        )
        created = await create_task(ctx, create_input)

        # Update
        update_input = UpdateTaskInput(
            task_id=created["id"],
            title="Updated Title",
            target_time=60,
        )
        result = await update_task(ctx, update_input)

        assert result["title"] == "Updated Title"
        assert result["target_time"] == 60
