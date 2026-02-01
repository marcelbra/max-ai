.PHONY: help install dev db-start db-stop db-create migrate seed run chat test lint clean

# Default target
help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make dev        - Install with dev dependencies"
	@echo "  make db-start   - Start PostgreSQL"
	@echo "  make db-stop    - Stop PostgreSQL"
	@echo "  make db-create  - Create database"
	@echo "  make migrate    - Run database migrations"
	@echo "  make seed       - Seed database with sample data"
	@echo "  make run        - Start the API server"
	@echo "  make chat       - Start the AI chat CLI"
	@echo "  make test       - Run tests"
	@echo "  make clean      - Clean up generated files"

# Dependencies
install:
	uv sync

dev:
	uv sync --extra dev

# Database
db-start:
	brew services start postgresql@16

db-stop:
	brew services stop postgresql@16

db-create:
	/opt/homebrew/opt/postgresql@16/bin/createdb maxai || true

migrate:
	uv run alembic upgrade head

seed:
	uv run python scripts/seed.py

# Application
run:
	uv run python main.py

chat:
	uv run max-ai

# Testing
test:
	uv run pytest

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov

# Combined commands
setup: install db-start db-create migrate seed
	@echo "Setup complete! Run 'make run' to start the server."
