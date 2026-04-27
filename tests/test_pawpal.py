"""
tests/test_pawpal.py
Unit tests for PawPal+ logic layer using pytest.
"""

import pytest
from datetime import date
from pawpal_system import Owner, Pet, Task, Schedule, Scheduler


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def pet():
    return Pet(name="Mochi", species="dog", breed="Shiba Inu", age=3)


@pytest.fixture
def owner():
    return Owner(name="Jordan", available_minutes=60)


@pytest.fixture
def owner_with_pet(owner, pet):
    owner.add_pet(pet)
    return owner, pet


@pytest.fixture
def task(pet):
    return Task(pet_id=pet.id, title="Morning Walk", duration_minutes=20, priority="high", category="walk")


# ===========================================================================
# Task tests
# ===========================================================================

class TestTask:

    def test_default_status_is_pending(self, task):
        assert task.status == "pending"

    def test_mark_complete_sets_status_to_completed(self, task):
        task.mark_complete()
        assert task.status == "completed"

    def test_set_status_in_progress(self, task):
        task.set_status("in_progress")
        assert task.status == "in_progress"

    def test_set_status_completed(self, task):
        task.set_status("completed")
        assert task.status == "completed"

    def test_set_status_pending(self, task):
        task.set_status("completed")
        task.set_status("pending")   # reset back
        assert task.status == "pending"

    def test_set_status_invalid_raises(self, task):
        with pytest.raises(ValueError, match="Invalid status"):
            task.set_status("done")

    def test_is_high_priority_true(self, task):
        assert task.is_high_priority() is True

    def test_is_high_priority_false(self, pet):
        low_task = Task(pet_id=pet.id, title="Play", duration_minutes=15, priority="low")
        assert low_task.is_high_priority() is False

    def test_to_dict_contains_all_fields(self, task):
        d = task.to_dict()
        assert d["title"] == "Morning Walk"
        assert d["priority"] == "high"
        assert d["status"] == "pending"
        assert d["pet_id"] == task.pet_id
        assert "id" in d

    def test_to_dict_status_updates_with_mark_complete(self, task):
        task.mark_complete()
        assert task.to_dict()["status"] == "completed"

    def test_task_has_unique_id(self, pet):
        t1 = Task(pet_id=pet.id, title="Walk", duration_minutes=10)
        t2 = Task(pet_id=pet.id, title="Walk", duration_minutes=10)
        assert t1.id != t2.id


# ===========================================================================
# Pet tests
# ===========================================================================

class TestPet:

    def test_add_task_increases_count(self, pet, task):
        assert len(pet.get_tasks()) == 0
        pet.add_task(task)
        assert len(pet.get_tasks()) == 1

    def test_add_multiple_tasks_increases_count(self, pet):
        for i in range(3):
            pet.add_task(Task(pet_id=pet.id, title=f"Task {i}", duration_minutes=10))
        assert len(pet.get_tasks()) == 3

    def test_add_task_wrong_pet_raises(self, pet):
        wrong_task = Task(pet_id="wrong-id", title="Walk", duration_minutes=10)
        with pytest.raises(ValueError):
            pet.add_task(wrong_task)

    def test_remove_task_decreases_count(self, pet, task):
        pet.add_task(task)
        pet.remove_task(task.id)
        assert len(pet.get_tasks()) == 0

    def test_remove_task_unknown_id_is_silent(self, pet):
        pet.remove_task("nonexistent-id")   # should not raise

    def test_get_task_by_id_returns_correct_task(self, pet, task):
        pet.add_task(task)
        found = pet.get_task(task.id)
        assert found is task

    def test_get_task_unknown_id_returns_none(self, pet):
        assert pet.get_task("no-such-id") is None

    def test_get_tasks_returns_copy(self, pet, task):
        pet.add_task(task)
        result = pet.get_tasks()
        result.clear()
        assert len(pet.get_tasks()) == 1   # original unchanged


# ===========================================================================
# Owner tests
# ===========================================================================

class TestOwner:

    def test_add_pet_increases_count(self, owner, pet):
        assert len(owner.get_pets()) == 0
        owner.add_pet(pet)
        assert len(owner.get_pets()) == 1

    def test_add_two_pets_increases_count_to_two(self, owner):
        owner.add_pet(Pet(name="Mochi", species="dog"))
        owner.add_pet(Pet(name="Luna", species="cat"))
        assert len(owner.get_pets()) == 2

    def test_remove_pet_decreases_count(self, owner, pet):
        owner.add_pet(pet)
        owner.remove_pet(pet.id)
        assert len(owner.get_pets()) == 0

    def test_remove_pet_unknown_id_is_silent(self, owner):
        owner.remove_pet("nonexistent-id")  # should not raise

    def test_get_pet_by_id(self, owner, pet):
        owner.add_pet(pet)
        found = owner.get_pet(pet.id)
        assert found is pet

    def test_get_pet_unknown_returns_none(self, owner):
        assert owner.get_pet("no-such-id") is None

    def test_update_pet_changes_attribute(self, owner, pet):
        owner.add_pet(pet)
        owner.update_pet(pet.id, name="Max")
        assert owner.get_pet(pet.id).name == "Max"

    def test_update_pet_unknown_raises(self, owner):
        with pytest.raises(ValueError):
            owner.update_pet("bad-id", name="Ghost")

    def test_create_task_adds_to_pet(self, owner, pet):
        owner.add_pet(pet)
        owner.create_task(pet.id, "Feeding", duration_minutes=10)
        assert len(pet.get_tasks()) == 1

    def test_create_task_returns_task_object(self, owner, pet):
        owner.add_pet(pet)
        task = owner.create_task(pet.id, "Walk", duration_minutes=20, priority="high")
        assert isinstance(task, Task)
        assert task.title == "Walk"

    def test_create_task_invalid_pet_raises(self, owner):
        with pytest.raises(ValueError):
            owner.create_task("bad-pet-id", "Walk", duration_minutes=20)

    def test_get_tasks_returns_pet_tasks(self, owner, pet):
        owner.add_pet(pet)
        owner.create_task(pet.id, "Walk", duration_minutes=20)
        owner.create_task(pet.id, "Feed", duration_minutes=10)
        assert len(owner.get_tasks(pet.id)) == 2

    def test_get_tasks_invalid_pet_raises(self, owner):
        with pytest.raises(ValueError):
            owner.get_tasks("bad-pet-id")

    def test_get_task_by_id_across_pets(self, owner):
        p1 = Pet(name="Mochi", species="dog")
        p2 = Pet(name="Luna",  species="cat")
        owner.add_pet(p1)
        owner.add_pet(p2)
        t = owner.create_task(p2.id, "Feeding", duration_minutes=10)
        found = owner.get_task(t.id)
        assert found is t

    def test_remove_task_removes_from_pet(self, owner, pet):
        owner.add_pet(pet)
        task = owner.create_task(pet.id, "Walk", duration_minutes=20)
        owner.remove_task(task.id)
        assert len(pet.get_tasks()) == 0

    def test_update_task_changes_attribute(self, owner, pet):
        owner.add_pet(pet)
        task = owner.create_task(pet.id, "Walk", duration_minutes=20, priority="low")
        owner.update_task(task.id, priority="high")
        assert task.priority == "high"

    def test_update_task_unknown_raises(self, owner):
        with pytest.raises(ValueError):
            owner.update_task("bad-id", priority="high")


# ===========================================================================
# Scheduler tests
# ===========================================================================

class TestScheduler:

    def test_high_priority_tasks_scheduled_first(self, pet):
        pet.add_task(Task(pet_id=pet.id, title="Low task",  duration_minutes=10, priority="low"))
        pet.add_task(Task(pet_id=pet.id, title="High task", duration_minutes=10, priority="high"))
        scheduler = Scheduler()
        schedule = scheduler.generate(pet, available_minutes=60, date="2026-04-05")
        assert schedule.scheduled_tasks[0].title == "High task"

    def test_tasks_within_budget_are_scheduled(self, pet):
        pet.add_task(Task(pet_id=pet.id, title="Walk",    duration_minutes=20, priority="high"))
        pet.add_task(Task(pet_id=pet.id, title="Feeding", duration_minutes=10, priority="high"))
        schedule = Scheduler().generate(pet, available_minutes=60, date="2026-04-05")
        assert len(schedule.scheduled_tasks) == 2
        assert len(schedule.unscheduled_tasks) == 0

    def test_tasks_over_budget_are_skipped(self, pet):
        pet.add_task(Task(pet_id=pet.id, title="Long task", duration_minutes=50, priority="low"))
        pet.add_task(Task(pet_id=pet.id, title="Walk",      duration_minutes=20, priority="high"))
        schedule = Scheduler().generate(pet, available_minutes=30, date="2026-04-05")
        titles_scheduled   = [t.title for t in schedule.scheduled_tasks]
        titles_unscheduled = [t.title for t in schedule.unscheduled_tasks]
        assert "Walk" in titles_scheduled
        assert "Long task" in titles_unscheduled

    def test_total_duration_is_accurate(self, pet):
        pet.add_task(Task(pet_id=pet.id, title="Walk",    duration_minutes=20, priority="high"))
        pet.add_task(Task(pet_id=pet.id, title="Feeding", duration_minutes=15, priority="medium"))
        schedule = Scheduler().generate(pet, available_minutes=60, date="2026-04-05")
        assert schedule.total_duration_minutes == 35

    def test_empty_pet_produces_empty_schedule(self, pet):
        schedule = Scheduler().generate(pet, available_minutes=60, date="2026-04-05")
        assert schedule.scheduled_tasks == []
        assert schedule.unscheduled_tasks == []
        assert schedule.total_duration_minutes == 0


# ===========================================================================
# Schedule tests
# ===========================================================================

class TestSchedule:

    @pytest.fixture
    def schedule(self, pet):
        pet.add_task(Task(pet_id=pet.id, title="Walk",    duration_minutes=20, priority="high"))
        pet.add_task(Task(pet_id=pet.id, title="Feeding", duration_minutes=10, priority="medium"))
        return Scheduler().generate(pet, available_minutes=60, date=str(date.today()))

    def test_explain_returns_string(self, schedule):
        result = schedule.explain()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_explain_mentions_scheduled_tasks(self, schedule):
        result = schedule.explain()
        assert "Walk" in result
        assert "Feeding" in result

    def test_explain_mentions_skipped_when_present(self, pet):
        pet.add_task(Task(pet_id=pet.id, title="Walk",     duration_minutes=20, priority="high"))
        pet.add_task(Task(pet_id=pet.id, title="Long task", duration_minutes=50, priority="low"))
        schedule = Scheduler().generate(pet, available_minutes=25, date="2026-04-05")
        assert "Skipped" in schedule.explain()

    def test_get_task_by_id(self, schedule):
        task = schedule.scheduled_tasks[0]
        found = schedule.get_task(task.id)
        assert found is task

    def test_get_task_unknown_returns_none(self, schedule):
        assert schedule.get_task("no-such-id") is None

    def test_to_dict_has_required_keys(self, schedule):
        d = schedule.to_dict()
        for key in ("id", "pet_id", "date", "scheduled_tasks", "unscheduled_tasks", "total_duration_minutes"):
            assert key in d

    def test_to_dict_scheduled_tasks_are_dicts(self, schedule):
        d = schedule.to_dict()
        assert all(isinstance(t, dict) for t in d["scheduled_tasks"])


# ===========================================================================
# Owner.build_schedule integration test
# ===========================================================================

class TestBuildSchedule:

    def test_build_schedule_stores_schedule(self, owner, pet):
        owner.add_pet(pet)
        owner.create_task(pet.id, "Walk", duration_minutes=20, priority="high")
        schedule = owner.build_schedule(pet.id, "2026-04-05")
        assert owner.get_schedule(schedule.id) is schedule

    def test_build_schedule_invalid_pet_raises(self, owner):
        with pytest.raises(ValueError):
            owner.build_schedule("bad-pet-id", "2026-04-05")

    def test_get_schedules_filters_by_pet(self, owner):
        p1 = Pet(name="Mochi", species="dog")
        p2 = Pet(name="Luna",  species="cat")
        owner.add_pet(p1)
        owner.add_pet(p2)
        owner.create_task(p1.id, "Walk",    duration_minutes=20)
        owner.create_task(p2.id, "Feeding", duration_minutes=10)
        owner.build_schedule(p1.id, "2026-04-05")
        owner.build_schedule(p2.id, "2026-04-05")
        assert len(owner.get_schedules(p1.id)) == 1
        assert len(owner.get_schedules(p2.id)) == 1

    def test_remove_schedule(self, owner, pet):
        owner.add_pet(pet)
        owner.create_task(pet.id, "Walk", duration_minutes=20)
        schedule = owner.build_schedule(pet.id, "2026-04-05")
        owner.remove_schedule(schedule.id)
        assert owner.get_schedule(schedule.id) is None


# ===========================================================================
# Sorting Correctness
# ===========================================================================

class TestSortingCorrectness:
    """Verifies that Scheduler.sort_by_time() returns tasks in chronological
    HH:MM order.

    Why this matters: the daily timeline displayed in the UI depends on tasks
    being listed earliest-first. If sort_by_time() is broken, a 14:00 task
    could appear before an 08:00 task.

    How it works:
      - Scheduler.sort_by_time() uses Python's sorted() with a lambda key
        that reads task.time (a "HH:MM" string).
      - "HH:MM" strings sort correctly lexicographically because hours and
        minutes are zero-padded to two digits — "08:00" < "12:00" < "14:00".
    """

    @pytest.fixture
    def pet(self):
        return Pet(name="Mochi", species="dog")

    def test_sort_three_tasks_chronologically(self, pet):
        """
        Creates three tasks with out-of-order times and confirms that
        sort_by_time() returns them earliest → latest.
        """
        t_late  = Task(pet_id=pet.id, title="Late Walk",   duration_minutes=20, time="14:00")
        t_early = Task(pet_id=pet.id, title="Early Feed",  duration_minutes=10, time="07:30")
        t_mid   = Task(pet_id=pet.id, title="Midday Play", duration_minutes=15, time="12:00")

        # Pass tasks in deliberately wrong order
        result = Scheduler.sort_by_time([t_late, t_early, t_mid])

        # Extract just the time strings from the sorted result
        times = [t.time for t in result]
        assert times == ["07:30", "12:00", "14:00"], (
            f"Expected chronological order, got: {times}"
        )

    def test_sort_already_sorted_list_unchanged(self, pet):
        """
        When tasks are already in order, sort_by_time() should produce the
        same sequence — no unintended reordering.
        """
        t1 = Task(pet_id=pet.id, title="A", duration_minutes=10, time="08:00")
        t2 = Task(pet_id=pet.id, title="B", duration_minutes=10, time="09:00")
        t3 = Task(pet_id=pet.id, title="C", duration_minutes=10, time="10:00")

        result = Scheduler.sort_by_time([t1, t2, t3])
        assert [t.time for t in result] == ["08:00", "09:00", "10:00"]

    def test_sort_single_task_returns_list_of_one(self, pet):
        """
        A list with a single task is trivially sorted — result should still
        be a list (not None or empty).
        """
        t = Task(pet_id=pet.id, title="Solo", duration_minutes=30, time="11:00")
        result = Scheduler.sort_by_time([t])
        assert len(result) == 1
        assert result[0].time == "11:00"

    def test_sort_empty_list_returns_empty_list(self):
        """
        Sorting an empty list should return an empty list, not raise an error.
        This guards against off-by-one crashes when a pet has no tasks.
        """
        assert Scheduler.sort_by_time([]) == []

    def test_sort_does_not_mutate_original_list(self, pet):
        """
        sorted() returns a *new* list, so the input list must stay unchanged.
        This confirms sort_by_time() has no side effects on the caller's data.
        """
        t1 = Task(pet_id=pet.id, title="Z Task", duration_minutes=10, time="23:00")
        t2 = Task(pet_id=pet.id, title="A Task", duration_minutes=10, time="06:00")
        original = [t1, t2]

        Scheduler.sort_by_time(original)

        # Original list must be untouched
        assert original[0].time == "23:00"
        assert original[1].time == "06:00"


# ===========================================================================
# Recurrence Logic
# ===========================================================================

class TestRecurrenceLogic:
    """Confirms that completing a recurring task automatically spawns the next
    occurrence with the correct due_date.

    Why this matters: PawPal+ uses recurring tasks so owners never have to
    manually re-enter daily walks or weekly grooming. If the recurrence logic
    breaks, tasks silently disappear after completion.

    How it works (Owner.complete_task):
      1. Marks the original task as 'completed'.
      2. Reads the completion date and uses timedelta to calculate the next date.
      3. Calls create_task() with due_date set to that next date and status
         reset to 'pending' — so it shows up on tomorrow's schedule.
    """

    @pytest.fixture
    def owner(self):
        return Owner(name="Jordan", available_minutes=120)

    @pytest.fixture
    def pet(self, owner):
        p = Pet(name="Mochi", species="dog")
        owner.add_pet(p)
        return p

    def test_daily_task_creates_new_task_for_next_day(self, owner, pet):
        """
        Completing a 'daily' task on 2026-04-05 must produce a new pending
        task with due_date = '2026-04-06' (one day later).

        timedelta(days=1) shifts the completion date forward by exactly one day.
        """
        task = owner.create_task(pet.id, "Daily Walk", duration_minutes=30,
                                 recurrence="daily")
        count_before = len(pet.get_tasks())

        owner.complete_task(task.id, on_date="2026-04-05")

        tasks_after = pet.get_tasks()
        assert len(tasks_after) == count_before + 1, "A new task should have been created."

        new_task = next(t for t in tasks_after if t.id != task.id)
        assert new_task.due_date == "2026-04-06"
        assert new_task.status == "pending"
        assert new_task.title == "Daily Walk"

    def test_weekly_task_creates_new_task_seven_days_later(self, owner, pet):
        """
        Completing a 'weekly' task on 2026-04-05 must produce a new task
        with due_date = '2026-04-12' (exactly 7 days later via timedelta(days=7)).
        """
        task = owner.create_task(pet.id, "Weekly Grooming", duration_minutes=60,
                                 recurrence="weekly")

        owner.complete_task(task.id, on_date="2026-04-05")

        new_task = next(t for t in pet.get_tasks() if t.id != task.id)
        assert new_task.due_date == "2026-04-12"

    def test_weekdays_task_skips_saturday_and_sunday(self, owner, pet):
        """
        Completing a 'weekdays' task on a Friday (2026-04-10) must skip
        Saturday (04-11) and Sunday (04-12) and land on Monday (2026-04-13).

        The loop `while next_date.weekday() >= 5` advances past any weekend day.
        weekday() returns 0=Mon … 4=Fri, 5=Sat, 6=Sun.
        """
        task = owner.create_task(pet.id, "Weekday Feed", duration_minutes=10,
                                 recurrence="weekdays")

        # 2026-04-10 is a Friday  (weekday() == 4)
        owner.complete_task(task.id, on_date="2026-04-10")

        new_task = next(t for t in pet.get_tasks() if t.id != task.id)
        assert new_task.due_date == "2026-04-13", (
            "After Friday the next weekday should be Monday 2026-04-13."
        )

    def test_none_recurrence_does_not_create_new_task(self, owner, pet):
        """
        A non-recurring task ('recurrence=\"none\"') must NOT spawn a follow-up
        task when completed. The pet's task count stays the same.
        """
        task = owner.create_task(pet.id, "One-off Bath", duration_minutes=45,
                                 recurrence="none")
        count_before = len(pet.get_tasks())

        owner.complete_task(task.id, on_date="2026-04-05")

        assert len(pet.get_tasks()) == count_before, (
            "Non-recurring tasks must not generate a follow-up."
        )

    def test_completed_original_task_is_marked_completed(self, owner, pet):
        """
        After calling complete_task(), the original task's status must be
        'completed', not left as 'pending'.
        """
        task = owner.create_task(pet.id, "Daily Meds", duration_minutes=5,
                                 recurrence="daily")

        owner.complete_task(task.id, on_date="2026-04-05")

        assert task.status == "completed"

    def test_new_recurring_task_inherits_same_recurrence(self, owner, pet):
        """
        The spawned task must carry the same recurrence value as the original.
        Without this, the chain would break after just one completion.
        """
        task = owner.create_task(pet.id, "Daily Walk", duration_minutes=30,
                                 recurrence="daily")

        owner.complete_task(task.id, on_date="2026-04-05")

        new_task = next(t for t in pet.get_tasks() if t.id != task.id)
        assert new_task.recurrence == "daily"


# ===========================================================================
# Conflict Detection
# ===========================================================================

class TestConflictDetection:
    """Verifies that Scheduler.detect_time_conflicts() correctly identifies
    tasks sharing the same HH:MM time slot.

    Why this matters: two tasks pinned to the same clock time (e.g. both at
    08:00) create a real-world conflict — the owner cannot do both at once.
    The detector surfaces these as warning strings so the UI can alert the user.

    How detect_time_conflicts() works:
      - Builds a dict mapping each time string → list of task titles.
      - Any time key with more than one title is a conflict.
      - Returns formatted warning strings; an empty list means no conflicts.
    """

    @pytest.fixture
    def pet(self):
        return Pet(name="Mochi", species="dog")

    def test_two_tasks_same_time_returns_one_warning(self, pet):
        """
        Two tasks both at '08:00' → exactly one conflict warning that
        mentions the shared time.
        """
        t1 = Task(pet_id=pet.id, title="Walk",    duration_minutes=20, time="08:00")
        t2 = Task(pet_id=pet.id, title="Feeding", duration_minutes=10, time="08:00")

        warnings = Scheduler.detect_time_conflicts([t1, t2])

        assert len(warnings) == 1
        assert "08:00" in warnings[0], "Warning must name the conflicting time."

    def test_three_tasks_same_time_returns_one_warning(self, pet):
        """
        Three tasks at the same time still produce only ONE warning per slot
        (the detector groups by time, not by pair).
        """
        tasks = [
            Task(pet_id=pet.id, title=f"Task {i}", duration_minutes=10, time="09:00")
            for i in range(3)
        ]
        warnings = Scheduler.detect_time_conflicts(tasks)
        assert len(warnings) == 1

    def test_two_tasks_different_times_no_warning(self, pet):
        """
        Tasks at different times must produce zero warnings — no false positives.
        """
        t1 = Task(pet_id=pet.id, title="Walk",    duration_minutes=20, time="08:00")
        t2 = Task(pet_id=pet.id, title="Feeding", duration_minutes=10, time="09:00")

        warnings = Scheduler.detect_time_conflicts([t1, t2])

        assert warnings == [], f"Expected no conflicts, got: {warnings}"

    def test_multiple_conflict_slots_returns_multiple_warnings(self, pet):
        """
        If conflicts exist at two different times (e.g. 08:00 AND 14:00),
        the detector should return one warning per conflicting slot — two total.
        """
        t1 = Task(pet_id=pet.id, title="Walk A",    duration_minutes=10, time="08:00")
        t2 = Task(pet_id=pet.id, title="Walk B",    duration_minutes=10, time="08:00")
        t3 = Task(pet_id=pet.id, title="Feed A",    duration_minutes=10, time="14:00")
        t4 = Task(pet_id=pet.id, title="Feed B",    duration_minutes=10, time="14:00")

        warnings = Scheduler.detect_time_conflicts([t1, t2, t3, t4])

        assert len(warnings) == 2

    def test_single_task_never_conflicts(self, pet):
        """
        A list with only one task cannot conflict with itself.
        """
        t = Task(pet_id=pet.id, title="Solo Walk", duration_minutes=30, time="08:00")
        assert Scheduler.detect_time_conflicts([t]) == []

    def test_empty_list_returns_no_warnings(self):
        """
        Passing an empty list must return an empty list — no crash.
        Edge case: a pet was just created and has no tasks yet.
        """
        assert Scheduler.detect_time_conflicts([]) == []

    def test_warning_message_names_conflicting_tasks(self, pet):
        """
        The warning string should mention the titles of the conflicting tasks
        so the user knows exactly which tasks clash.
        """
        t1 = Task(pet_id=pet.id, title="Morning Walk",    duration_minutes=20, time="08:00")
        t2 = Task(pet_id=pet.id, title="Morning Feeding", duration_minutes=10, time="08:00")

        warnings = Scheduler.detect_time_conflicts([t1, t2])

        assert "Morning Walk" in warnings[0]
        assert "Morning Feeding" in warnings[0]

    def test_default_time_tasks_do_not_produce_false_conflict(self, pet):
        """
        Tasks created without an explicit time default to None (no time set).
        Multiple such tasks must NOT generate a conflict warning —
        None means 'unscheduled', not 'scheduled at midnight'.
        """
        t1 = Task(pet_id=pet.id, title="Walk",    duration_minutes=20)
        t2 = Task(pet_id=pet.id, title="Feeding", duration_minutes=10)
        t3 = Task(pet_id=pet.id, title="Grooming", duration_minutes=15)

        assert t1.time is None
        warnings = Scheduler.detect_time_conflicts([t1, t2, t3])

        assert warnings == [], f"Expected no conflicts for unscheduled tasks, got: {warnings}"
