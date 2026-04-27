# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

All core rules live in [AGENTS.md](AGENTS.md). This file extends them with Claude Code-specific behavior.

---

## Commands

```bash
# Run app
streamlit run app.py

# Run all tests
python -m pytest tests/test_pawpal.py -v

# Run a single test
python -m pytest tests/test_pawpal.py::TestClassName::test_method_name -v

# Install dependencies
pip install -r requirements.txt
```

---

## Architecture

**Six core classes** in `pawpal_system.py` (logic layer — zero I/O):

| Class | Responsibility |
|-------|---------------|
| `Task` | Data model + recurrence metadata |
| `Pet` | Pet info + owns list of Tasks |
| `ScheduledSlot` | Task pinned to start/end minute window |
| `Schedule` | Immutable scheduling result container |
| `Scheduler` | Greedy knapsack algorithm + static utilities |
| `Owner` | Root coordinator; depends on Scheduler via injection |

`app.py` = Streamlit UI only. `pawpal_system.py` = all logic. New features → new module files.

---

## Coding Rules

- All function params and return types must have type hints
- Every public method and class requires a docstring
- SOLID strictly: do not violate SRP, OCP, LSP, ISP, DIP
- DRY: extract repeated logic to shared methods
- No inline comments — use self-documenting names

---

## Testing Rules

- TDD: write failing test first, then implement
- No mocks of `pawpal_system.py` classes — hit real objects
- Every feature needs happy path + edge case (zero/empty/boundary)
- UI logic is also tested
- pytest only; test files in `tests/`

---

## Commit Rules

- Conventional Commits: `feat:`, `fix:`, `test:`, `refactor:`, `docs:`
- One concern per commit
- Reference the task/feature in commit body
- Never commit broken code

---

## Hard Limits (ask user first)

- Adding packages to `requirements.txt`
- Adding persistence / file I/O / database
- Changing fields on `Task`, `Pet`, `Owner`, `Schedule`, `ScheduledSlot`
- Refactoring working code outside current task scope

---

## Self-Maintenance

If a rule here becomes outdated or causes issues, **update this file and `AGENTS.md`, `.github/copilot-instructions.md`, `.cursor/rules/pawpal.mdc`** to keep all agent configs in sync.
