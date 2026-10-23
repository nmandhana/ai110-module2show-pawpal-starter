"""Tests for the PawPal+ logic layer (pawpal_system.py).

Run from the project root with:  pytest
"""

from datetime import date, timedelta

import pytest

from pawpal_system import DailyPlan, Owner, Pet, ScheduledTask, Scheduler, Task

TODAY = date(2026, 10, 21)


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


def test_task_time_defaults_to_flexible():
    """A task without a time is flexible (time is None)."""
    assert Task("Feeding", 10, "high").time is None


def test_task_accepts_valid_time():
    """A zero-padded 24-hour HH:MM time is stored as given."""
    assert Task("Meds", 5, "high", time="09:00").time == "09:00"
    assert Task("Late walk", 20, "medium", time="23:59").time == "23:59"


@pytest.mark.parametrize("bad_time", ["9:00", "24:00", "12:60", "noon", "", "08:00 "])
def test_invalid_time_is_rejected(bad_time):
    """Times that aren't valid zero-padded HH:MM can't be used to create a task."""
    with pytest.raises(ValueError):
        Task("Meds", 5, "high", time=bad_time)


def test_owner_get_all_tasks_combines_pets():
    """get_all_tasks() returns every pet's tasks together, in pet order."""
    dog = Pet(name="Biscuit", species="dog")
    dog.add_task(Task("Walk", 30, "high"))
    cat = Pet(name="Mochi", species="cat")
    cat.add_task(Task("Feeding", 10, "high"))
    owner = make_owner(60, dog, cat)

    titles = [t.title for t in owner.get_all_tasks()]

    assert titles == ["Walk", "Feeding"]


def make_filter_owner() -> Owner:
    """Two pets with a mix of finished and unfinished tasks, for filter tests."""
    dog = Pet(name="Biscuit", species="dog")
    dog.add_task(Task("Walk", 30, "high"))
    dog.add_task(Task("Pill", 5, "high", completed=True))
    cat = Pet(name="Mochi", species="cat")
    cat.add_task(Task("Feeding", 10, "high"))
    cat.add_task(Task("Brush", 10, "low", completed=True))
    return make_owner(60, dog, cat)


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({}, ["Walk", "Pill", "Feeding", "Brush"]),
        ({"completed": False}, ["Walk", "Feeding"]),
        ({"completed": True}, ["Pill", "Brush"]),
        ({"pet_name": "Mochi"}, ["Feeding", "Brush"]),
        ({"pet_name": "Mochi", "completed": False}, ["Feeding"]),
        ({"pet_name": "Biscuit", "completed": True}, ["Pill"]),
        ({"pet_name": "Nobody"}, []),
    ],
)
def test_filter_tasks(kwargs, expected):
    """filter_tasks() filters by status, by pet, or both; no filter returns everything."""
    titles = [t.title for t in make_filter_owner().filter_tasks(**kwargs)]

    assert titles == expected


def test_filter_tasks_returns_the_real_tasks():
    """Filtered results are the owner's own Task objects, so changes stick."""
    owner = make_filter_owner()

    owner.filter_tasks(pet_name="Mochi", completed=False)[0].mark_complete()

    assert owner.filter_tasks(pet_name="Mochi", completed=False) == []


def test_filter_tasks_sees_completed_recurring_task_and_its_next_copy():
    """After complete_task(), one copy is done and the new one is to do."""
    pet = Pet(name="Biscuit", species="dog")
    walk = Task("Walk", 30, "high")
    pet.add_task(walk)
    upcoming = pet.complete_task(walk)
    owner = make_owner(60, pet)

    assert owner.filter_tasks(completed=True) == [walk]
    assert owner.filter_tasks(completed=False) == [upcoming]


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


def test_sort_by_time_orders_by_clock_time():
    """Timed tasks come back earliest first, even across the 9→10 o'clock boundary."""
    tasks = [
        Task("Dinner", 10, "high", time="18:00"),
        Task("Walk", 30, "high", time="10:00"),
        Task("Meds", 5, "high", time="09:00"),
    ]

    result = Scheduler().sort_by_time(tasks)

    assert [t.time for t in result] == ["09:00", "10:00", "18:00"]


def test_sort_by_time_puts_flexible_tasks_last_in_original_order():
    """Untimed tasks go after timed ones and keep the order they were added."""
    tasks = [
        Task("Play", 20, "low"),
        Task("Meds", 5, "high", time="09:00"),
        Task("Brush", 10, "medium"),
        Task("Walk", 30, "high", time="07:30"),
    ]

    result = Scheduler().sort_by_time(tasks)

    assert [t.title for t in result] == ["Walk", "Meds", "Play", "Brush"]


def test_sort_by_time_does_not_change_input():
    """sort_by_time returns a new list and leaves the original order alone."""
    tasks = [Task("B", 5, "high", time="12:00"), Task("A", 5, "high", time="08:00")]

    Scheduler().sort_by_time(tasks)

    assert [t.title for t in tasks] == ["B", "A"]


def test_sort_by_time_keeps_same_time_tasks_in_added_order():
    """Two tasks at the exact same time stay in the order they were added."""
    tasks = [
        Task("Play", 20, "medium", time="18:00"),
        Task("Breakfast", 10, "high", time="07:00"),
        Task("Nail trim", 15, "low", time="18:00"),
    ]

    result = Scheduler().sort_by_time(tasks)

    assert [t.title for t in result] == ["Breakfast", "Play", "Nail trim"]


def test_sort_by_time_with_no_tasks_returns_empty_list():
    """Sorting an empty list gives an empty list, not an error."""
    assert Scheduler().sort_by_time([]) == []


# --- Fixed times and conflicts -------------------------------------------------


def test_fixed_time_task_is_booked_at_its_time():
    """A task with a time starts exactly then, not at 08:00."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Meds", 5, "high", time="09:30"))

    plan = Scheduler().build_plan(make_owner(60, pet))

    assert [(e.task.title, e.start_time) for e in plan.entries] == [("Meds", "09:30")]
    assert "fixed time 09:30" in plan.entries[0].reason


def test_flexible_tasks_fill_gaps_around_fixed_tasks():
    """Flexible tasks use the earliest gap that fits, skipping over appointments."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Vet call", 15, "low", time="08:20"))
    pet.add_task(Task("Feeding", 10, "high"))  # fits 08:00–08:10, before the call
    pet.add_task(Task("Walk", 30, "high"))  # too long for 08:10–08:20, goes after

    plan = Scheduler().build_plan(make_owner(90, pet))

    assert [(e.task.title, e.start_time) for e in plan.entries] == [
        ("Feeding", "08:00"),
        ("Vet call", "08:20"),
        ("Walk", "08:35"),
    ]


def test_flexible_task_never_pushes_out_a_fixed_task():
    """A higher-priority flexible task moves around a lower-priority appointment."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Walk", 30, "high"))
    pet.add_task(Task("Vet call", 15, "low", time="08:15"))

    plan = Scheduler().build_plan(make_owner(60, pet))

    assert [(e.task.title, e.start_time) for e in plan.entries] == [
        ("Vet call", "08:15"),
        ("Walk", "08:30"),
    ]
    assert plan.skipped == []


def test_overlapping_fixed_tasks_keep_the_higher_priority_one():
    """Two appointments that overlap: the higher-ranked one wins, the other is a conflict."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Grooming", 30, "low", time="09:00"))
    pet.add_task(Task("Meds", 10, "high", time="09:20"))

    plan = Scheduler().build_plan(make_owner(60, pet))

    assert [e.task.title for e in plan.entries] == ["Meds"]
    assert [s.task.title for s in plan.skipped] == ["Grooming"]
    assert "conflicts with Meds" in plan.skipped[0].reason


def test_back_to_back_fixed_tasks_are_not_a_conflict():
    """One task ending exactly when another starts is not an overlap."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Walk", 30, "high", time="09:00"))
    pet.add_task(Task("Feeding", 10, "high", time="09:30"))

    plan = Scheduler().build_plan(make_owner(60, pet))

    assert [e.start_time for e in plan.entries] == ["09:00", "09:30"]


def test_fixed_tasks_count_against_the_budget():
    """A fixed-time task still uses up the owner's available minutes."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Vet visit", 40, "high", time="10:00"))
    pet.add_task(Task("Walk", 30, "medium"))

    plan = Scheduler().build_plan(make_owner(50, pet))

    assert [e.task.title for e in plan.entries] == ["Vet visit"]
    assert "not enough time" in plan.skipped[0].reason


def test_entries_are_in_start_time_order():
    """The plan reads top to bottom in clock order, whatever the ranking was."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Evening meds", 5, "high", time="18:00"))
    pet.add_task(Task("Early walk", 20, "low", time="07:00"))
    pet.add_task(Task("Feeding", 10, "medium"))

    plan = Scheduler().build_plan(make_owner(60, pet))

    assert [e.start_time for e in plan.entries] == ["07:00", "08:00", "18:00"]


def test_task_running_past_midnight_is_skipped():
    """A fixed task that would end after 24:00 is skipped with a reason."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Night walk", 30, "high", time="23:45"))

    plan = Scheduler().build_plan(make_owner(60, pet))

    assert plan.entries == []
    assert plan.skipped[0].reason == "runs past midnight"


def test_unplaced_flexible_task_refunds_its_minutes():
    """A flexible task with no free gap gives its minutes back for a later task."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Day care", 960, "high", time="08:00"))  # fills 08:00–24:00
    pet.add_task(Task("Play", 10, "medium"))  # reserves 10 min, then finds no gap
    pet.add_task(Task("Early meds", 35, "low", time="07:00"))  # needs the refund

    plan = Scheduler().build_plan(make_owner(1000, pet))

    assert [e.task.title for e in plan.entries] == ["Early meds", "Day care"]
    assert [(s.task.title, s.reason) for s in plan.skipped] == [
        ("Play", "no free slot left today")
    ]


def test_reasons_show_running_budget_in_clock_order():
    """Each entry's reason shows the minutes used so far, rising down the plan."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Walk", 30, "high"))  # ranked first, but runs at 08:00
    pet.add_task(Task("Early meds", 5, "low", time="07:00"))

    plan = Scheduler().build_plan(make_owner(60, pet))

    assert [e.reason.split("; ")[-1] for e in plan.entries] == [
        "5/60 min used after this",
        "35/60 min used after this",
    ]


def test_skipped_tasks_are_listed_in_rank_order():
    """Skips from different passes still read most important first."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Grooming", 30, "low", time="09:00"))
    pet.add_task(Task("Meds", 10, "high", time="09:20"))
    pet.add_task(Task("Long walk", 90, "medium"))

    plan = Scheduler().build_plan(make_owner(60, pet))

    assert [s.task.title for s in plan.skipped] == ["Long walk", "Grooming"]


# --- Conflict detection -----------------------------------------------------------


def test_detect_conflicts_same_pet():
    """Two overlapping fixed-time tasks for one pet give one warning naming both."""
    pet = Pet(name="Mochi", species="cat")
    pet.add_task(Task("Play", 20, "medium", time="18:00", due_date=TODAY))
    pet.add_task(Task("Nail trim", 15, "low", time="18:10", due_date=TODAY))

    warnings = Scheduler().detect_conflicts(pet.tasks)

    assert warnings == [
        "Mochi's Play (18:00–18:20) overlaps Mochi's Nail trim (18:10–18:25) "
        "on 2026-10-21 — same pet"
    ]


def test_detect_conflicts_different_pets():
    """Overlaps are found across pets, not only within one pet's list."""
    biscuit = Pet(name="Biscuit", species="dog")
    mochi = Pet(name="Mochi", species="cat")
    biscuit.add_task(Task("Grooming", 45, "low", time="17:30", due_date=TODAY))
    mochi.add_task(Task("Play", 20, "medium", time="18:00", due_date=TODAY))

    warnings = Scheduler().detect_conflicts(make_owner(60, biscuit, mochi).get_all_tasks())

    assert len(warnings) == 1
    assert "Biscuit's Grooming" in warnings[0] and "Mochi's Play" in warnings[0]
    assert warnings[0].endswith("different pets")


def test_detect_conflicts_exact_same_time():
    """Two tasks starting at the very same minute clash, and the warning says so."""
    tasks = [
        Task("Meds", 5, "high", time="09:00", due_date=TODAY, pet_name="Biscuit"),
        Task("Meds", 5, "high", time="09:00", due_date=TODAY, pet_name="Mochi"),
    ]

    assert Scheduler().detect_conflicts(tasks) == [
        "Biscuit's Meds (09:00–09:05) starts at the same time as Mochi's Meds (09:00–09:05) "
        "on 2026-10-21 — different pets"
    ]


def test_same_time_tasks_warn_instead_of_crashing():
    """Two tasks at the same time that both fit the budget: build_plan doesn't
    raise — it warns, keeps the higher-ranked one and skips the other."""
    biscuit = Pet(name="Biscuit", species="dog")
    mochi = Pet(name="Mochi", species="cat")
    biscuit.add_task(Task("Walk", 30, "high", time="18:00", due_date=TODAY))
    mochi.add_task(Task("Vet call", 15, "medium", time="18:00", due_date=TODAY))

    plan = Scheduler().build_plan(make_owner(300, biscuit, mochi), TODAY)

    assert len(plan.warnings) == 1 and "starts at the same time as" in plan.warnings[0]
    assert [(e.task.title, e.start_time) for e in plan.entries] == [("Walk", "18:00")]
    assert plan.skipped[0].reason == "conflicts with Walk (Biscuit) at 18:00–18:30"


def test_detect_conflicts_reports_every_pair():
    """Three tasks that all overlap give a warning for each of the three pairs."""
    tasks = [
        Task("A", 60, "high", time="09:00", due_date=TODAY),
        Task("B", 60, "high", time="09:15", due_date=TODAY),
        Task("C", 60, "high", time="09:30", due_date=TODAY),
    ]

    assert len(Scheduler().detect_conflicts(tasks)) == 3


@pytest.mark.parametrize(
    "other",
    [
        Task("Walk", 30, "high", time="09:30", due_date=TODAY),  # starts as Meds ends
        Task("Walk", 30, "high", due_date=TODAY),  # flexible
        Task("Walk", 30, "high", time="09:00", due_date=TODAY, completed=True),  # done
        Task("Walk", 30, "high", time="09:00", due_date=TODAY + timedelta(days=1)),  # other day
    ],
    ids=["back-to-back", "flexible", "completed", "different-day"],
)
def test_detect_conflicts_ignores_non_clashes(other):
    """Touching ends, flexible tasks, done tasks and other days are not conflicts."""
    meds = Task("Meds", 30, "high", time="09:00", due_date=TODAY)

    assert Scheduler().detect_conflicts([meds, other]) == []


def test_detect_conflicts_with_no_tasks_returns_empty_list():
    """No tasks means no warnings — and no error."""
    assert Scheduler().detect_conflicts([]) == []


def test_plan_warns_about_conflicts_even_when_tasks_are_skipped_for_time():
    """build_plan reports a clash even if neither task got far enough to be booked."""
    biscuit = Pet(name="Biscuit", species="dog")
    mochi = Pet(name="Mochi", species="cat")
    biscuit.add_task(Task("Grooming", 45, "low", time="17:30", due_date=TODAY))
    mochi.add_task(Task("Play", 20, "low", time="18:00", due_date=TODAY))

    plan = Scheduler().build_plan(make_owner(10, biscuit, mochi), TODAY)

    assert plan.entries == []
    assert len(plan.skipped) == 2
    assert len(plan.warnings) == 1
    assert plan.explain().startswith("Warning: Biscuit's Grooming (17:30–18:15) overlaps")


def test_plan_warns_when_overdue_task_clashes_with_todays():
    """An overdue task is planned for today, so it can clash with today's task."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Meds", 10, "high", time="09:00", due_date=TODAY - timedelta(days=1)))
    pet.add_task(Task("Walk", 30, "high", time="09:05", due_date=TODAY))

    plan = Scheduler().build_plan(make_owner(60, pet), TODAY)

    assert plan.warnings == [
        "Biscuit's Meds (09:00–09:10) overlaps Biscuit's Walk (09:05–09:35) "
        "on 2026-10-21 — same pet"
    ]
    assert "conflicts with Meds" in plan.skipped[0].reason


def test_plan_without_clashes_has_no_warnings():
    """A plan with no overlapping fixed tasks carries no warnings."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Walk", 30, "high", time="09:00", due_date=TODAY))
    pet.add_task(Task("Feeding", 10, "high", time="09:30", due_date=TODAY))

    plan = Scheduler().build_plan(make_owner(60, pet), TODAY)

    assert plan.warnings == []
    assert not plan.explain().startswith("Warning")


def test_scheduled_task_end_time():
    """end_time is start plus duration, rolling over the hour correctly."""
    entry = ScheduledTask(Task("Walk", 30, "high"), "08:45", "")
    assert entry.end_time == "09:15"


# --- Recurring tasks and due dates ----------------------------------------------


@pytest.mark.parametrize("frequency, days", [("daily", 1), ("weekly", 7)])
def test_next_occurrence_is_one_period_later(frequency, days):
    """next_occurrence() copies the task, unfinished, due one day or one week later."""
    task = Task("Walk", 30, "high", frequency=frequency, due_date=TODAY, time="09:00")
    task.mark_complete(TODAY)

    upcoming = task.next_occurrence(TODAY)

    assert upcoming is not task
    assert upcoming.due_date == TODAY + timedelta(days=days)
    assert upcoming.completed is False
    assert (upcoming.title, upcoming.time, upcoming.priority) == ("Walk", "09:00", "high")


@pytest.mark.parametrize("frequency, days", [("daily", 1), ("weekly", 7)])
def test_mark_complete_creates_next_occurrence(frequency, days):
    """mark_complete() finishes the task and returns a new one due one period later."""
    task = Task("Walk", 30, "high", frequency=frequency, due_date=TODAY)

    upcoming = task.mark_complete(TODAY)

    assert task.completed is True
    assert upcoming is not task
    assert upcoming.completed is False
    assert upcoming.due_date == TODAY + timedelta(days=days)


def test_complete_task_books_next_occurrence():
    """Pet.complete_task() marks the task done and adds the next one to the pet."""
    pet = Pet(name="Biscuit", species="dog")
    walk = Task("Walk", 30, "high", due_date=TODAY)
    pet.add_task(walk)

    upcoming = pet.complete_task(walk, TODAY)

    assert walk.completed is True
    assert pet.tasks == [walk, upcoming]
    assert upcoming.due_date == TODAY + timedelta(days=1)
    assert upcoming.pet_name == "Biscuit"


def test_overdue_task_completed_today_is_next_due_tomorrow():
    """Finishing an overdue daily task books it for today + 1 day, not for a past day."""
    walk = Task("Walk", 30, "high", due_date=TODAY - timedelta(days=3))

    upcoming = walk.mark_complete(TODAY)

    assert upcoming.due_date == TODAY + timedelta(days=1)


def test_task_completed_early_counts_from_its_due_date():
    """Finishing tomorrow's walk today books the day after tomorrow, not tomorrow again."""
    walk = Task("Walk", 30, "high", due_date=TODAY + timedelta(days=1))

    upcoming = walk.mark_complete(TODAY)

    assert upcoming.due_date == TODAY + timedelta(days=2)


@pytest.mark.parametrize(
    "completed_on, frequency, expected",
    [
        (date(2026, 10, 31), "daily", date(2026, 11, 1)),
        (date(2026, 12, 31), "daily", date(2027, 1, 1)),
        (date(2028, 2, 28), "daily", date(2028, 2, 29)),
        (date(2026, 12, 28), "weekly", date(2027, 1, 4)),
    ],
)
def test_next_due_date_crosses_month_and_year_ends(completed_on, frequency, expected):
    """timedelta rolls over month ends, year ends and leap days correctly."""
    task = Task("Walk", 30, "high", frequency=frequency, due_date=completed_on)

    assert task.mark_complete(completed_on).due_date == expected


def test_mark_complete_defaults_to_today():
    """With no date given, the next due date counts from the real today."""
    task = Task("Walk", 30, "high", due_date=date.today() - timedelta(days=5))

    assert task.mark_complete().due_date == date.today() + timedelta(days=1)


def test_tasks_due_later_are_left_out_of_todays_plan():
    """Tomorrow's occurrence doesn't appear today, but is planned tomorrow."""
    pet = Pet(name="Biscuit", species="dog")
    walk = Task("Walk", 30, "high", due_date=TODAY)
    pet.add_task(walk)
    pet.complete_task(walk, TODAY)
    owner = make_owner(60, pet)

    today_plan = Scheduler().build_plan(owner, TODAY)
    tomorrow_plan = Scheduler().build_plan(owner, TODAY + timedelta(days=1))

    assert today_plan.entries == [] and today_plan.skipped == []
    assert [e.task.title for e in tomorrow_plan.entries] == ["Walk"]


def test_overdue_task_is_still_planned_and_flagged():
    """A task due before the plan day is still owed, and its reason says so."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Nail trim", 15, "low", due_date=TODAY - timedelta(days=2)))

    plan = Scheduler().build_plan(make_owner(60, pet), TODAY)

    assert "overdue since 2026-10-19" in plan.entries[0].reason


# --- Editing and removing ---------------------------------------------------------


def test_duplicate_unfinished_task_is_rejected():
    """The same title twice (any case) for one pet on one day is refused."""
    pet = Pet(name="Biscuit", species="dog")
    pet.add_task(Task("Walk", 30, "high"))

    with pytest.raises(ValueError, match="already has"):
        pet.add_task(Task("walk", 20, "low"))


def test_same_title_allowed_once_the_first_is_done_or_on_another_pet():
    """Duplicates only matter for unfinished tasks of the same pet."""
    dog = Pet(name="Biscuit", species="dog")
    cat = Pet(name="Mochi", species="cat")
    first = Task("Feeding", 10, "high")
    dog.add_task(first)
    cat.add_task(Task("Feeding", 10, "high"))  # different pet: fine

    first.mark_complete()
    dog.add_task(Task("Feeding", 10, "high"))  # first one is done: fine

    assert len(dog.tasks) == 2


def test_edit_task_changes_fields_in_place():
    """edit_task() updates only the named fields of the same task object."""
    pet = Pet(name="Biscuit", species="dog")
    walk = Task("Walk", 30, "high")
    pet.add_task(walk)

    pet.edit_task(walk, duration_minutes=45, time="07:30")

    assert pet.tasks[0] is walk
    assert (walk.duration_minutes, walk.time, walk.priority) == (45, "07:30", "high")


@pytest.mark.parametrize("changes", [{"duration_minutes": 0}, {"time": "7:30"}, {"title": "Feeding"}])
def test_bad_edit_raises_and_changes_nothing(changes):
    """An invalid value or a duplicate title is rejected and the task stays as it was."""
    pet = Pet(name="Biscuit", species="dog")
    walk = Task("Walk", 30, "high")
    pet.add_task(walk)
    pet.add_task(Task("Feeding", 10, "high"))

    with pytest.raises(ValueError):
        pet.edit_task(walk, **changes)

    assert (walk.title, walk.duration_minutes, walk.time) == ("Walk", 30, None)


def test_remove_task_and_remove_pet():
    """Removed tasks and pets disappear from get_all_tasks()."""
    dog = Pet(name="Biscuit", species="dog")
    walk, feed = Task("Walk", 30, "high"), Task("Feeding", 10, "high")
    dog.add_task(walk)
    dog.add_task(feed)
    cat = Pet(name="Mochi", species="cat")
    cat.add_task(Task("Litter box", 15, "medium"))
    owner = make_owner(60, dog, cat)

    dog.remove_task(walk)
    assert [t.title for t in owner.get_all_tasks()] == ["Feeding", "Litter box"]

    owner.remove_pet(cat)
    assert [t.title for t in owner.get_all_tasks()] == ["Feeding"]


def test_removing_a_task_the_pet_does_not_have_raises():
    """remove_task() refuses a task that belongs to someone else."""
    with pytest.raises(ValueError):
        Pet(name="Biscuit", species="dog").remove_task(Task("Walk", 30, "high"))


def test_empty_owner_gives_empty_plan():
    """No pets or tasks: an empty plan that says so."""
    plan = Scheduler().build_plan(make_owner(60))

    assert isinstance(plan, DailyPlan)
    assert plan.entries == [] and plan.skipped == []
    assert plan.explain() == "No tasks to schedule."


def test_pet_with_no_tasks_is_handled():
    """A pet with no tasks doesn't break planning, filtering or conflict checks,
    and doesn't stop another pet's tasks from being planned."""
    empty = Pet(name="Rex", species="dog")
    busy = Pet(name="Mochi", species="cat")
    busy.add_task(Task("Feeding", 10, "high", due_date=TODAY))
    owner = make_owner(60, empty, busy)

    plan = Scheduler().build_plan(owner, TODAY)

    assert [e.task.title for e in plan.entries] == ["Feeding"]
    assert owner.filter_tasks(pet_name="Rex") == []
    assert Scheduler().detect_conflicts(empty.tasks) == []
    assert Scheduler().build_plan(make_owner(60, empty), TODAY).explain() == "No tasks to schedule."
