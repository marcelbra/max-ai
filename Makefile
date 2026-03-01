.PHONY: install dev lint lint-fix typecheck test voice voice-dev migrate migration setup-spotify setup-calendar clean

install:                    ## Install dependencies
	uv sync

dev:                        ## Install with dev dependencies
	uv sync --all-extras
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push

lint:                       ## Run ruff linter + formatter check
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

lint-fix:                   ## Auto-fix lint issues
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

typecheck:                  ## Run mypy
	uv run mypy

test:                       ## Run tests
	uv sync --extra dev
	uv run python -m pytest tests/ -v

voice:                      ## Start the voice agent (STT → Agent → TTS)
	uv run max-ai

voice-dev:                  ## Dev tool: record, denoise, save raw + denoised WAVs
	uv run python scripts/voice_dev.py

migrate:                    ## Run database migrations
	uv run alembic upgrade head

migration:                  ## Generate new migration from model changes
	uv run alembic revision --autogenerate -m "$(msg)"

setup-spotify:              ## Run Spotify OAuth setup
	uv run python scripts/setup_spotify.py

setup-calendar:             ## Grant macOS Calendar access (one-time)
	uv run python scripts/setup_calendar.py

clean:                      ## Remove build artifacts
	rm -rf .mypy_cache .pytest_cache .ruff_cache __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +
