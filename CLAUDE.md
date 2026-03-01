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

## Third-party libraries without type stubs
When adding a dependency that has no type stubs or `py.typed` marker, mypy (strict mode) will raise `import-untyped`. Fix by adding a `[[tool.mypy.overrides]]` block in `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = ["some_lib", "some_lib.*"]
ignore_missing_imports = true
```

If a library has a packaging bug that causes mypy to fail (e.g. duplicate `__init__.py` files), use `follow_imports = "skip"` instead:

```toml
[[tool.mypy.overrides]]
module = ["bad_lib", "bad_lib.*"]
follow_imports = "skip"
```

Current untyped libraries in this project: `spotipy`, `soundfile`, `sounddevice`, `noisereduce` (→ `ignore_missing_imports`) and `langwatch` (→ `follow_imports = "skip"`). Add any new ones here.

Also apply this principle broadly: whenever you encounter a project-specific recurring issue (tooling quirks, env setup, architectural constraints), add a note to CLAUDE.md so it doesn't need to be debugged again.

## Naming conventions
Variable, parameter, and attribute names must be fully spelled out — never abbreviated. Examples of what is **not allowed**:
- `defn` → use `definition`
- `buf` → use `buffer` or a descriptive name like `wav_buffer`
- `idx` → use `index` or a descriptive name like `position`
- `cfg` / `conf` → use `config` or `configuration`
- `msg` → use `message`
- `resp` → use `response`
- `req` → use `request`
- `conv` → use `conversation`
- `ctx` → use `context`
- `cb` / `_cb` → use a descriptive name like `_on_key_press` or `_on_complete`
- `fn` / `func` → use `function` or a descriptive name
- `err` → use `error` or `exception`
- `tmp` → use `temporary` or a descriptive name
- `num` → use `count` or a descriptive name

Single-letter names (`n`, `i`, `x`, `y`) are acceptable only in tight mathematical or NumPy signal-processing loops where they are conventional.

## Running tests
Dev dependencies (pytest, ruff, mypy) are optional extras and not installed by `uv sync` alone. `make test` handles this automatically via `uv sync --extra dev`. If running pytest directly, install them first with `uv sync --extra dev`, then use `uv run python -m pytest tests/ -v`.

## Testing requirements
- Every new feature must include tests covering its core behaviour.
- Every bug fix must include a test that would have caught the bug.
- When modifying existing code, check whether existing tests are affected and update them.
- Tests must not hit real external services (use mocks or in-memory SQLite).
