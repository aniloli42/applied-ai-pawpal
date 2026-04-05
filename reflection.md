# PawPal+ Project Reflection

## 1. System Design
User can able to add pet
User can able to add tasks
User can able to see schedule of today
User can able to edit pet
User can able to edit tasks
User can able to delete pet
User can able to delete tasks

**a. Initial design**

- Briefly describe your initial UML design.
  - The initial UML design includes four classes: `Owner`, `Pet`, `Task`, and `Schedule`. An `Owner` holds a daily time budget and a list of pets. Each `Pet` holds a list of care `Task` objects. The `Schedule` class takes an owner and a pet, selects tasks that fit within the owner's time budget (sorted by priority), and stores both the chosen tasks and the ones that were skipped.

- What classes did you include, and what responsibilities did you assign to each?
  - **Owner** — stores owner info and daily available time; manages a list of pets.
  - **Pet** — stores pet info and manages a list of care tasks.
  - **Task** — represents a single care activity with a title, duration, priority, and category.
  - **Schedule** — acts as the planner; reads the owner's time budget, selects and orders tasks by priority, and explains why tasks were included or skipped.

**b. Design changes**

- Did your design change during implementation?
    - Yes
- If yes, describe at least one change and why you made it.
    - **Added unique IDs to every object.** The initial design had no `id` field on any class. Without IDs, removing or looking up a specific pet or task by name would cause conflicts when two objects share the same name (e.g. two pets named "Max"). Adding a UUID to each class solved this cleanly.
    - **Added get-by-ID methods to every class.** Once we had IDs, we needed a way to retrieve a specific entry without scanning everything manually. Each class now has a `get_pet(pet_id)`, `get_task(task_id)`, etc. method so lookups are consistent and encapsulated.
    - **Added foreign key reference IDs.** `Pet` stores `pet_id`, `Task` stores `pet_id`, and `Schedule` stores `pet_id`. This lets each object know which parent it belongs to without holding a full object reference, making serialization and lookups simpler.
    - **Moved task creation to Owner, not Pet.** Originally the design had task management methods on `Pet`. But since tasks must be created with the correct `pet_id` set, it made more sense for `Owner` to be the factory — it knows which pets it has, so it can set the FK correctly and then delegate storage to `Pet.add_task()`.
    - **Extracted a Scheduler class (SOLID — SRP + OCP).** The original `Schedule` class was responsible for both storing the result and running the scheduling algorithm. This violates the Single Responsibility Principle. We extracted a separate `Scheduler` class whose only job is to run the algorithm and return a `Schedule`. This also makes it easy to swap in a different scheduling strategy later without touching `Schedule` at all.
    - **Schedule became a pure result container.** After extracting `Scheduler`, `Schedule` no longer has `generate()` or `available_tasks` as inputs. It only stores the output (scheduled tasks, skipped tasks, total duration) and provides `explain()` and `to_dict()`. This makes it clean and focused.


---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
  - The conflict detection strategy currently only checks for **exact time matches** (e.g., two tasks both independently tagged "14:00") instead of computing true overlapping duration intervals (e.g., a 60-minute task starting at "14:00" overlapping with another task at "14:30").
- Why is that tradeoff reasonable for this scenario?
  - It is reasonable for our lightweight minimum viable product (MVP): checking for exact string matches (`O(N)` dictionary grouping) is significantly simpler and faster than importing heavy timestamp libraries to evaluate continuous minute-by-minute range intersections. For everyday pet scheduling, most accidental double-bookings happen when a user accidentally assigns the exact same starting hour twice, prioritizing performance and code readability over stringent calendar rules.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
