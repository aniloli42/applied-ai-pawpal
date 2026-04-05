"""
pawpal_system.py
Logic layer for PawPal+ — pet care planning assistant.

Owner is the root of the application. There is no PawPal wrapper class.
The Streamlit app.py will create one Owner instance and work with it directly.

SOLID design:
  S — Task/Pet = data models; Scheduler = algorithm; Schedule = result; Owner = root
  O — Scheduler can be subclassed for new strategies without modifying Schedule
  L — Any Scheduler subclass can replace the default in Owner
  I — Each class exposes only what its consumers need
  D — Owner depends on Scheduler abstraction, not a hardcoded algorithm

Classes:
    Task          — a single pet care activity (data + recurrence logic)
    Pet           — a pet and its task list
    ScheduledSlot — a task pinned to a concrete time window within a Schedule
    Schedule      — immutable result of a scheduling run (data + explain)
    Scheduler     — scheduling algorithm (sort, filter, conflict detection)
    Owner         — root app user; manages pets, tasks, and schedules
"""

import uuid
from dataclasses import dataclass, field
from datetime import date as date_type, datetime
from typing import ClassVar, Optional


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """Represents a single pet care activity, including recurrence metadata."""

    VALID_PRIORITIES:  ClassVar[set] = {"low", "medium", "high"}
    VALID_CATEGORIES:  ClassVar[set] = {"walk", "feeding", "meds", "grooming", "enrichment", "other"}
    VALID_STATUSES:    ClassVar[set] = {"pending", "in_progress", "completed"}
    VALID_RECURRENCES: ClassVar[set] = {"none", "daily", "weekly", "weekdays"}
    VALID_TIME_SLOTS:  ClassVar[set] = {"any", "morning", "afternoon", "evening"}

    pet_id:             str
    title:              str
    duration_minutes:   int
    priority:           str           = "medium"
    category:           str           = "other"
    time:               str           = "00:00"      # HH:MM format
    notes:              str           = ""
    status:             str           = "pending"
    # --- recurrence ---
    recurrence:         str           = "none"   # none | daily | weekdays | weekly
    preferred_time_slot: str          = "any"    # any | morning | afternoon | evening
    due_date:           Optional[str] = None     # New due date to use for recurrence
    id: str = field(default_factory=lambda: str(uuid.uuid4()), init=False)

    # ------------------------------------------------------------------ #
    # Query helpers                                                        #
    # ------------------------------------------------------------------ #

    def is_high_priority(self) -> bool:
        """Returns True if the task priority is 'high'."""
        return self.priority == "high"

    def is_due(self, date: str) -> bool:
        """Returns True if this task should appear in a schedule for *date*."""
        if self.status == "completed":
            return False
        if self.due_date:
            return date >= self.due_date
        return True

    # ------------------------------------------------------------------ #
    # Mutations                                                            #
    # ------------------------------------------------------------------ #

    def set_status(self, status: str, on_date: Optional[str] = None) -> None:
        """Updates the task status."""
        if status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {self.VALID_STATUSES}"
            )
        self.status = status

    def mark_complete(self, on_date: Optional[str] = None) -> None:
        """Marks the task as completed. Shortcut for set_status('completed')."""
        self.set_status("completed", on_date=on_date)

    # ------------------------------------------------------------------ #
    # Serialisation                                                        #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict:
        """Serializes the task to a plain dictionary."""
        return {
            "id":                  self.id,
            "pet_id":              self.pet_id,
            "title":               self.title,
            "duration_minutes":    self.duration_minutes,
            "priority":            self.priority,
            "category":            self.category,
            "time":                self.time,
            "notes":               self.notes,
            "status":              self.status,
            "recurrence":          self.recurrence,
            "preferred_time_slot": self.preferred_time_slot,
            "due_date":            self.due_date,
        }


# ---------------------------------------------------------------------------
# Pet
# ---------------------------------------------------------------------------

@dataclass
class Pet:
    """Represents a pet with a list of care tasks.

    Responsibility: manage its own task list.
    """

    name:    str
    species: str
    breed:   str = ""
    age:     int = 0
    tasks:   list["Task"] = field(default_factory=list)
    id:      str = field(default_factory=lambda: str(uuid.uuid4()), init=False)

    def add_task(self, task: "Task") -> None:
        """Appends a task to this pet's list.

        Raises:
            ValueError: if task.pet_id does not match this pet's id.
        """
        if task.pet_id != self.id:
            raise ValueError(
                f"Task '{task.title}' belongs to pet '{task.pet_id}', "
                f"not to this pet '{self.id}'."
            )
        self.tasks.append(task)

    def remove_task(self, task_id: str) -> None:
        """Removes a task by its unique ID. Silently ignores unknown IDs."""
        self.tasks = [t for t in self.tasks if t.id != task_id]

    def get_tasks(self) -> list["Task"]:
        """Returns all tasks assigned to this pet."""
        return list(self.tasks)

    def get_task(self, task_id: str) -> Optional["Task"]:
        """Returns a specific task by ID, or None if not found."""
        return next((t for t in self.tasks if t.id == task_id), None)


# ---------------------------------------------------------------------------
# ScheduledSlot  (a task pinned to a concrete time window inside a Schedule)
# ---------------------------------------------------------------------------

@dataclass
class ScheduledSlot:
    """Associates a Task with a start/end offset (in minutes) within a day.

    ``start_minute`` and ``end_minute`` are offsets from the start of the
    scheduling window (0 = first minute of the owner's available time).
    """

    task:         Task
    start_minute: int
    end_minute:   int

    def time_label(self, start_hour: int = 8) -> str:
        """Returns a human-readable HH:MM–HH:MM label for this slot."""
        def fmt(m: int) -> str:
            total_m = (start_hour * 60) + m
            return f"{(total_m // 60) % 24:02d}:{total_m % 60:02d}"
        return f"{fmt(self.start_minute)}–{fmt(self.end_minute)}"

    def to_dict(self, start_hour: int = 8) -> dict:
        return {
            "task_id":    self.task.id,
            "task_title": self.task.title,
            "start_minute": self.start_minute,
            "end_minute":   self.end_minute,
            "time_label":   self.time_label(start_hour),
        }


# ---------------------------------------------------------------------------
# Schedule  (result data container — SRP: stores and explains, nothing more)
# ---------------------------------------------------------------------------

@dataclass
class Schedule:
    """Immutable result of a scheduling run for one pet.

    Responsibility: store the result and explain it.
    Does NOT generate itself — that is Scheduler's job (SRP + OCP).
    """

    pet_id:                 str
    date:                   str
    scheduled_tasks:        list[Task]
    unscheduled_tasks:      list[Task]
    total_duration_minutes: int
    slots:                  list[ScheduledSlot] = field(default_factory=list)
    conflicts:              list[str]           = field(default_factory=list)
    start_hour:             int                 = 8
    id: str = field(default_factory=lambda: str(uuid.uuid4()), init=False)

    def explain(self) -> str:
        """Returns a human-readable explanation of which tasks were chosen and why."""
        lines = [f"📅 Schedule for {self.date}", ""]

        if self.scheduled_tasks:
            lines.append(f"✅ Scheduled ({self.total_duration_minutes} min total):")
            for slot in self.slots:
                recur = (f" [🔁 {slot.task.recurrence}]"
                         if slot.task.recurrence != "none" else "")
                lines.append(
                    f"  {slot.time_label(self.start_hour)}  •  {slot.task.title}"
                    f" — {slot.task.duration_minutes} min"
                    f" [{slot.task.priority} priority, {slot.task.category}]{recur}"
                )
        else:
            lines.append("No tasks were scheduled.")

        if self.unscheduled_tasks:
            lines.append("")
            lines.append("⏭ Skipped (did not fit in time budget):")
            for task in self.unscheduled_tasks:
                lines.append(
                    f"  • {task.title} — {task.duration_minutes} min"
                    f" [{task.priority} priority]"
                )

        if self.conflicts:
            lines.append("")
            lines.append("⚠️ Conflicts detected:")
            for msg in self.conflicts:
                lines.append(f"  • {msg}")

        return "\n".join(lines)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Returns a specific scheduled task by ID, or None if not found."""
        return next((t for t in self.scheduled_tasks if t.id == task_id), None)

    def to_dict(self) -> dict:
        """Serializes the full schedule to a plain dictionary."""
        return {
            "id":                    self.id,
            "pet_id":                self.pet_id,
            "date":                  self.date,
            "scheduled_tasks":       [t.to_dict() for t in self.scheduled_tasks],
            "unscheduled_tasks":     [t.to_dict() for t in self.unscheduled_tasks],
            "total_duration_minutes": self.total_duration_minutes,
            "slots":                 [s.to_dict(self.start_hour) for s in self.slots],
            "conflicts":             self.conflicts,
            "start_hour":            self.start_hour,
        }


# ---------------------------------------------------------------------------
# Scheduler  (algorithm — SRP + OCP: one job, open to subclassing)
# ---------------------------------------------------------------------------

class Scheduler:
    """Encapsulates the scheduling algorithm.

    Responsibility: filter due tasks, sort by priority + duration, assign
    concrete time slots, and detect scheduling conflicts.

    Open for extension: subclass to implement alternative strategies
    (e.g. CategoryScheduler, TimeSlotScheduler) without modifying Schedule
    or Owner.
    """

    PRIORITY_ORDER: ClassVar[dict] = {"high": 0, "medium": 1, "low": 2}

    # Soft capacity (minutes) for each preferred time slot.
    # Exceeding these thresholds triggers a conflict warning.
    SLOT_CAPACITY: ClassVar[dict] = {
        "morning":   60,
        "afternoon": 90,
        "evening":   60,
    }

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def generate(self, pet: Pet, available_minutes: int, date: str, start_hour: int = 8) -> Schedule:
        """Filters tasks due today, sorts them, assigns time slots, detects conflicts.

        Sorting strategy: priority (high→low), then duration (short→long) as
        a tie-break — this is the greedy knapsack heuristic that maximises the
        number of tasks that fit within the budget.

        Args:
            pet:               the pet whose tasks will be scheduled.
            available_minutes: the owner's daily time budget in minutes.
            date:              ISO-format date string (YYYY-MM-DD).

        Returns:
            A populated Schedule instance with slots and any conflict messages.
        """
        # 1. Filter: only tasks that are due on this date
        candidate_tasks = [t for t in pet.get_tasks() if t.is_due(date)]

        # 2. Sort: priority first, shortest-duration first as a tie-break
        sorted_tasks = self._sort_tasks(candidate_tasks)

        # 3. Greedy fill — assign sequential time slots
        scheduled:  list[Task]          = []
        unscheduled: list[Task]         = []
        slots:      list[ScheduledSlot] = []
        conflicts:  list[str]           = []
        time_used = 0

        for task in sorted_tasks:
            remaining = available_minutes - time_used
            if task.duration_minutes <= remaining:
                slots.append(ScheduledSlot(
                    task=task,
                    start_minute=time_used,
                    end_minute=time_used + task.duration_minutes,
                ))
                scheduled.append(task)
                time_used += task.duration_minutes
            else:
                unscheduled.append(task)
                # Conflict: a high-priority task couldn't fit
                if task.is_high_priority():
                    conflicts.append(
                        f"High-priority task '{task.title}' ({task.duration_minutes} min) "
                        f"could not be scheduled — only {remaining} min remaining."
                    )

        # 4. Conflict: detect preferred time-slot overcrowding
        conflicts += self._detect_slot_conflicts(slots)

        return Schedule(
            pet_id=pet.id,
            date=date,
            scheduled_tasks=scheduled,
            unscheduled_tasks=unscheduled,
            total_duration_minutes=time_used,
            slots=slots,
            conflicts=conflicts,
            start_hour=start_hour,
        )

    # ------------------------------------------------------------------ #
    # Filtering & Sorting helpers                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def detect_time_conflicts(tasks: list[Task]) -> list[str]:
        """A lightweight conflict detection strategy that returns warning messages
        if two or more tasks are scheduled at the exact same time.

        Args:
            tasks: A list of Task objects to verify.

        Returns:
            A list of formatted warning strings describing detected time overlap conflicts.
        """
        warnings = []
        time_map: dict[str, list[str]] = {}
        for task in tasks:
            time_map.setdefault(task.time, []).append(f"{task.title}")
            
        for time_str, titles in time_map.items():
            if len(titles) > 1:
                warnings.append(
                    f"⚠️ Conflict at {time_str}: {', '.join(titles)} are scheduled at the same time!"
                )
        return warnings

    @staticmethod
    def sort_by_time(tasks: list[Task]) -> list[Task]:
        """Sorts tasks by their time attribute in strict chronological 'HH:MM' format.

        Args:
            tasks: The list of tasks to sort.

        Returns:
            A new list of Task objects ordered by their string time attribute via lambda.
        """
        # Python's sorted() uses lexical sorting for strings. 
        # A lambda function is passed as a "key" to sort by the HH:MM time property.
        return sorted(tasks, key=lambda t: t.time)

    @staticmethod
    def filter_tasks(
        tasks: list[Task],
        status: Optional[str] = None,
        sort_by: str = "priority",
    ) -> list[Task]:
        """Returns a filtered and sorted copy of *tasks*.

        Args:
            tasks:   source list to filter.
            status:  if given, keep only tasks whose .status matches.
            sort_by: one of 'priority' | 'duration' | 'category' | 'title'.
        """
        result = [t for t in tasks if status is None or t.status == status]

        sort_keys: dict = {
            "priority": lambda t: (
                {"high": 0, "medium": 1, "low": 2}.get(t.priority, 99),
                t.duration_minutes,
            ),
            "duration": lambda t: t.duration_minutes,
            "category": lambda t: t.category,
            "title":    lambda t: t.title.lower(),
        }
        return sorted(result, key=sort_keys.get(sort_by, sort_keys["priority"]))

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Sorts tasks: priority high→low, then duration short→long."""
        return sorted(
            tasks,
            key=lambda t: (self.PRIORITY_ORDER.get(t.priority, 99), t.duration_minutes),
        )

    def _detect_slot_conflicts(self, slots: list[ScheduledSlot]) -> list[str]:
        """Returns conflict messages when preferred time-slot usage exceeds capacity."""
        slot_time: dict[str, int] = {s: 0 for s in self.SLOT_CAPACITY}
        for s in slots:
            pref = s.task.preferred_time_slot
            if pref in slot_time:
                slot_time[pref] += s.task.duration_minutes

        messages = []
        for slot_name, used in slot_time.items():
            cap = self.SLOT_CAPACITY[slot_name]
            if used > cap:
                messages.append(
                    f"'{slot_name.capitalize()}' slot is overloaded: "
                    f"{used} min of tasks vs. {cap} min soft capacity."
                )
        return messages


# ---------------------------------------------------------------------------
# Owner  (root — single entry point for the entire app session)
# ---------------------------------------------------------------------------

@dataclass
class Owner:
    """The root of the application. One Owner per session.

    Responsibility: manage the user profile, pets, tasks, and schedule history.
    Delegates scheduling work to the injected Scheduler (DIP).
    """

    name:              str
    available_minutes: int            = 120
    start_hour:        int            = 8
    preferences:       list[str]      = field(default_factory=list)
    pets:              list[Pet]      = field(default_factory=list)
    schedules:         list[Schedule] = field(default_factory=list)
    scheduler:         Scheduler      = field(default_factory=Scheduler)
    id: str = field(default_factory=lambda: str(uuid.uuid4()), init=False)

    # --- Pet management ---

    def add_pet(self, pet: Pet) -> None:
        """Adds a pet."""
        self.pets.append(pet)

    def remove_pet(self, pet_id: str) -> None:
        """Removes a pet by ID. Silently ignores unknown IDs."""
        self.pets = [p for p in self.pets if p.id != pet_id]

    def get_pets(self) -> list[Pet]:
        """Returns all pets."""
        return list(self.pets)

    def get_pet(self, pet_id: str) -> Optional[Pet]:
        """Returns a specific pet by ID, or None if not found."""
        return next((p for p in self.pets if p.id == pet_id), None)

    def update_pet(self, pet_id: str, **kwargs) -> None:
        """Updates attributes of an existing pet by ID.

        Raises:
            ValueError: if pet_id is not found.
        """
        allowed = {"name", "species", "breed", "age"}
        pet = self.get_pet(pet_id)
        if pet is None:
            raise ValueError(f"Pet '{pet_id}' not found.")
        for key, value in kwargs.items():
            if key in allowed:
                setattr(pet, key, value)

    # --- Task management ---

    def create_task(
        self,
        pet_id:             str,
        title:              str,
        duration_minutes:   int,
        priority:           str = "medium",
        category:           str = "other",
        time:               str = "00:00",
        notes:              str = "",
        status:             str = "pending",
        recurrence:         str = "none",
        preferred_time_slot: str = "any",
        due_date:           Optional[str] = None,
    ) -> Task:
        """Creates a Task for a specific pet, sets pet_id, and appends it.

        Raises:
            ValueError: if pet_id is not found among this owner's pets.
        """
        pet = self.get_pet(pet_id)
        if pet is None:
            raise ValueError(f"Pet '{pet_id}' not found.")
        task = Task(
            pet_id=pet_id,
            title=title,
            duration_minutes=duration_minutes,
            priority=priority,
            category=category,
            time=time,
            notes=notes,
            status=status,
            recurrence=recurrence,
            preferred_time_slot=preferred_time_slot,
            due_date=due_date,
        )
        pet.add_task(task)
        return task

    def remove_task(self, task_id: str) -> None:
        """Removes a task by ID from whichever pet holds it."""
        for pet in self.pets:
            pet.remove_task(task_id)

    def get_tasks(self, pet_id: str) -> list[Task]:
        """Returns all tasks for a specific pet.

        Raises:
            ValueError: if pet_id is not found.
        """
        pet = self.get_pet(pet_id)
        if pet is None:
            raise ValueError(f"Pet '{pet_id}' not found.")
        return pet.get_tasks()

    def get_task(self, task_id: str) -> Optional[Task]:
        """Returns a specific task by ID across all pets, or None if not found."""
        for pet in self.pets:
            task = pet.get_task(task_id)
            if task is not None:
                return task
        return None

    def filter_tasks_by_pet_or_status(self, pet_name: Optional[str] = None, status: Optional[str] = None) -> list[Task]:
        """Filters tasks by completion status or pet name.

        Args:
            pet_name: Optional name string to restrict returned tasks to a specific pet.
            status: Optional status string (e.g., 'pending', 'completed') to filter by.

        Returns:
            A list of Task objects matching the provided constraints.
        """
        filtered_tasks = []
        for pet in self.pets:
            if pet_name is not None and pet.name != pet_name:
                continue
            for task in pet.get_tasks():
                if status is not None and task.status != status:
                    continue
                filtered_tasks.append(task)
        return filtered_tasks

    def complete_task(self, task_id: str, on_date: Optional[str] = None) -> None:
        """Marks a task as completed and automatically generates the next occurrence.

        Args:
            task_id: The UUID of the task to be marked completed.
            on_date: An optional string representing the completion date (YYYY-MM-DD). 
                     Defaults to today. For recurring tasks, this date is used to calculate 
                     the next occurrence via timedelta.
        """
        task = self.get_task(task_id)
        if not task: return
        
        task.set_status("completed", on_date)
        
        if task.recurrence != "none":
            from datetime import timedelta, datetime
            current_date = datetime.strptime(on_date or str(date_type.today()), "%Y-%m-%d").date()
            
            if task.recurrence == "daily":
                next_date = current_date + timedelta(days=1)
            elif task.recurrence == "weekly":
                next_date = current_date + timedelta(days=7)
            elif task.recurrence == "weekdays":
                next_date = current_date + timedelta(days=1)
                while next_date.weekday() >= 5:  # 5=Sat, 6=Sun
                    next_date += timedelta(days=1)
            else:
                next_date = current_date + timedelta(days=1)
                
            self.create_task(
                pet_id=task.pet_id,
                title=task.title,
                duration_minutes=task.duration_minutes,
                priority=task.priority,
                category=task.category,
                time=task.time,
                notes=task.notes,
                status="pending",
                recurrence=task.recurrence,
                preferred_time_slot=task.preferred_time_slot,
                due_date=str(next_date)
            )

    def get_filtered_tasks(
        self,
        pet_id:  Optional[str] = None,
        status:  Optional[str] = None,
        sort_by: str = "priority",
    ) -> list[Task]:
        """Returns a filtered and sorted list of tasks across all (or one) pet.

        Args:
            pet_id:  if given, restrict to that pet only.
            status:  if given, keep only tasks matching that status.
            sort_by: one of 'priority' | 'duration' | 'category' | 'title'.
        """
        tasks: list[Task] = []
        for pet in self.pets:
            if pet_id is None or pet.id == pet_id:
                tasks.extend(pet.get_tasks())
        return Scheduler.filter_tasks(tasks, status=status, sort_by=sort_by)

    def update_task(self, task_id: str, **kwargs) -> None:
        """Updates attributes of an existing task by ID.

        Raises:
            ValueError: if task_id is not found.
        """
        allowed = {
            "title", "duration_minutes", "priority", "category",
            "time", "notes", "recurrence", "preferred_time_slot",
        }
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found.")
        for key, value in kwargs.items():
            if key in allowed:
                setattr(task, key, value)

    # --- Schedule management ---

    def build_schedule(self, pet_id: str, date: str) -> Schedule:
        """Looks up the pet, runs the scheduler, stores and returns the result.

        If a schedule already exists for this pet on the same date it is
        replaced, so the schedule list never accumulates duplicates.

        Raises:
            ValueError: if pet_id is not found.
        """
        pet = self.get_pet(pet_id)
        if pet is None:
            raise ValueError(f"Pet '{pet_id}' not found.")

        # Dedup: remove any existing schedule for this pet + date
        self.schedules = [
            s for s in self.schedules
            if not (s.pet_id == pet_id and s.date == date)
        ]

        schedule = self.scheduler.generate(pet, self.available_minutes, date, self.start_hour)
        self.schedules.append(schedule)
        return schedule

    def get_schedules(self, pet_id: str) -> list[Schedule]:
        """Returns all schedules for a specific pet."""
        return [s for s in self.schedules if s.pet_id == pet_id]

    def get_schedule(self, schedule_id: str) -> Optional[Schedule]:
        """Returns a specific schedule by ID, or None if not found."""
        return next((s for s in self.schedules if s.id == schedule_id), None)

    def remove_schedule(self, schedule_id: str) -> None:
        """Removes a schedule by ID. Silently ignores unknown IDs."""
        self.schedules = [s for s in self.schedules if s.id != schedule_id]
