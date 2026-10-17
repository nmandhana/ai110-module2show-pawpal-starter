# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🧩 Design Overview

The backend lives in `pawpal_system.py` (no Streamlit code there); the full class diagram is in `diagrams/uml.mmd`.

- **Task** — one care activity: `title`, `duration_minutes` (how long it takes), `priority` (high/medium/low), `frequency` (daily/weekly), `completed` status, and `pet_name` (which pet it belongs to). Tasks validate their own fields on construction, so an invalid task can't exist.
- **Pet** — pet details plus its task list; all additions go through `add_task()`, the single doorway for list-level rules, which also stamps each task with the pet's name.
- **Owner** — the owner's time available today (the scheduler's main constraint) and the pets they manage; `get_all_tasks()` returns every pet's tasks together.
- **Scheduler** — stateless logic that reads tasks across all pets via `Owner.get_all_tasks()`, ranks them by priority, and fits them into the time budget.
- **DailyPlan / ScheduledTask / SkippedTask** — the result: ordered entries with a reason for each choice, plus which tasks were left out and why.

## 🛠️ Implementation Summary

PawPal+ takes a list of pet care chores and a busy owner's free time, and turns them into a realistic plan for the day — one that does the most important things first and is honest about what didn't fit.

**How the pieces work together**

Think of it like a household:

1. **The owner sets the limit.** An `Owner` says how many minutes they have today and which pets they look after.
2. **Each pet keeps its own to-do list.** A `Pet` holds its `Task`s — "Morning walk, 30 min, high priority, daily." When a task is added, the pet writes its name on it, so later we always know whose chore it is. A task checks itself when it's created, so nonsense like a 0-minute walk or a "super-urgent" priority is rejected right away. Once a chore is done, `mark_complete()` ticks it off.
3. **The scheduler makes the decisions.** The `Scheduler` asks the owner for every pet's tasks in one go (`get_all_tasks()`), sets aside anything already done, and sorts the rest:
   - most important first (high → medium → low),
   - then daily chores before weekly ones (a skipped daily chore is a missed day; a weekly one can wait),
   - then shorter tasks first, so more of them fit.

   It then walks down that list, adding each task if there's still time and skipping it if not. Tasks are placed back-to-back starting at 08:00, so nothing ever overlaps.
4. **The plan explains itself.** The result is a `DailyPlan`: a list of scheduled tasks with start times, plus a list of skipped tasks. Every entry carries a short reason written *at the moment the decision was made* — "high priority, daily task, fits in the 70 min remaining" or "not enough time left (needs 45 min, only 5 min remaining)". `explain()` reads those reasons back.

**Why it's built this way**

- **Each class has one job.** Pets and tasks just hold information; only the scheduler makes choices; the plan just reports the result. Changing one part rarely breaks another.
- **The scheduler only talks to the owner.** It never digs into individual pets, so how pets are stored can change without touching the scheduling logic.
- **Same input, same plan.** The scheduler keeps no memory between runs, which makes its behavior predictable and easy to test.

**Trying it out**

- `python main.py` builds a sample owner with two pets (a dog and a cat) and prints today's schedule as a table in the terminal.
- `pytest` runs the test suite in `tests/test_pawpal.py`, which checks task creation, task completion, adding tasks to pets, priority ordering, the time budget, skipped-task reasons, and multi-pet plans.

## 🖥️ Sample Output

Output of `python main.py` (terminal demo — one owner with 90 minutes, a dog and a cat, eight tasks, one already completed):

```
==============================================================
  🐾 TODAY'S SCHEDULE
  Owner: Jordan   Pets: Biscuit (dog), Mochi (cat)
  Time available: 90 min
==============================================================
  TIME          TASK          PET       MIN  PRIORITY
  ------------------------------------------------------------
  08:00–08:10   Feeding       Biscuit    10  HIGH
  08:10–08:20   Feeding       Mochi      10  HIGH
  08:20–08:50   Morning walk  Biscuit    30  HIGH
  08:50–09:05   Litter box    Mochi      15  MEDIUM
  09:05–09:25   Play session  Mochi      20  MEDIUM

  SKIPPED (not enough time)
  ------------------------------------------------------------
  ✗ Nail trim     Mochi    needs 15 min
  ✗ Grooming      Biscuit  needs 45 min

  Why this order: priority (high → low), then daily before weekly,
  then shortest first; tasks added until the time ran out.
==============================================================
  5 tasks scheduled · 85/90 min used · 5 min free
==============================================================
```

Biscuit's "Heartworm pill" doesn't appear anywhere because it was already marked complete.

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest

# Run with coverage (needs `pip install pytest-cov`, not in requirements.txt):
pytest --cov
```

`pytest.ini` points pytest at the `tests/` folder and adds the project root to the import path, so plain `pytest` works from the project folder.

Sample test output (`pytest -v`):

```
tests/test_pawpal.py::test_mark_complete_changes_status PASSED           [  5%]
tests/test_pawpal.py::test_adding_task_increases_pet_task_count PASSED   [ 11%]
tests/test_pawpal.py::test_add_task_stamps_pet_name PASSED               [ 17%]
tests/test_pawpal.py::test_invalid_task_is_rejected[kwargs0] PASSED      [ 23%]
tests/test_pawpal.py::test_invalid_task_is_rejected[kwargs1] PASSED      [ 29%]
tests/test_pawpal.py::test_invalid_task_is_rejected[kwargs2] PASSED      [ 35%]
tests/test_pawpal.py::test_invalid_task_is_rejected[kwargs3] PASSED      [ 41%]
tests/test_pawpal.py::test_owner_get_all_tasks_combines_pets PASSED      [ 47%]
tests/test_pawpal.py::test_scheduler_orders_by_priority PASSED           [ 52%]
tests/test_pawpal.py::test_ties_break_daily_before_weekly_then_shortest PASSED [ 58%]
tests/test_pawpal.py::test_tasks_over_budget_are_skipped_with_reason PASSED [ 64%]
tests/test_pawpal.py::test_scheduled_time_never_exceeds_budget PASSED    [ 70%]
tests/test_pawpal.py::test_smaller_task_still_fits_after_a_skip PASSED   [ 76%]
tests/test_pawpal.py::test_completed_tasks_are_left_out PASSED           [ 82%]
tests/test_pawpal.py::test_start_times_are_back_to_back_from_8am PASSED  [ 88%]
tests/test_pawpal.py::test_plan_includes_tasks_from_all_pets PASSED      [ 94%]
tests/test_pawpal.py::test_empty_owner_gives_empty_plan PASSED           [100%]

============================== 17 passed in 0.02s ==============================
```

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler._rank_tasks()` | Priority (high → medium → low), then daily before weekly, then shortest first. Stable sort, so the same input always gives the same order. |
| Filtering | `Scheduler.build_plan()`, `Scheduler._fits_in_budget()`, `Task.mark_complete()` | Completed tasks are left out. A task that doesn't fit the remaining time is skipped with a reason, and the loop keeps going, so a smaller task further down can still fit. |
| Conflict handling | `Scheduler.build_plan()` | Avoided by design: tasks are placed back-to-back from 08:00, so they can't overlap. There's no check for overlapping user-chosen times, because tasks don't have a set time of day. |
| Recurring tasks | `Task.frequency`, `Scheduler._rank_tasks()` | Partial: `daily`/`weekly` is stored and validated, and daily tasks rank ahead of weekly ones on ties. Tasks aren't automatically re-created for the next day or week yet. |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

**Terminal demo (`main.py`)** — available now:

1. Set up the environment (see [Setup](#setup)) and run `python main.py` from the project folder.
2. The script creates an owner, Jordan, with 90 minutes free today, and two pets: Biscuit (dog) and Mochi (cat).
3. It adds eight tasks across the two pets, with different durations, priorities and frequencies. One of them, Biscuit's "Heartworm pill", is already marked complete.
4. The `Scheduler` builds the plan and the terminal prints a "Today's Schedule" table: each task's time slot, pet, length and priority, in the order they were chosen.
5. Below the table, a "Skipped" section lists the tasks that didn't fit and how long each needed, followed by a one-line summary of time used and time left (shown in Sample Output above).

**Streamlit app (`app.py`)**: <!-- Not connected to the scheduler yet; describe these steps once it is -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
