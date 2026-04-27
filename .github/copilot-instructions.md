# GitHub Copilot Instructions — PawPal+

All core rules live in [AGENTS.md](../AGENTS.md). This file mirrors them for Copilot.

## Stack

Python 3.11+, Streamlit, pytest. No TypeScript, no Node.

## Architecture

- `pawpal_system.py` — all business logic (6 dataclasses: Task, Pet, ScheduledSlot, Schedule, Scheduler, Owner)
- `app.py` — Streamlit UI only; imports from `pawpal_system.py`
- `tests/test_pawpal.py` — 70+ pytest tests

New features go in their own module file. Do not add classes to `pawpal_system.py` unless extending a core model.

## Coding Rules

- Type hints on all params and return types
- Docstring on every public method and class
- SOLID strictly — no violations
- DRY — extract repeated logic
- No inline comments

## Testing Rules

- TDD: failing test first
- No mocks of `pawpal_system.py` — use real objects
- Every feature: happy path + edge cases
- pytest only

## Commit Rules

- Conventional Commits: `feat:`, `fix:`, `test:`, `refactor:`, `docs:`
- One concern per commit
- Reference task in commit body

## Hard Limits (ask user before doing)

- Adding packages to `requirements.txt`
- Adding file I/O / database / persistence
- Changing fields on Task, Pet, Owner, Schedule, ScheduledSlot
- Refactoring working code outside current task

## Self-Maintenance

If a rule becomes outdated, update this file **and** `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/pawpal.mdc`.
