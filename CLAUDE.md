# max-ai Project Rules

## After every feature
Always commit and push to remote when a feature or fix is complete. No exceptions.

## Database
In development mode, tables are created via `create_all` (no Alembic migrations needed). Only use Alembic for production deployments.

## Running tests
Dev dependencies (pytest, ruff, mypy) are optional extras and not installed by `uv sync` alone. `make test` handles this automatically via `uv sync --extra dev`. If running pytest directly, install them first with `uv sync --extra dev`, then use `uv run python -m pytest tests/ -v`.
