---
paths: ["frontend/**", "smoke-tests/**", "scripts/**", ".githooks/**"]
---

# Node Environment: npm + nvm (Project Override)

This project uses **npm** for package management and **nvm** for Node version management. The user-level `node-isolation` rule does NOT apply here. Do not suggest or attempt migration to pnpm/fnm.

## Why this override exists

The entire frontend toolchain — Makefiles, CI workflows, generation scripts, git hooks, smoke tests — assumes `npm install`, `npm run`, and `package-lock.json`. Converting to pnpm would require rewriting ~15 files with no functional benefit. npm is the project's native package manager and the only supported one.

## fnm compatibility

fnm reads `.nvmrc` natively, so fnm-managed environments work transparently. The Makefile skips `nvm use` when Node is already the correct version. Both version managers are compatible with this project — references to "nvm" in scripts and docs are kept as-is.

## Commands

| Task | Command |
|------|---------|
| Install deps | `cd frontend && npm install` |
| Run dev server | `make -C frontend dev` or `make -f project.mk dev-frontend` |
| Run tests | `make -C frontend test` (wraps `npm run test`) |
| Run type check | `make -C frontend type-check` |
| Add a dependency | `cd frontend && npm install <pkg>` |
| Add a dev dependency | `cd frontend && npm install -D <pkg>` |
| One-off tool | `npx <tool>` (or Makefile target when available) |

## Constraints

- **Never `pnpm add`, `pnpm install`, `pnpm dlx`** inside this repo.
- **Never delete `package-lock.json`** in favor of `pnpm-lock.yaml`.
- **Never `yarn`** — npm is the only supported package manager.
- **Makefile targets are the preferred entry point.** Use `npm run` only when no Makefile target exists for the task.
- **`.nvmrc` is committed** — never delete or replace with `.node-version` unless both are kept in sync.

## Boundary

- **Inside this repo** (frontend, smoke-tests, scripts, .githooks) → npm + nvm refs.
- **Outside this repo** (user-ia services, standalone tools) → pnpm + fnm per user-level rules.
