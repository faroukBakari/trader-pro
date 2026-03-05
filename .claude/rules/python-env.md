---
paths: ["backend/**", "scripts/**", "smoke-tests/**", "*.mk", "Makefile"]
---

# Python Environment: Poetry (Project Override)

This project uses **Poetry** for Python dependency management. The user-level `uv-python-isolation` rule does NOT apply here. Do not suggest or attempt migration to uv.

## Why this override exists

The entire backend toolchain — Makefiles, CI workflows, dev scripts, pre-commit hooks — assumes `poetry run`, `poetry install`, and `poetry.lock`. Converting to uv would require rewriting all of these. Poetry is the project's native package manager and the only supported one.

## Commands

| Task | Command |
|------|---------|
| Install deps | `cd backend && poetry install` |
| Run a script | `cd backend && poetry run python script.py` |
| Run tests | `make -C backend test` (wraps `poetry run pytest`) |
| Add a dependency | `cd backend && poetry add <pkg>` |
| Add a dev dependency | `cd backend && poetry add --group dev <pkg>` |
| Run any Python tool | `cd backend && poetry run <tool>` |

## Constraints

- **Never `uv add`, `uv run`, `uv pip install`** inside the backend or any Python path in this project.
- **Never `pip install` or bare `python`** — always `poetry run` or a Makefile target.
- **Never modify `pyproject.toml` [build-system]** — it must remain `poetry.core.masonry.api`.
- **`poetry.lock` is committed** — never delete or regenerate without cause. Use `poetry lock --no-update` to refresh metadata only.
- Makefile targets are the preferred entry point. Use `poetry run` only when no Makefile target exists for the task.

## What uv IS still used for

uv may still be used for **out-of-project** tooling that is not part of the trader-pro backend:
- One-off CLI tools: `uvx ruff check .`, `uvx black .` (only if not already available via `poetry run`)
- Standalone scripts or services in `user-ia/services/` (those are uv-managed per user rules)

The boundary is clear: **inside this repo's Python paths → Poetry. Outside → uv.**
