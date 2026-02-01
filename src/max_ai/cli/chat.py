"""CLI chat interface for Max AI."""

import asyncio
import logging
import sys

from dotenv import load_dotenv

# Load .env before importing agent (which needs OPENAI_API_KEY)
load_dotenv()

# Suppress noisy loggers for clean CLI output
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

from max_ai.agent import MaxAgent


def print_welcome() -> None:
    """Print welcome message."""
    print("\n" + "=" * 60)
    print("  Max AI - Your Personal Life Operating System")
    print("=" * 60)
    print("\nHi! I'm Max, your AI assistant for managing your life system.")
    print("I can help you with:")
    print("  - Managing your Personal Mission Statement (PMS)")
    print("  - Organizing roles and goals")
    print("  - Planning and reviewing your tasks")
    print("\nCommands:")
    print("  'exit' or 'quit' - Exit the chat")
    print("  'clear' - Clear conversation history")
    print("\n" + "-" * 60 + "\n")


async def chat_loop() -> None:
    """Main chat loop."""
    print_welcome()

    agent = MaxAgent()

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            # Handle empty input
            if not user_input:
                continue

            # Handle exit commands
            if user_input.lower() in ("exit", "quit", "q"):
                print("\nGoodbye! Keep living intentionally.\n")
                break

            # Handle clear command
            if user_input.lower() == "clear":
                agent.clear_memory()
                print("\n[Conversation cleared]\n")
                continue

            # Get agent response
            print("\nMax: ", end="", flush=True)
            response = await agent.chat(user_input)
            print(response)
            print()

        except KeyboardInterrupt:
            print("\n\nGoodbye! Keep living intentionally.\n")
            break
        except EOFError:
            print("\n\nGoodbye! Keep living intentionally.\n")
            break


def main() -> None:
    """Entry point for the CLI."""
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        print("\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
