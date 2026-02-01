import pytest
from httpx import ASGITransport, AsyncClient

from max_ai.api import create_app
from max_ai.db import reset_engine


@pytest.fixture
async def client():
    reset_engine()
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ============ Health ============

async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


# ============ PMS Categories ============

async def test_list_categories(client):
    response = await client.get("/api/pms/categories")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_create_category(client):
    response = await client.post("/api/pms/categories", json={
        "emoji": "🎯",
        "name": "Test Category",
        "sort_order": 99
    })
    assert response.status_code == 201
    data = response.json()
    assert data["emoji"] == "🎯"
    assert data["name"] == "Test Category"
    assert "id" in data


async def test_get_category(client):
    # Create first
    create_resp = await client.post("/api/pms/categories", json={
        "emoji": "📚",
        "name": "Reading"
    })
    category_id = create_resp.json()["id"]

    # Get it
    response = await client.get(f"/api/pms/categories/{category_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Reading"


async def test_update_category(client):
    # Create first
    create_resp = await client.post("/api/pms/categories", json={
        "emoji": "🔧",
        "name": "Original"
    })
    category_id = create_resp.json()["id"]

    # Update it
    response = await client.patch(f"/api/pms/categories/{category_id}", json={
        "name": "Updated"
    })
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"


async def test_delete_category(client):
    # Create first
    create_resp = await client.post("/api/pms/categories", json={
        "emoji": "🗑️",
        "name": "To Delete"
    })
    category_id = create_resp.json()["id"]

    # Delete it
    response = await client.delete(f"/api/pms/categories/{category_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_resp = await client.get(f"/api/pms/categories/{category_id}")
    assert get_resp.status_code == 404


async def test_get_category_not_found(client):
    response = await client.get("/api/pms/categories/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ============ PMS Statements ============

async def test_create_statement(client):
    # Create category first
    cat_resp = await client.post("/api/pms/categories", json={
        "emoji": "💡",
        "name": "Ideas"
    })
    category_id = cat_resp.json()["id"]

    # Create statement
    response = await client.post("/api/pms/statements", json={
        "category_id": category_id,
        "statement": "I value creative thinking."
    })
    assert response.status_code == 201
    assert response.json()["statement"] == "I value creative thinking."


async def test_list_statements_by_category(client):
    # Create category
    cat_resp = await client.post("/api/pms/categories", json={
        "emoji": "🌟",
        "name": "Stars"
    })
    category_id = cat_resp.json()["id"]

    # Create statement
    await client.post("/api/pms/statements", json={
        "category_id": category_id,
        "statement": "Test statement"
    })

    # List filtered
    response = await client.get(f"/api/pms/statements?category_id={category_id}")
    assert response.status_code == 200
    assert len(response.json()) >= 1


# ============ Roles ============

async def test_list_roles(client):
    response = await client.get("/api/roles")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_create_role(client):
    # Create category first
    cat_resp = await client.post("/api/pms/categories", json={
        "emoji": "👨‍💻",
        "name": "Work"
    })
    category_id = cat_resp.json()["id"]

    # Create role
    response = await client.post("/api/roles", json={
        "pms_category_id": category_id,
        "name": "Developer",
        "target_budget": 2400
    })
    assert response.status_code == 201
    assert response.json()["name"] == "Developer"


async def test_get_role_with_goals(client):
    # Create category and role
    cat_resp = await client.post("/api/pms/categories", json={
        "emoji": "🏃",
        "name": "Fitness"
    })
    category_id = cat_resp.json()["id"]

    role_resp = await client.post("/api/roles", json={
        "pms_category_id": category_id,
        "name": "Athlete"
    })
    role_id = role_resp.json()["id"]

    # Get role (includes goals)
    response = await client.get(f"/api/roles/{role_id}")
    assert response.status_code == 200
    assert "recurring_goals" in response.json()
    assert "unique_goals" in response.json()


# ============ Recurring Goals ============

async def test_list_recurring_goals(client):
    response = await client.get("/api/goals/recurring")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_create_recurring_goal(client):
    # Create category and role
    cat_resp = await client.post("/api/pms/categories", json={"emoji": "📖", "name": "Learning"})
    role_resp = await client.post("/api/roles", json={
        "pms_category_id": cat_resp.json()["id"],
        "name": "Student"
    })
    role_id = role_resp.json()["id"]

    # Create recurring goal
    response = await client.post("/api/goals/recurring", json={
        "role_id": role_id,
        "activity": "Study for 1 hour",
        "target_amount": 5.0,
        "target_time": 60
    })
    assert response.status_code == 201
    assert response.json()["activity"] == "Study for 1 hour"


async def test_filter_recurring_goals_by_role(client):
    # Create category and role
    cat_resp = await client.post("/api/pms/categories", json={"emoji": "🎵", "name": "Music"})
    role_resp = await client.post("/api/roles", json={
        "pms_category_id": cat_resp.json()["id"],
        "name": "Musician"
    })
    role_id = role_resp.json()["id"]

    # Create goal
    await client.post("/api/goals/recurring", json={
        "role_id": role_id,
        "activity": "Practice guitar",
        "target_amount": 3.0,
        "target_time": 30
    })

    # Filter by role
    response = await client.get(f"/api/goals/recurring?role_id={role_id}")
    assert response.status_code == 200
    assert len(response.json()) >= 1


# ============ Unique Goals ============

async def test_list_unique_goals(client):
    response = await client.get("/api/goals/unique")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_create_unique_goal(client):
    # Create category and role
    cat_resp = await client.post("/api/pms/categories", json={"emoji": "🎓", "name": "Education"})
    role_resp = await client.post("/api/roles", json={
        "pms_category_id": cat_resp.json()["id"],
        "name": "Learner"
    })
    role_id = role_resp.json()["id"]

    # Create unique goal
    response = await client.post("/api/goals/unique", json={
        "role_id": role_id,
        "title": "Complete Python course",
        "deadline": "2026-03-01"
    })
    assert response.status_code == 201
    assert response.json()["title"] == "Complete Python course"
    assert response.json()["status"] == "not_started"


async def test_update_unique_goal_status(client):
    # Create category, role, and goal
    cat_resp = await client.post("/api/pms/categories", json={"emoji": "✅", "name": "Tasks"})
    role_resp = await client.post("/api/roles", json={
        "pms_category_id": cat_resp.json()["id"],
        "name": "Doer"
    })
    goal_resp = await client.post("/api/goals/unique", json={
        "role_id": role_resp.json()["id"],
        "title": "Test goal"
    })
    goal_id = goal_resp.json()["id"]

    # Update status
    response = await client.patch(f"/api/goals/unique/{goal_id}", json={
        "status": "in_progress"
    })
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


# ============ Tasks ============

async def test_list_tasks(client):
    response = await client.get("/api/tasks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_today_tasks(client):
    response = await client.get("/api/tasks/today")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_week_tasks(client):
    response = await client.get("/api/tasks/week")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_create_task(client):
    response = await client.post("/api/tasks", json={
        "title": "Test task",
        "scheduled_date": "2026-02-01",
        "target_time": 30
    })
    assert response.status_code == 201
    assert response.json()["title"] == "Test task"
    assert response.json()["status"] == "pending"


async def test_complete_task(client):
    # Create task
    create_resp = await client.post("/api/tasks", json={
        "title": "Task to complete",
        "scheduled_date": "2026-02-01"
    })
    task_id = create_resp.json()["id"]

    # Complete it
    response = await client.post(f"/api/tasks/{task_id}/complete")
    assert response.status_code == 200
    assert response.json()["status"] == "done"
    assert response.json()["completed_at"] is not None


async def test_skip_task(client):
    # Create task
    create_resp = await client.post("/api/tasks", json={
        "title": "Task to skip",
        "scheduled_date": "2026-02-01"
    })
    task_id = create_resp.json()["id"]

    # Skip it
    response = await client.post(f"/api/tasks/{task_id}/skip")
    assert response.status_code == 200
    assert response.json()["status"] == "skipped"


async def test_delete_task(client):
    # Create task
    create_resp = await client.post("/api/tasks", json={
        "title": "Task to delete",
        "scheduled_date": "2026-02-01"
    })
    task_id = create_resp.json()["id"]

    # Delete it
    response = await client.delete(f"/api/tasks/{task_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_resp = await client.get(f"/api/tasks/{task_id}")
    assert get_resp.status_code == 404


async def test_task_not_found(client):
    response = await client.get("/api/tasks/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_complete_task_not_found(client):
    response = await client.post("/api/tasks/00000000-0000-0000-0000-000000000000/complete")
    assert response.status_code == 404
