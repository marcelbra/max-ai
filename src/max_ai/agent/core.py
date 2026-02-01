"""Core MaxAgent class with Pydantic AI integration."""

from dataclasses import dataclass

from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncSession

from max_ai.db import get_session_factory

from .llm import OpenAILLM
from .memory import ConversationMemory
from .observability import LangWatchSpan, init_langwatch
from .prompts import get_system_prompt
from .tools.goals import (
    CreateRecurringGoalInput,
    CreateUniqueGoalInput,
    DeleteRecurringGoalInput,
    DeleteUniqueGoalInput,
    UpdateRecurringGoalInput,
    UpdateUniqueGoalInput,
    create_recurring_goal,
    create_unique_goal,
    delete_recurring_goal,
    delete_unique_goal,
    list_recurring_goals,
    list_unique_goals,
    update_recurring_goal,
    update_unique_goal,
)
from .tools.pms import (
    CreatePMSCategoryInput,
    CreatePMSStatementInput,
    DeletePMSCategoryInput,
    DeletePMSStatementInput,
    UpdatePMSCategoryInput,
    UpdatePMSStatementInput,
    create_pms_category,
    create_pms_statement,
    delete_pms_category,
    delete_pms_statement,
    list_pms_categories,
    update_pms_category,
    update_pms_statement,
)
from .tools.roles import (
    CreateRoleInput,
    DeleteRoleInput,
    UpdateRoleInput,
    create_role,
    delete_role,
    list_roles,
    update_role,
)
from .tools.tasks import (
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
class AgentDeps:
    """Dependencies passed to agent tools."""

    db: AsyncSession


class MaxAgent:
    """AI-powered personal life OS agent with tool calling."""

    def __init__(self, llm: OpenAILLM | None = None):
        """Initialize the agent with an LLM adapter."""
        self.llm = llm or OpenAILLM()
        self.memory = ConversationMemory()

        # Initialize observability
        init_langwatch()

        # Create the Pydantic AI agent
        self.agent = Agent(
            model=self.llm.get_model_name(),
            system_prompt=get_system_prompt(),
            deps_type=AgentDeps,
        )

        # Register all tools
        self._register_tools()

    def _register_tools(self) -> None:
        """Register all agent tools."""
        # PMS tools
        self.agent.tool(list_pms_categories)
        self.agent.tool(create_pms_category)
        self.agent.tool(update_pms_category)
        self.agent.tool(delete_pms_category)
        self.agent.tool(create_pms_statement)
        self.agent.tool(update_pms_statement)
        self.agent.tool(delete_pms_statement)

        # Role tools
        self.agent.tool(list_roles)
        self.agent.tool(create_role)
        self.agent.tool(update_role)
        self.agent.tool(delete_role)

        # Goal tools
        self.agent.tool(list_recurring_goals)
        self.agent.tool(create_recurring_goal)
        self.agent.tool(update_recurring_goal)
        self.agent.tool(delete_recurring_goal)
        self.agent.tool(list_unique_goals)
        self.agent.tool(create_unique_goal)
        self.agent.tool(update_unique_goal)
        self.agent.tool(delete_unique_goal)

        # Task tools
        self.agent.tool(get_today_tasks)
        self.agent.tool(get_week_tasks)
        self.agent.tool(create_task)
        self.agent.tool(update_task)
        self.agent.tool(delete_task)
        self.agent.tool(complete_task)
        self.agent.tool(skip_task)

    async def chat(self, user_message: str) -> str:
        """
        Process a user message and return the agent's response.

        Args:
            user_message: The user's input message

        Returns:
            The agent's response string
        """
        # Add user message to memory
        self.memory.add_user_message(user_message)

        # Get conversation history for context
        message_history = self.memory.get_messages()[:-1]  # Exclude current message

        # Run the agent with database session
        async with LangWatchSpan("max-agent-chat"):
            session_factory = get_session_factory()
            async with session_factory() as db:
                try:
                    result = await self.agent.run(
                        user_message,
                        deps=AgentDeps(db=db),
                        message_history=message_history,
                    )

                    # Commit any database changes
                    await db.commit()

                    # Extract response text
                    response = result.output

                    # Add assistant response to memory
                    self.memory.add_assistant_message(response)

                    return response

                except Exception as e:
                    await db.rollback()
                    error_msg = f"I encountered an error: {str(e)}"
                    self.memory.add_assistant_message(error_msg)
                    return error_msg

    def clear_memory(self) -> None:
        """Clear the conversation history."""
        self.memory.clear()

    def get_memory(self) -> ConversationMemory:
        """Get the conversation memory."""
        return self.memory
