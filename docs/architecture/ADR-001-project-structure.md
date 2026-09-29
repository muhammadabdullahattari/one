# ADR-001: Project Structure and Package Management

**Date:** 2026-09-24
**Status:** Accepted
**Deciders:** Project Lead

## Context

The project requires a deterministic, reproducible Python environment for a production-grade distributed task engine. The package manager and project layout must support the full stack: API, worker, scheduler, SDK, and CLI — all from one repository.

## Decision

- **uv** is the package manager (SRS §23: "uv approach — deterministic Python dependency management").
- `pyproject.toml` is the single source of truth for all dependencies.
- `uv.lock` is committed to version control for reproducible installs.
- The project uses `src/` layout to prevent accidental imports from the working directory.
- All subsystems (`broker`, `worker`, `scheduler`, `retry`, `rate_limit`, etc.) are separate Python packages under `src/` with their own `__init__.py`.

## Consequences

- `uv sync --frozen` on CI ensures byte-identical environments across machines.
- The `src/` layout means `import src.domain.task` — explicit and unambiguous.
- Adding a new subsystem requires: create directory + `__init__.py`, no changes to `pyproject.toml` unless new external deps are needed.
