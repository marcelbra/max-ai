# max-ai Technical Specification

*Personal Life OS with AI-Powered Accountability*

**Version:** 0.3 (Draft)
**Last Updated:** February 2025

---

## 1. Concept

A personal AI assistant that helps manage life goals, tasks, and accountability through natural language conversation. The system operationalizes a personal mission statement into actionable daily tasks and provides structured planning/review workflows.

**Core value proposition:**

- Transforms static life planning documents into dynamic, executable system
- Agent holds user accountable through structured daily workflows
- Natural language interface for all CRUD operations
- Connects intentions to real calendar entries (calendar = source of truth)

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Terminal Chat (CLI)                        │
│   - Agent conversations                                         │
│   - Planning workflow                                           │
│   - Review workflow                                             │
│   - Ad-hoc commands                                             │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Backend API (FastAPI)                    │
│  - REST endpoints (Swagger for dev inspection)                  │
│  - Agent orchestration endpoint                                 │
└─────────────────────────────┬───────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
 ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
 │   Agent Core    │ │   Data Layer    │ │  Integrations   │
 │   (Pydantic AI) │ │   (SQLAlchemy)  │ │                 │
 │                 │ │                 │ │  - Apple Cal    │
 │  - LLM Adapter  │ │  - Postgres     │ │    (Phase 3+)   │
 │  - Tools        │ │  - Pydantic     │ │                 │
 │  - Skills       │ │    Models       │ │                 │
 └─────────────────┘ └────────┬────────┘ └─────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Observability                           │
├───────────────────────────────┬─────────────────────────────────┤
│   LLM Observability           │   App Observability             │
│   (LangWatch)                 │   (Python logging)              │
│   - Trace LLM calls           │   - Basic structured logging    │
│   - Evals                     │   - Request/response logs       │
│   - Cost tracking             │   - Error tracking              │
└───────────────────────────────┴─────────────────────────────────┘
```

---

## 3. Tech Stack

| Layer              | Technology              | Notes                                  |
| ------------------ | ----------------------- | -------------------------------------- |
| Package management | UV                      | Fast Python package manager            |
| Backend framework  | FastAPI                 | REST API + Swagger docs                |
| Agent framework    | Pydantic AI             | Tool calling, structured outputs       |
| ORM                | SQLAlchemy 2.0          | Async support                          |
| Database           | PostgreSQL              | Local Docker instance                  |
| Data validation    | Pydantic v2             | Shared models between API and agent    |
| LLM                | OpenAI API (default)    | Abstracted via adapter pattern         |
| LLM Observability  | LangWatch               | Tracing, evals, cost (agent only)      |
| App Observability  | Python logging          | Basic logging, upgrade later if needed |
| CLI                | Simple input/print      | Minimal chat loop                      |
| Calendar           | Apple Calendar (CalDAV) | Phase 4+ integration                   |

---

## 4. Data Model

### 4.1 Entity Hierarchy

```
PMS Category (values)
    └── PMS Statement (principles)
    └── Role (operational context)
            ├── Recurring Goal (habits)
            │       └── Task Instance (daily execution)
            └── Unique Goal (milestones)
                    └── Task Instance (work items)
```

### 4.2 Core Entities

**pms_category**

| Field      | Type    | Description                            |
| ---------- | ------- | -------------------------------------- |
| id         | UUID    | Primary key                            |
| emoji      | String  | Visual identifier                      |
| name       | String  | Category name (e.g., "Self", "Health") |
| sort_order | Integer | Display order                          |

**pms_statement**

| Field       | Type    | Description           |
| ----------- | ------- | --------------------- |
| id          | UUID    | Primary key           |
| category_id | FK      | Links to pms_category |
| statement   | Text    | The guiding principle |
| sort_order  | Integer | Order within category |

**role**

| Field           | Type    | Description                      |
| --------------- | ------- | -------------------------------- |
| id              | UUID    | Primary key                      |
| pms_category_id | FK      | Links to pms_category            |
| name            | String  | Role identifier                  |
| pms_anchor      | Text    | Summary of linked PMS statements |
| current_state   | Text    | Snapshot of current situation    |
| context         | Text    | Background, constraints          |
| target_budget   | Integer | Weekly minutes target            |

**recurring_goal**

| Field         | Type    | Description                                 |
| ------------- | ------- | ------------------------------------------- |
| id            | UUID    | Primary key                                 |
| role_id       | FK      | Links to role                               |
| activity      | String  | What to do                                  |
| target_amount | Float   | Frequency per week (e.g., 0.25 for monthly) |
| target_time   | Integer | Duration per occurrence (minutes)           |
| context       | Text    | Special instructions (nullable)             |
| active        | Boolean | Whether goal is active                      |

**unique_goal**

| Field      | Type   | Description                                             |
| ---------- | ------ | ------------------------------------------------------- |
| id         | UUID   | Primary key                                             |
| role_id    | FK     | Links to role                                           |
| title      | String | Goal description                                        |
| deadline   | Date   | Target completion date (nullable)                       |
| status     | Enum   | not_started, in_progress, completed, cancelled, at_risk |
| context    | Text   | Additional details                                      |
| depends_on | FK     | Optional dependency on another unique_goal              |

**task_instance**

| Field             | Type      | Description                                              |
| ----------------- | --------- | -------------------------------------------------------- |
| id                | UUID      | Primary key                                              |
| role_id           | FK        | Links to role (nullable for chores)                      |
| source_id         | UUID      | FK to recurring_goal or unique_goal (nullable for adhoc) |
| title             | String    | Task description                                         |
| scheduled_date    | Date      | When task is scheduled                                   |
| due_date          | Date      | Hard deadline (nullable)                                 |
| target_time       | Integer   | Expected duration (minutes)                              |
| status            | Enum      | pending, done, skipped                                   |
| completed_at      | Timestamp | When marked complete (nullable)                          |
| context           | Text      | Notes, special instructions (nullable)                   |
| calendar_event_id | String    | Link to Apple Calendar event (nullable)                  |

**weekly_review**

| Field        | Type      | Description               |
| ------------ | --------- | ------------------------- |
| id           | UUID      | Primary key               |
| week_start   | Date      | Monday of the week        |
| completed_at | Timestamp | When review was done      |
| summary      | JSON      | Aggregated stats per role |
| wins         | Text      | What went well            |
| misses       | Text      | What was missed           |
| blockers     | Text      | Identified obstacles      |
| adjustments  | Text      | Changes for next week     |

---

## 5. Agent Design

### 5.1 LLM Adapter Pattern

Abstract interface allowing swap between:

- OpenAI (GPT-4o, GPT-4o-mini)
- Anthropic (Claude)
- Google (Gemini)
- Local models (Ollama)

Selection via environment variable or runtime config.

### 5.2 Agent Tools

Tools organized by domain:

**PMS Tools**

- `list_pms_categories()` — Get all categories with statements
- `create_pms_category(emoji, name)` — Add category
- `update_pms_category(id, ...)` — Modify category
- `delete_pms_category(id)` — Remove category (requires confirmation)
- `create_pms_statement(category_id, statement)` — Add statement
- `update_pms_statement(id, ...)` — Modify statement
- `delete_pms_statement(id)` — Remove statement (requires confirmation)

**Role Tools**

- `list_roles()` — Get all roles
- `create_role(...)` — Add role
- `update_role(id, ...)` — Modify role
- `delete_role(id)` — Remove role (requires confirmation)

**Goal Tools**

- `list_recurring_goals(role_id?)` — Get recurring goals, optionally filtered
- `create_recurring_goal(...)` — Add recurring goal
- `update_recurring_goal(id, ...)` — Modify recurring goal
- `delete_recurring_goal(id)` — Remove recurring goal (requires confirmation)
- `list_unique_goals(role_id?, status?)` — Get unique goals with filters
- `create_unique_goal(...)` — Add unique goal
- `update_unique_goal(id, ...)` — Modify unique goal
- `delete_unique_goal(id)` — Remove unique goal (requires confirmation)

**Task Tools**

- `get_today_tasks()` — Tasks scheduled for today
- `get_week_tasks(week_start?)` — Tasks for a given week
- `create_task(...)` — Add task instance
- `update_task(id, ...)` — Modify task
- `delete_task(id)` — Remove task (requires confirmation)
- `complete_task(id)` — Mark task as done
- `skip_task(id)` — Mark task as skipped

**Calendar Tools** *(Phase 4+)*

- `get_calendar_events(start_date, end_date)` — Read events
- `create_calendar_event(title, start, end, notes)` — Add event
- `update_calendar_event(event_id, ...)` — Modify event
- `delete_calendar_event(event_id)` — Remove event

### 5.3 Agent Skills

Skills are multi-step workflows the agent can execute. Based on [Anthropic's agent skills pattern](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills).

**V1 Approach:**
- All skills live in a single, clearly structured system prompt
- No dynamic skill loading or separate skill modules
- Skill functionality will not be implemented until agent evals are in place
- Keep it simple: one prompt, well-organized sections

**Planning Skill**

- User-initiated (`"let's plan"`)
- Agent walks through: calendar → recurring goals → unique goals → conflicts → finalize

**Review Skill**

- User-initiated (`"let's review"`)
- Agent walks through: today's tasks → completions → learnings → new tasks → preview tomorrow

**Weekly Summary Skill**

- Aggregates task completion data into weekly_review record
- No daily reviews stored — derived from task_instance data

---

## 6. User Interface

### 6.1 Terminal Chat (CLI)

**Purpose:** Primary and only interaction point for agent conversations

**Features:**

- Simple chat loop (input/print)
- Conversation with agent
- User-initiated workflows via natural language

**Technology:** Basic Python input/print. Keep minimal. Iterate from there.

**Developer Access:** Swagger UI available at `/docs` for API inspection and manual testing.

**Validation:** All functionality verified through testing + agent evals. No UI required.

---

## 7. Apple Calendar Integration

> **Phase 4+ — Not in initial scope**

**Protocol:** CalDAV (native macOS calendar protocol)

**Approach:**

- Use `caldav` Python library
- Calendar = source of truth
- 1 task = 1 calendar event
- Configurable calendar name

**Scope:**

- Read events from configured calendar
- Create events with task metadata
- Update event times
- Delete events

**Design decision:** Build internal ecosystem first. User modifies calendar manually initially. Agent calendar write access comes later.

---

## 8. Observability

**LLM Observability (LangWatch):**

- Trace LLM calls from agent
- Track token usage and cost
- Log tool call sequences
- Agent evals for quality validation

**App Observability (Python logging):**

- Basic structured logging
- Request/response logs
- Error tracking
- Upgrade to more complex solution if needed later

---

## 9. Development Phases

### Phase 1: Foundation

**1.1 Project Setup**

- [ ] Git repository initialization
- [ ] UV project setup
- [ ] Directory structure
- [ ] Docker Compose for Postgres
- [ ] Environment configuration (.env)
- [ ] Basic logging setup

**1.2 Data Model**

- [ ] Pydantic models for all entities
- [ ] SQLAlchemy models
- [ ] Alembic migrations setup
- [ ] Initial migration (all tables)
- [ ] Seed data script (import from markdown files)

**1.3 CRUD API**

- [ ] FastAPI app skeleton
- [ ] PMS endpoints (categories, statements)
- [ ] Role endpoints
- [ ] Goal endpoints (recurring, unique)
- [ ] Task endpoints
- [ ] Weekly review endpoints
- [ ] Swagger docs (auto-generated)

### Phase 2: Agent + CLI

**2.1 Agent Core**

- [ ] Pydantic AI setup
- [ ] LLM adapter pattern implementation
- [ ] LangWatch integration
- [ ] Tool definitions (all CRUD tools)

**2.2 Terminal Interface**

- [ ] Simple chat loop
- [ ] Agent invocation
- [ ] Response display

**2.3 Evals + Testing**

- [ ] Unit tests for API endpoints
- [ ] Integration tests for agent tools
- [ ] Agent eval framework setup (LangWatch)
- [ ] Baseline eval suite

**2.4 Skills** *(after evals in place)*

- [ ] Planning skill (single prompt)
- [ ] Review skill (single prompt)
- [ ] Weekly summary skill

**2.5 Agent Polish**

- [ ] Confirmation flow for deletes
- [ ] Error handling
- [ ] Conversation memory (session-based)

### Phase 3+: Future

- [ ] Apple Calendar integration (CalDAV)
- [ ] TTS/STT voice interface
- [ ] Accountability triggers
- [ ] Push notifications
- [ ] Mobile access consideration

---

## 10. Decisions Made

| Question                    | Decision                                        |
| --------------------------- | ----------------------------------------------- |
| UI approach                 | CLI/Agent-only, no web UI                       |
| Skills v1                   | Single prompt, no dynamic loading               |
| Skills implementation       | After evals are in place                        |
| Session state               | Session-based memory                            |
| Calendar as SSOT            | Yes, calendar is source of truth                |
| Multi-device                | Desktop (macOS) only for now                    |
| Task ↔ Calendar            | 1:1 relationship                                |
| Time tracking               | No actual time tracking, just completion status |
| Adhoc tasks                 | Can be role-less (nullable role_id)             |
| Daily reviews               | Not stored; weekly derived from tasks           |
| Workflow triggers           | User-initiated only                             |
| Conversation style          | Efficient, direct, action-oriented              |
| Calendar name               | Configurable                                    |
| Delete protection           | All deletes require user confirmation           |
| Calendar integration timing | Phase 3+ (after agent)                          |
| Validation approach         | Testing + agent evals, no UI verification       |
