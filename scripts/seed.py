#!/usr/bin/env python3
"""Seed the database with sample data."""

import asyncio
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from max_ai.db import (
    PMSCategoryModel,
    PMSStatementModel,
    RecurringGoalModel,
    RoleModel,
    TaskInstanceModel,
    UniqueGoalModel,
    get_session_factory,
)


async def seed_data(session: AsyncSession) -> None:
    # Check if data already exists
    result = await session.execute(select(PMSCategoryModel).limit(1))
    if result.scalar_one_or_none():
        print("Database already seeded. Skipping.")
        return

    # Create PMS Categories
    categories = [
        PMSCategoryModel(
            id=uuid.uuid4(),
            emoji="🧠",
            name="Self",
            sort_order=0,
        ),
        PMSCategoryModel(
            id=uuid.uuid4(),
            emoji="💪",
            name="Health",
            sort_order=1,
        ),
        PMSCategoryModel(
            id=uuid.uuid4(),
            emoji="💼",
            name="Career",
            sort_order=2,
        ),
        PMSCategoryModel(
            id=uuid.uuid4(),
            emoji="❤️",
            name="Relationships",
            sort_order=3,
        ),
    ]
    session.add_all(categories)

    # Create PMS Statements
    statements = [
        PMSStatementModel(
            id=uuid.uuid4(),
            category_id=categories[0].id,
            statement="I prioritize continuous learning and personal growth.",
            sort_order=0,
        ),
        PMSStatementModel(
            id=uuid.uuid4(),
            category_id=categories[0].id,
            statement="I maintain clarity of mind through regular reflection.",
            sort_order=1,
        ),
        PMSStatementModel(
            id=uuid.uuid4(),
            category_id=categories[1].id,
            statement="I invest in my physical health daily.",
            sort_order=0,
        ),
        PMSStatementModel(
            id=uuid.uuid4(),
            category_id=categories[2].id,
            statement="I build expertise and deliver value through my work.",
            sort_order=0,
        ),
        PMSStatementModel(
            id=uuid.uuid4(),
            category_id=categories[3].id,
            statement="I nurture meaningful connections with family and friends.",
            sort_order=0,
        ),
    ]
    session.add_all(statements)

    # Create Roles
    roles = [
        RoleModel(
            id=uuid.uuid4(),
            pms_category_id=categories[0].id,
            name="Lifelong Learner",
            pms_anchor="Continuous learning and personal growth",
            current_state="Reading 2 books per month",
            context="Focus on technical and personal development books",
            target_budget=300,  # 5 hours per week
        ),
        RoleModel(
            id=uuid.uuid4(),
            pms_category_id=categories[1].id,
            name="Athlete",
            pms_anchor="Physical health and fitness",
            current_state="Working out 4x per week",
            context="Mix of strength training and cardio",
            target_budget=360,  # 6 hours per week
        ),
        RoleModel(
            id=uuid.uuid4(),
            pms_category_id=categories[2].id,
            name="Software Engineer",
            pms_anchor="Building expertise and delivering value",
            current_state="Working on max-ai project",
            context="Focus on AI and full-stack development",
            target_budget=2400,  # 40 hours per week
        ),
    ]
    session.add_all(roles)

    # Create Recurring Goals
    recurring_goals = [
        RecurringGoalModel(
            id=uuid.uuid4(),
            role_id=roles[0].id,
            activity="Read for 30 minutes",
            target_amount=7.0,  # Daily
            target_time=30,
            context="Morning or evening reading session",
            active=True,
        ),
        RecurringGoalModel(
            id=uuid.uuid4(),
            role_id=roles[1].id,
            activity="Workout",
            target_amount=4.0,  # 4x per week
            target_time=60,
            context="Strength training or cardio",
            active=True,
        ),
        RecurringGoalModel(
            id=uuid.uuid4(),
            role_id=roles[1].id,
            activity="Meditation",
            target_amount=7.0,  # Daily
            target_time=15,
            context="Morning meditation practice",
            active=True,
        ),
    ]
    session.add_all(recurring_goals)

    # Create Unique Goals
    unique_goals = [
        UniqueGoalModel(
            id=uuid.uuid4(),
            role_id=roles[2].id,
            title="Complete max-ai Phase 1",
            deadline=date.today() + timedelta(days=14),
            status="in_progress",
            context="Foundation setup with API and data layer",
        ),
        UniqueGoalModel(
            id=uuid.uuid4(),
            role_id=roles[0].id,
            title="Finish current book",
            deadline=date.today() + timedelta(days=7),
            status="in_progress",
            context=None,
        ),
    ]
    session.add_all(unique_goals)

    # Create some Task Instances for today
    today = date.today()
    tasks = [
        TaskInstanceModel(
            id=uuid.uuid4(),
            role_id=roles[0].id,
            source_id=recurring_goals[0].id,
            title="Read for 30 minutes",
            scheduled_date=today,
            target_time=30,
            status="pending",
        ),
        TaskInstanceModel(
            id=uuid.uuid4(),
            role_id=roles[1].id,
            source_id=recurring_goals[1].id,
            title="Morning workout",
            scheduled_date=today,
            target_time=60,
            status="pending",
        ),
        TaskInstanceModel(
            id=uuid.uuid4(),
            role_id=roles[1].id,
            source_id=recurring_goals[2].id,
            title="Morning meditation",
            scheduled_date=today,
            target_time=15,
            status="pending",
        ),
        TaskInstanceModel(
            id=uuid.uuid4(),
            role_id=roles[2].id,
            source_id=unique_goals[0].id,
            title="Implement FastAPI endpoints",
            scheduled_date=today,
            target_time=120,
            status="pending",
            context="Part of Phase 1",
        ),
    ]
    session.add_all(tasks)

    await session.commit()
    print("Database seeded successfully!")


async def main() -> None:
    async with get_session_factory()() as session:
        await seed_data(session)


if __name__ == "__main__":
    asyncio.run(main())
