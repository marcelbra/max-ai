# max-ai Project Rules

## Before every commit
Run the following checks before committing. All must pass:

```
make lint        # ruff check + format check
make typecheck   # mypy
make test        # pytest
```

`make lint-fix` auto-fixes most lint/format issues. Pre-commit hooks (`.pre-commit-config.yaml`) also enforce ruff and mypy on every `git commit` automatically — install them once via `make dev`.

## After every feature
Always commit and push to remote when a feature or fix is complete. No exceptions.

## Database
In development mode, tables are created via `create_all` (no Alembic migrations needed). Only use Alembic for production deployments.

## Running tests
Dev dependencies (pytest, ruff, mypy) are optional extras and not installed by `uv sync` alone. `make test` handles this automatically via `uv sync --extra dev`. If running pytest directly, install them first with `uv sync --extra dev`, then use `uv run python -m pytest tests/ -v`.
