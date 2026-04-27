# AGENTS.md

Master rules for all AI agents working in this repository (Claude Code, GitHub Copilot, Cursor, OpenAI Codex). All agent-specific config files mirror these rules.

## Self-Maintenance

If any rule here causes confusion, breaks workflow, or becomes outdated during a session, **update this file and all agent config files** before continuing. When a new pattern is confirmed by the user, add it here. Keep all agent files in sync:
- `CLAUDE.md`
- `.github/copilot-instructions.md`
- `.cursor/rules/pawpal.mdc`

---

## Commands

```bash
# Run app
streamlit run app.py
# or:
make run

# Run all tests
python -m pytest tests/test_pawpal.py -v

# Run a single test
python -m pytest tests/test_pawpal.py::TestClassName::test_method_name -v

# Install dependencies
pip install -r requirements.txt
```

---

## Architecture

**Six core classes** in `pawpal_system.py` (logic layer — zero I/O, no Streamlit):

| Class | Responsibility |
|-------|---------------|
| `Task` | Data model for a single pet care activity; owns recurrence metadata |
| `Pet` | Pet info + owns a list of Tasks |
| `ScheduledSlot` | Pins a Task to a concrete start/end minute window within a day |
| `Schedule` | Immutable result container from a scheduling run |
| `Scheduler` | Greedy knapsack algorithm + static utilities (conflict detection, sorting, filtering) |
| `Owner` | Root coordinator; manages pets, tasks, schedules; depends on Scheduler via injection |

**File layout:**
```
pawpal_system.py   ← all logic (6 classes)
app.py             ← Streamlit UI only; imports from pawpal_system.py
main.py            ← CLI smoke-test/demo
tests/
  test_pawpal.py   ← 70+ tests, 8+ test classes
  conftest.py      ← sys.path setup only
```

**New feature rule:** New features go in their own module file (e.g., `ai_scheduler.py`, `notifications.py`). Do not add new classes to `pawpal_system.py` unless extending a core model. UI additions go in `app.py` or a new `ui_*.py` module.

**Key patterns to preserve:**
- `@dataclass` + `field(default_factory=...)` for dependency injection (`Owner.scheduler`)
- UUID via `uuid4()` at `__post_init__`; identity fields always named with `id` suffix
- `Owner.complete_task()` recurrence pattern — marks complete, spawns next via `timedelta`
- `Schedule` is immutable after creation — never mutate its fields
- `Scheduler` static methods (`detect_time_conflicts`, `sort_by_time`, `filter_tasks`) are pure functions; keep them stateless

---

## Coding Rules

**Type hints:** All function parameters and return types must be annotated.
```python
def add_pet(self, pet: Pet) -> None:
def get_task(self, task_id: str) -> Task | None:
```

**Docstrings:** Every public method and class requires a docstring. One-line for simple methods; multi-line for anything with non-obvious behavior.
```python
def complete_task(self, task_id: str, on_date: str) -> None:
    """Mark task complete and spawn next recurrence if applicable."""
```

**SOLID strictly:**
- S: Each class has one reason to change. Don't add unrelated responsibilities.
- O: Extend via subclassing or new modules; don't modify working classes.
- L: Scheduler subclasses must be drop-in replacements for `Scheduler`.
- I: Expose only what consumers need; avoid fat interfaces.
- D: Depend on abstractions. `Owner` depends on `Scheduler` type, not a hardcoded algorithm.

**DRY:** No repeated logic. If the same operation appears twice, extract to a shared method or static utility.

**No inline comments:** Self-documenting names are sufficient. Add a comment only for non-obvious constraints, external workarounds, or hidden invariants — not to explain what the code does.

---

## Testing Rules

**TDD:** Write the failing test first. Implement only enough to make it pass.

**No mocks of the logic layer:** Tests hit real `pawpal_system.py` classes. No `unittest.mock` on internal classes.

**Coverage requirement:** Every new feature needs:
- Happy path test
- Empty/zero/boundary edge case
- Invalid input test (if applicable)

**UI logic is also tested:** Business logic extracted from `app.py` (e.g., filtering, session state transitions) must have corresponding tests.

**pytest only.** No `unittest.TestCase`.

**Test location:** `tests/test_pawpal.py` for core logic. New modules get a matching `tests/test_<module_name>.py`.

---

## Naming Rules

- `snake_case` for all Python identifiers (variables, functions, methods, files)
- Match existing naming style in `pawpal_system.py` exactly
- UUID identity fields use `id` suffix: `pet.id`, `task.id`, `schedule.id`
- No single-letter variable names except loop indices (`i`, `j`) and comprehension targets where context is obvious

---

## UI Rules (app.py)

- All state lives in `st.session_state` — no global variables
- No hard-coded strings for labels, messages, or options — use module-level constants
- New UI sections must be consistent with existing `app.py` layout patterns

---

## Commit Rules

- **Conventional Commits format:** `feat:`, `fix:`, `test:`, `refactor:`, `docs:` prefixes required
- **One concern per commit:** Never bundle unrelated changes
- **Reference the task/feature** in the commit body or footer (e.g., `Implements: pet medication tracking`)
- Never commit broken or incomplete code

---

## Hard Limits

The following require explicit user confirmation before proceeding:

1. **Adding packages** to `requirements.txt`
2. **Adding persistence** — file I/O, database, or any form of data storage
3. **Changing data model fields** on `Task`, `Pet`, `Owner`, `Schedule`, or `ScheduledSlot`
4. **Refactoring working code** — structural changes to classes or files that aren't part of the current task

When in doubt, ask. Do not scaffold LLM/AI integration code speculatively — AI features are not planned yet.
