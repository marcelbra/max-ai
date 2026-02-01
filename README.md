# Max AI

Personal Life OS with AI-Powered Accountability.

## Features

- Personal Mission Statement (PMS) management
- Role-based life organization
- Recurring and unique goal tracking
- Task scheduling and review
- AI-powered chat interface for natural language interaction

## Quick Start

```bash
# Install dependencies
make dev

# Start database
make db-start
make db-create
make migrate

# Run the AI chat
make chat

# Or run the API server
make run
```

## CLI Usage

Start the AI chat interface:

```bash
make chat
# or
uv run max-ai
```

Commands:
- `exit` / `quit` - Exit the chat
- `clear` - Clear conversation history

## Development

```bash
# Run tests
make test

# Run API server
make run
```
