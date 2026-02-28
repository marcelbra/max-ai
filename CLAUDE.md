# max-ai Project Rules

## After every feature
Always commit and push to remote when a feature or fix is complete. No exceptions.

## Database
In development mode, tables are created via `create_all` (no Alembic migrations needed). Only use Alembic for production deployments.
