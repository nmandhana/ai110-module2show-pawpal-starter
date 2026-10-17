"""Tests for the PawPal+ logic layer (pawpal_system.py).

Run from the project root with:  pytest
"""

import pytest

from pawpal_system import DailyPlan, Owner, Pet, Scheduler, Task


def make_owner(minutes: int, *pets: Pet) -> Owner:
    """Build an owner with the given time budget and pets."""
    owner = Owner(name="Jordan", available_minutes=minutes)
    for pet in pets:
        owner.add_pet(pet)
    return owner


# --- Task and Pet basics ------------------------------------------------------


def test_mark_complete_changes_status():
    """A new task starts incomplete; mark_complete() flips its status."""
    task = Task("Feeding", 10, "high")
    assert task.completed is False

    task.mark_complete()

    assert task.completed is True


def test_adding_task_increases_pet_task_count():
    """Each add_task() call grows the pet's task list by one."""
    pet = Pet(name="Biscuit", species="dog")
    assert len(pet.tasks) == 0

    pet.add_task(Task("Feeding", 10, "high"))
    assert len(pet.tasks) == 1

    pet.add_task(Task("Morning walk", 30, "high"))
    assert len(pet.tasks) == 2


def test_add_task_stamps_pet_name():
    """add_task() records which pet the task belongs to."""
    pet = Pet(name="Mochi", species="cat")
    task = Task("Litter box", 15, "medium")

    pet.add_task(task)

    assert task.pet_name == "Mochi"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"duration_minutes": 0, "priority": "high"},
        {"duration_minutes": -5, "priority": "high"},
        {"duration_minutes": 10, "priority": "urgent"},
        {"duration_minutes": 10, "priority": "high", "frequency": "monthly"},
    ],
)
def test_invalid_task_is_rejected(kwargs):
    """Tasks with a non-positive duration or unknown priority/frequency can't be created."""
    with pytest.raises(ValueError):
        Task("Bad task", **kwargs)


def test_owner_get_all_tasks_combines_pets():
    """get_all_tasks() returns every pet's tasks together, in pet order."""
    dog = Pet(name="Biscuit", species="dog")
    dog.add_task(Task("Walk", 30, "high"))
    cat = Pet(name="Mochi", species="cat")
    cat.add_task(Task("Feeding", 10, "high"))
    owner = make_owner(60, dog, cat)

    titles = [t.title for t in owner.get_all_tasks()]

    assert titles == ["Walk", "Feeding"]


# --- Scheduler behavior -------------------------------------------------------


def test_scheduler_orders_by_priority():
    """High priority comes before medium, which comes before low."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Low task", 10, "low"))
    pet.add_task(Task("High task", 10, "high"))
    pet.add_task(Task("Medium task", 10, "medium"))

    plan = Scheduler().build_plan(make_owner(60, pet))

    assert [e.task.title for e in plan.entries] == ["High task", "Medium task", "Low task"]


def test_ties_break_daily_before_weekly_then_shortest():
    """Same priority: daily before weekly, then shorter duration first."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Weekly bath", 5, "high", frequency="weekly"))
    pet.add_task(Task("Long walk", 30, "high"))
    pet.add_task(Task("Feeding", 10, "high"))

    plan = Scheduler().build_plan(make_owner(60, pet))

    assert [e.task.title for e in plan.entries] == ["Feeding", "Long walk", "Weekly bath"]


def test_tasks_over_budget_are_skipped_with_reason():
    """A task that doesn't fit is skipped, and the skip explains why."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Walk", 30, "high"))
    pet.add_task(Task("Grooming", 45, "low"))

    plan = Scheduler().build_plan(make_owner(40, pet))

    assert [e.task.title for e in plan.entries] == ["Walk"]
    assert [s.task.title for s in plan.skipped] == ["Grooming"]
    assert "not enough time" in plan.skipped[0].reason


def test_scheduled_time_never_exceeds_budget():
    """Total scheduled minutes stay within the owner's available time."""
    pet = Pet(name="Biscuit", species="dog")
    for title, mins in [("A", 25), ("B", 25), ("C", 25), ("D", 25)]:
        pet.add_task(Task(title, mins, "medium"))

    plan = Scheduler().build_plan(make_owner(60, pet))

    assert sum(e.task.duration_minutes for e in plan.entries) <= 60


def test_smaller_task_still_fits_after_a_skip():
    """Skipping a big task doesn't stop a smaller, later task from fitting."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Big", 50, "high"))
    pet.add_task(Task("Small", 10, "low"))

    plan = Scheduler().build_plan(make_owner(20, pet))

    assert [e.task.title for e in plan.entries] == ["Small"]
    assert [s.task.title for s in plan.skipped] == ["Big"]


def test_completed_tasks_are_left_out():
    """Completed tasks appear in neither the schedule nor the skipped list."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Done already", 5, "high", completed=True))
    pet.add_task(Task("Feeding", 10, "high"))

    plan = Scheduler().build_plan(make_owner(60, pet))

    assert [e.task.title for e in plan.entries] == ["Feeding"]
    assert plan.skipped == []


def test_start_times_are_back_to_back_from_8am():
    """Tasks start at 08:00 and each begins when the previous one ends."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Feeding", 10, "high"))
    pet.add_task(Task("Walk", 30, "medium"))
    pet.add_task(Task("Play", 20, "low"))

    plan = Scheduler().build_plan(make_owner(90, pet))

    assert [e.start_time for e in plan.entries] == ["08:00", "08:10", "08:40"]


def test_plan_includes_tasks_from_all_pets():
    """The scheduler reads tasks across every pet, not just the first."""
    dog = Pet(name="Biscuit", species="dog")
    dog.add_task(Task("Walk", 30, "high"))
    cat = Pet(name="Mochi", species="cat")
    cat.add_task(Task("Feeding", 10, "high"))

    plan = Scheduler().build_plan(make_owner(60, dog, cat))

    assert {e.task.pet_name for e in plan.entries} == {"Biscuit", "Mochi"}


def test_empty_owner_gives_empty_plan():
    """No pets or tasks: an empty plan that says so."""
    plan = Scheduler().build_plan(make_owner(60))

    assert isinstance(plan, DailyPlan)
    assert plan.entries == [] and plan.skipped == []
    assert plan.explain() == "No tasks to schedule."
