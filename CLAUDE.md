# max-ai Project Rules

## Before every commit
Run the following checks before committing. All must pass:

```
make lint        # ruff check + format check
make typecheck   # mypy
make test        # pytest
```

`make lint-fix` auto-fixes most lint/format issues. Pre-commit hooks (`.pre-commit-config.yaml`) also enforce ruff and mypy on every `git commit` automatically — install them once via `make dev`.

## Development workflow

### Bug fix
1. **Always use a git worktree** — run `make worktree NAME=fix/<short-description>` (e.g. `make worktree NAME=fix/handle-empty-voice-input`). Open Claude Code inside the new worktree directory.
2. Fix the bug and add a regression test
3. Open a PR titled `FIX: <short description>` — no issue required

### Feature
1. Create a GitHub issue titled `FEAT: <short description>` using the feature template (`.github/issue_template.md`) — include a full spec and acceptance criteria
2. **Always use a git worktree** — run `make worktree NAME=feat/<short-description>` (e.g. `make worktree NAME=feat/spotify-queue-management`). This creates an isolated working directory so multiple features can be developed in parallel without branch conflicts. Never implement a feature directly in the main checkout.
3. Open Claude Code inside the new worktree directory (`cd ../<repo>-<name>`).
4. Implement, then open a PR titled `FEAT: <short description>` that closes the issue (`closes #<number>`)

### Branch naming
Branches must follow the pattern `<prefix>/<description>` where prefix is one of: `feat`, `fix`, `opt`, `ref`.
Issues and PR titles use the uppercase form: `FEAT:`, `FIX:`, `OPT:`, `REF:`.
CI enforces the branch pattern. Direct pushes to `main` are blocked — all changes must go through a PR with passing CI.

### After every change
Always push and open a PR when work is complete. No exceptions.

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

## Lazy imports inside functions (intentional pattern)
Some imports are deliberately placed inside functions rather than at the top of the file. Do not move these to module level. Valid reasons:

- **Optional dependency not guaranteed to be installed** — guarded by `try/except ImportError` (e.g. `import langwatch` in `monitoring/langwatch.py`).
- **Platform-specific module** — would raise `ImportError` on unsupported platforms at module load time (e.g. `import termios`, `import tty` in `voice/loop.py` — Unix only).
- **Optional feature with its own deps** — e.g. `from max_ai.tools.spotify import _get_spotify` and voice modules (`tts`, `recorder`, `stt`) in `voice/loop.py`; importing them at module level would fail when the feature's extras are not installed.

When reviewing code, treat an import inside a function as intentional if it falls into one of these categories.

## Running tests
Dev dependencies (pytest, ruff, mypy) are optional extras and not installed by `uv sync` alone. `make test` handles this automatically via `uv sync --extra dev`. If running pytest directly, install them first with `uv sync --extra dev`, then use `uv run python -m pytest tests/ -v`.

## Testing requirements
- Every new feature must include tests covering its core behaviour.
- Every bug fix must include a test that would have caught the bug.
- When modifying existing code, check whether existing tests are affected and update them.
- Tests must not hit real external services (use mocks or in-memory SQLite).
- Every `MagicMock` construction must be cast to the actual type being mocked: `name = cast(ActualType, MagicMock(spec=ActualType))`. Never use bare `MagicMock()` or leave the inferred type as `MagicMock`. Fixture return types must also reflect the real type (e.g. `-> anthropic.AsyncAnthropic`). Two narrow exceptions require suppression comments:
  - Read-only properties on the real type: `# type: ignore[misc]`
  - Method-attribute replacement: `# type: ignore[method-assign]`
  - Invalid-enum test values: `# type: ignore[assignment]`
- `pytest.mark.asyncio` must never appear in test files. `asyncio_mode = "auto"` is configured, so it is redundant — but it also triggers a cascade of pre-commit failures: the decorator causes `[misc]` (untyped decorator), which makes mypy treat the whole function as untyped and skip checking its body, which makes any `# type: ignore[method-assign]` inside the body "unused", which triggers `[unused-ignore]`. **If you find `@pytest.mark.asyncio` in existing code while touching a test file, remove it immediately** — leaving it will cause the pre-commit hook to fail on your commit even if you didn't add it.
- `pytest.mark.parametrize` IS an untyped decorator; add `# type: ignore[misc]` to the decorated function. The `[[tool.mypy.overrides]]` in pyproject.toml disables `unused-ignore` for `tests.*`, which prevents conflicts between the pre-commit hook (which sees [misc]) and the full cached run (which does not).
