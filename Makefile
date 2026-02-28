.PHONY: install dev lint lint-fix typecheck test run voice migrate migration setup-spotify clean

install:                    ## Install dependencies
	uv sync

dev:                        ## Install with dev dependencies
	uv sync --all-extras
	uv run pre-commit install

lint:                       ## Run ruff linter + formatter check
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

lint-fix:                   ## Auto-fix lint issues
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

typecheck:                  ## Run mypy
	uv run mypy src/

test:                       ## Run tests
	uv run pytest tests/ -v

run:                        ## Start the CLI agent
	uv run python -m max_ai

voice:                      ## Start the voice agent (STT → Agent → TTS)
	uv run max-ai-voice

migrate:                    ## Run database migrations
	uv run alembic upgrade head

migration:                  ## Generate new migration from model changes
	uv run alembic revision --autogenerate -m "$(msg)"

setup-spotify:              ## Run Spotify OAuth setup
	uv run python scripts/setup_spotify.py

clean:                      ## Remove build artifacts
	rm -rf .mypy_cache .pytest_cache .ruff_cache __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +
