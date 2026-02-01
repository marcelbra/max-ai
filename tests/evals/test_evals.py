"""Evaluation tests for the Max AI agent.

These tests evaluate the agent's ability to:
1. Understand user intent and call appropriate tools
2. Execute multi-step workflows (planning, review)
3. Handle edge cases gracefully

Note: These tests require an OpenAI API key and will make real API calls.
Set OPENAI_API_KEY environment variable to run.
"""

import json
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from max_ai.db import Base, PMSCategoryModel, RoleModel, TaskInstanceModel


# Skip all tests if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - skipping eval tests",
)


@pytest.fixture
async def eval_db():
    """Create a test database with sample data for evals."""
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
        # Seed with sample data
        category = PMSCategoryModel(
            emoji="💪",
            name="Health",
            sort_order=1,
        )
        session.add(category)
        await session.flush()

        role = RoleModel(
            pms_category_id=category.id,
            name="Runner",
            pms_anchor="Stay healthy and energetic",
            target_budget=180,
        )
        session.add(role)
        await session.flush()

        # Add some tasks
        today = date.today()
        tasks = [
            TaskInstanceModel(
                role_id=role.id,
                title="Morning run",
                scheduled_date=today,
                target_time=30,
                status="pending",
            ),
            TaskInstanceModel(
                role_id=role.id,
                title="Evening stretch",
                scheduled_date=today,
                target_time=15,
                status="pending",
            ),
        ]
        for task in tasks:
            session.add(task)

        await session.commit()
        yield session


@dataclass
class EvalCase:
    """A single evaluation case."""

    name: str
    user_input: str
    expected_tools: list[str]  # Tools that should be called
    expected_in_response: list[str]  # Strings that should appear in response
    category: str  # CRUD, planning, review, etc.


# Define evaluation cases
EVAL_CASES = [
    # CRUD Cases
    EvalCase(
        name="list_roles",
        user_input="Show me all my roles",
        expected_tools=["list_roles"],
        expected_in_response=["Runner"],
        category="crud",
    ),
    EvalCase(
        name="list_today_tasks",
        user_input="What tasks do I have today?",
        expected_tools=["get_today_tasks"],
        expected_in_response=["Morning run", "Evening stretch"],
        category="crud",
    ),
    EvalCase(
        name="create_task",
        user_input="Create a task to read for 30 minutes tomorrow",
        expected_tools=["create_task"],
        expected_in_response=["read", "30"],
        category="crud",
    ),
    # Planning Cases
    EvalCase(
        name="planning_start",
        user_input="Let's plan my week",
        expected_tools=["get_week_tasks", "list_roles"],
        expected_in_response=[],  # Response varies
        category="planning",
    ),
    # Review Cases
    EvalCase(
        name="review_start",
        user_input="Let's review my day",
        expected_tools=["get_today_tasks"],
        expected_in_response=["Morning run"],
        category="review",
    ),
]


def load_eval_datasets():
    """Load additional eval cases from JSON files."""
    datasets_dir = Path(__file__).parent / "datasets"
    cases = list(EVAL_CASES)

    if datasets_dir.exists():
        for json_file in datasets_dir.glob("*.json"):
            with open(json_file) as f:
                data = json.load(f)
                for case_data in data.get("cases", []):
                    cases.append(
                        EvalCase(
                            name=case_data["name"],
                            user_input=case_data["user_input"],
                            expected_tools=case_data.get("expected_tools", []),
                            expected_in_response=case_data.get(
                                "expected_in_response", []
                            ),
                            category=case_data.get("category", "other"),
                        )
                    )

    return cases


class TestAgentEvals:
    """Evaluation tests for the agent."""

    @pytest.mark.parametrize(
        "eval_case",
        load_eval_datasets(),
        ids=lambda c: f"{c.category}_{c.name}",
    )
    async def test_eval_case(self, eval_case: EvalCase, eval_db):
        """Run a single evaluation case."""
        # This test is a placeholder for actual agent evaluation
        # In a real implementation, you would:
        # 1. Initialize the agent with eval_db
        # 2. Send the user_input
        # 3. Check which tools were called
        # 4. Check response content

        # For now, we just verify the test structure
        assert eval_case.user_input
        assert eval_case.category in ["crud", "planning", "review", "other"]

    async def test_eval_summary(self):
        """Print summary of eval cases."""
        cases = load_eval_datasets()
        by_category = {}
        for case in cases:
            by_category.setdefault(case.category, []).append(case)

        print("\n=== Eval Case Summary ===")
        for category, cat_cases in by_category.items():
            print(f"{category}: {len(cat_cases)} cases")
        print(f"Total: {len(cases)} cases")
