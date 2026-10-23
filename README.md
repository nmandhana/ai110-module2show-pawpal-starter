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

- **Task** — one care activity: `title`, `duration_minutes` (how long it takes), `priority` (high/medium/low), `frequency` (daily/weekly), `completed` status, `pet_name` (which pet it belongs to), an optional `time` of day (`"HH:MM"`) for fixed appointments (tasks without one are flexible), and a `due_date` (defaults to today). Tasks validate their own fields on construction, so an invalid task can't exist. `mark_complete()` ticks a task off and returns its next occurrence (a new copy from `next_occurrence()`, due a day or a week later).
- **Pet** — pet details plus its task list. All changes go through the pet: `add_task()` (stamps the pet's name and refuses a duplicate unfinished task with the same title on the same day), `edit_task()` (changes fields in place with the same checks), `remove_task()`, and `complete_task()` (marks a task done and books its next occurrence).
- **Owner** — the owner's time available today (the scheduler's main constraint) and the pets they manage; `add_pet()` / `remove_pet()`; `get_all_tasks()` returns every pet's tasks together, and `filter_tasks(completed=..., pet_name=...)` returns only the ones matching a status, a pet, or both.
- **Scheduler** — stateless logic that reads tasks across all pets via `Owner.get_all_tasks()`, keeps the ones due on the plan day, ranks them by priority, fits them into the time budget, books fixed-time tasks at their time (skipping overlaps as conflicts) and slots flexible tasks into the free gaps. `sort_by_time()` orders tasks by time of day for display.
- **DailyPlan / ScheduledTask / SkippedTask** — the result: entries in start-time order (each with an `end_time`) and a reason for each choice, plus which tasks were left out and why. `explain()` turns the plan into readable text.

## 🛠️ Implementation Summary

PawPal+ takes a list of pet care chores and a busy owner's free time, and turns them into a realistic plan for the day — one that does the most important things first, respects fixed appointments, and is honest about what didn't fit.

**How the pieces work together**

Think of it like a household:

1. **The owner sets the limit.** An `Owner` says how many minutes they have today and which pets they look after.
2. **Each pet keeps its own to-do list.** A `Pet` holds its `Task`s — "Morning walk, 30 min, high priority, daily", or "Vet call, 15 min, at 08:15". When a task is added, the pet writes its name on it, so later we always know whose chore it is. A task checks itself when it's created, so nonsense like a 0-minute walk, a "super-urgent" priority or a time of "9am" is rejected right away, and a pet won't accept the same unfinished chore twice for one day.
3. **Chores come back.** When a chore is done, `complete_task()` ticks it off and books the next one — tomorrow for a daily task, in a week for a weekly one. Each task has a `due_date`, and only tasks due today (or overdue) are planned.
4. **The scheduler makes the decisions.** The `Scheduler` asks the owner for every pet's tasks in one go (`get_all_tasks()`), sets aside anything done or not yet due, and sorts the rest:
   - most important first (high → medium → low),
   - then daily chores before weekly ones (a skipped daily chore is a missed day; a weekly one can wait),
   - then shorter tasks first, so more of them fit.

   It walks down that list keeping each task if there's still time. Tasks with a fixed time are booked at that time; if two appointments overlap, the higher-ranked one keeps the slot and the other is skipped as a conflict. Then the flexible tasks fill the earliest free gaps from 08:00, around the appointments, so nothing ever overlaps and a flexible task never pushes an appointment out.
5. **The plan explains itself.** The result is a `DailyPlan`: scheduled tasks in clock order with start and end times, plus a list of skipped tasks. Every entry carries a short reason: why it was chosen and how much of the budget is used once it's done — "high priority, daily task, earliest free slot; 65/90 min used after this" — and every skipped task says why it was left out — "conflicts with Meds (Biscuit) at 09:20–09:30", "no free slot left today" or "not enough time left (needs 45 min, only 10 min remaining)". `explain()` reads those reasons back.

**Why it's built this way**

- **Each class has one job.** Pets and tasks just hold information; only the scheduler makes choices; the plan just reports the result. Changing one part rarely breaks another.
- **The scheduler only talks to the owner.** It never digs into individual pets, so how pets are stored can change without touching the scheduling logic.
- **Same input, same plan.** The scheduler keeps no memory between runs, which makes its behavior predictable and easy to test.

**Trying it out**

- `python main.py` builds a sample owner with two pets (a dog and a cat), prints their tasks as added, sorted by time (`sort_by_time()`) and filtered by pet and status (`filter_tasks()`), then prints today's schedule as a table, followed by the full `explain()` text.
- `streamlit run app.py` opens the interactive app (see the walkthrough below).
- `pytest` runs both test files: `tests/test_pawpal.py` (the logic layer) and `tests/test_app.py` (the Streamlit app, driven headlessly).

## 🖥️ Sample Output

Output of `python main.py` (terminal demo — one owner with 90 minutes, a dog and a cat, nine tasks; four have fixed times and are added out of clock order — 17:00, 07:30, 18:00, 08:15 — and one weekly task is already completed today). Dates are whatever day you run it:

```
==============================================================
  🐾 TASKS
==============================================================
  As added (pet order)
  ------------------------------------------------------------
  flexible  Feeding         Biscuit  due 2026-10-23  to do
  17:00     Grooming        Biscuit  due 2026-10-23  to do
  07:30     Morning walk    Biscuit  due 2026-10-23  to do
  flexible  Heartworm pill  Biscuit  due 2026-10-23  done
  flexible  Heartworm pill  Biscuit  due 2026-10-30  to do
  flexible  Feeding         Mochi    due 2026-10-23  to do
  flexible  Litter box      Mochi    due 2026-10-23  to do
  18:00     Play session    Mochi    due 2026-10-23  to do
  flexible  Nail trim       Mochi    due 2026-10-23  to do
  08:15     Vet call        Mochi    due 2026-10-23  to do

  Sorted by time — sort_by_time()
  ------------------------------------------------------------
  07:30     Morning walk    Biscuit  due 2026-10-23  to do
  08:15     Vet call        Mochi    due 2026-10-23  to do
  17:00     Grooming        Biscuit  due 2026-10-23  to do
  18:00     Play session    Mochi    due 2026-10-23  to do
  flexible  Feeding         Biscuit  due 2026-10-23  to do
  flexible  Heartworm pill  Biscuit  due 2026-10-23  done
  flexible  Heartworm pill  Biscuit  due 2026-10-30  to do
  flexible  Feeding         Mochi    due 2026-10-23  to do
  flexible  Litter box      Mochi    due 2026-10-23  to do
  flexible  Nail trim       Mochi    due 2026-10-23  to do

  Mochi only — filter_tasks(pet_name="Mochi")
  ------------------------------------------------------------
  flexible  Feeding       Mochi  due 2026-10-23  to do
  flexible  Litter box    Mochi  due 2026-10-23  to do
  18:00     Play session  Mochi  due 2026-10-23  to do
  flexible  Nail trim     Mochi  due 2026-10-23  to do
  08:15     Vet call      Mochi  due 2026-10-23  to do

  Done — filter_tasks(completed=True)
  ------------------------------------------------------------
  flexible  Heartworm pill  Biscuit  due 2026-10-23  done

  Biscuit, to do — filter_tasks(completed=False, pet_name="Biscuit")
  ------------------------------------------------------------
  flexible  Feeding         Biscuit  due 2026-10-23  to do
  17:00     Grooming        Biscuit  due 2026-10-23  to do
  07:30     Morning walk    Biscuit  due 2026-10-23  to do
  flexible  Heartworm pill  Biscuit  due 2026-10-30  to do

==============================================================
  🐾 TODAY'S SCHEDULE
  Owner: Jordan   Pets: Biscuit (dog), Mochi (cat)
  Time available: 90 min
==============================================================
  TIME          TASK          PET       MIN  PRIORITY
  ------------------------------------------------------------
  07:30–08:00   Morning walk  Biscuit    30  HIGH 📌
  08:00–08:10   Feeding       Biscuit    10  HIGH
  08:15–08:30   Vet call      Mochi      15  MEDIUM 📌
  08:30–08:40   Feeding       Mochi      10  HIGH
  08:40–08:55   Litter box    Mochi      15  MEDIUM

  SKIPPED
  ------------------------------------------------------------
  ✗ Play session  Mochi    not enough time left (needs 20 min, only 10 min remaining)
  ✗ Nail trim     Mochi    not enough time left (needs 15 min, only 10 min remaining)
  ✗ Grooming      Biscuit  not enough time left (needs 45 min, only 10 min remaining)

  Why: priority (high → low), then daily before weekly, then
  shortest first; 📌 tasks keep their fixed time, the rest fill
  the earliest free gaps from 08:00 until the time runs out.
==============================================================
  5 tasks scheduled · 80/90 min used · 10 min free
==============================================================

Details (DailyPlan.explain()):
07:30–08:00 — Morning walk (30 min, Biscuit) [priority: high] — high priority, daily task, fixed time 07:30; 30/90 min used after this
08:00–08:10 — Feeding (10 min, Biscuit) [priority: high] — high priority, daily task, earliest free slot; 40/90 min used after this
08:15–08:30 — Vet call (15 min, Mochi) [priority: medium] — medium priority, daily task, fixed time 08:15; 55/90 min used after this
08:30–08:40 — Feeding (10 min, Mochi) [priority: high] — high priority, daily task, earliest free slot; 65/90 min used after this
08:40–08:55 — Litter box (15 min, Mochi) [priority: medium] — medium priority, daily task, earliest free slot; 80/90 min used after this
Skipped: Play session (Mochi) — not enough time left (needs 20 min, only 10 min remaining)
Skipped: Nail trim (Mochi) — not enough time left (needs 15 min, only 10 min remaining)
Skipped: Grooming (Biscuit) — not enough time left (needs 45 min, only 10 min remaining)
```

What to look for:

- **Sorting** — in "As added", the fixed times appear as 17:00, 07:30, 18:00, 08:15. `sort_by_time()` puts them in clock order (07:30, 08:15, 17:00, 18:00), followed by the flexible tasks in the order they were added.
- **Filtering** — `filter_tasks()` narrows the same list by pet, by status, or both. The "done" filter finds today's completed Heartworm pill; the "Biscuit, to do" filter shows next week's dose that `complete_task()` booked.
- **Schedule** — the completed Heartworm pill isn't planned, and next week's isn't due yet. Biscuit's Morning walk keeps its 07:30 slot and Mochi's Vet call keeps 08:15. Mochi's Feeding doesn't fit in the 5-minute gap before the Vet call, so it moves to 08:30. Play session (18:00) and Grooming (17:00) have fixed times but rank below the other tasks and need more than the 10 minutes left, so they're skipped.

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest

# Run with coverage (needs `pip install pytest-cov`, not in requirements.txt):
pytest --cov
```

`pytest.ini` points pytest at the `tests/` folder and adds the project root to the import path, so plain `pytest` works from the project folder.

There are 90 tests in two files:

| File | What it checks |
|------|----------------|
| `tests/test_pawpal.py` (71) | Task creation and validation (duration, priority, frequency, time); `mark_complete()` (and the next occurrence it creates); adding, editing and removing tasks and pets; the duplicate-task rule; priority ordering and tie-breaks; the time budget and skip reasons; fixed-time booking, gap filling around appointments, conflicts, back-to-back tasks, tasks past midnight; refunding the minutes of a task that finds no free slot; running budget totals in reasons; skipped tasks in rank order; start-time order and `end_time`; recurrence (`next_occurrence()`, `complete_task()`), due dates and overdue tasks; `sort_by_time()`; `filter_tasks()` by status, by pet and both together; multi-pet and empty plans. |
| `tests/test_app.py` (19) | The Streamlit app run headlessly with `AppTest`: adding pets and tasks (including fixed times), error messages for blank/duplicate/invalid input, state surviving reruns, Mark complete, Delete task, the edit form, Remove pet, the pet and status filters (including no matches), and the generated schedule, skipped table and explanation. |

Result of the last run:

```
============================== 90 passed in 3.71s ==============================
```

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler._rank_tasks()` | Priority (high → medium → low), then daily before weekly, then shortest first. Stable sort, so the same input always gives the same order. |
| Sort by time | `Scheduler.sort_by_time()` | `sorted()` with a lambda key `lambda t: (t.time is None, t.time or "")`: timed tasks earliest first, flexible tasks after in their original order. Plain `"HH:MM"` string comparison is safe because `Task` only accepts zero-padded times. Used for the app's task table. |
| Filtering | `Scheduler.build_plan()`, `Scheduler._fits_in_budget()`, `Task.mark_complete()` | Completed tasks and tasks not yet due are left out. A task that doesn't fit the remaining time waits; the loop keeps going, so a smaller task further down can still fit. If a flexible task finds no free slot, its minutes are refunded, and waiting tasks get a second try with what's left before being skipped with a reason. |
| Fixed times | `Task.time`, `Scheduler.build_plan()`, `Scheduler._first_free_slot()` | Fixed-time tasks are booked at their time; flexible tasks fill the earliest free gaps from 08:00 around them. Entries are returned in clock order. |
| Conflict handling | `Scheduler._find_conflict()` | Two fixed-time tasks that overlap: the higher-ranked one keeps the slot, the other is skipped with "conflicts with …". Tasks that only touch (one ends at 09:30, the next starts at 09:30) don't conflict. A fixed task running past midnight is skipped. |
| Recurring tasks | `Task.mark_complete()`, `Task.next_occurrence()`, `Pet.complete_task()`, `Task.due_date` | Marking a task complete creates its next occurrence, due today + `timedelta(days=1)` for a daily task or `timedelta(days=7)` for a weekly one; `Pet.complete_task()` adds that new task to the pet's list. Counting from the day it's completed means finishing an overdue task doesn't book another overdue one; a task finished early counts from its due date instead. `timedelta` handles month and year ends (Oct 31 → Nov 1, Dec 31 → Jan 1). The scheduler only plans tasks due on the plan day; overdue tasks are still planned and their reason says "overdue since …". |
| Filtering by status or pet | `Owner.filter_tasks()` | `filter_tasks(completed=False)` gives unfinished tasks, `filter_tasks(pet_name="Mochi")` gives Mochi's, and both together give Mochi's unfinished tasks. Leaving a filter as `None` matches everything. It returns the owner's real `Task` objects, so changes to them stick. Used by the **Show pet** / **Show status** filters in the app. |
| Editing | `Pet.edit_task()`, `Pet.remove_task()`, `Owner.remove_pet()` | Edits are validated on a copy first, so a bad edit changes nothing. |

## 📸 Demo Walkthrough

**Terminal demo (`main.py`)**:

1. Set up the environment (see [Setup](#setup)) and run `python main.py` from the project folder.
2. The script creates an owner, Jordan, with 90 minutes free today, and two pets: Biscuit (dog) and Mochi (cat).
3. It adds nine tasks across the two pets, with different durations, priorities and frequencies. Four have fixed times, added out of clock order: Biscuit's "Grooming" (17:00), Biscuit's "Morning walk" (07:30), Mochi's "Play session" (18:00) and Mochi's "Vet call" (08:15). Biscuit's weekly "Heartworm pill" is completed with `complete_task()`, which books next week's dose.
4. A **Tasks** section prints the tasks as added, then sorted with `Scheduler.sort_by_time()`, then filtered with `Owner.filter_tasks()`: Mochi's tasks only, completed tasks only, and Biscuit's unfinished tasks.
5. The `Scheduler` builds the plan and the terminal prints a "Today's Schedule" table in clock order: each task's time slot, pet, length and priority, with 📌 marking fixed-time tasks.
6. Below the table, a "Skipped" section lists the tasks that didn't make it and why, then a one-line summary of time used and time left, and finally the full `DailyPlan.explain()` text (shown in Sample Output above).

**Streamlit app (`app.py`)**:

1. Run `streamlit run app.py` and open the local URL it prints (usually http://localhost:8501).
2. **Owner** — enter your name and how many minutes you have today (default 60). This is the time budget the scheduler must fit into.
3. **Add a Pet** — type a pet name, pick a species, and click **Add pet**. Repeat for each pet. A blank name or a pet you've already added is rejected with a message. **Remove a pet** (in the expander) deletes a pet and all its tasks.
4. **Add a Task** — choose which pet the task is for, then enter a title, duration, priority and frequency (daily/weekly), and optionally a **fixed time** like `09:00` (leave it blank for a flexible task). Click **Add task**. Invalid input (a blank title, a time like `9am`, or the same unfinished task twice) shows an error instead of being saved.
5. **Your Tasks** — every task across all pets, fixed-time ones first in clock order, with its due date and a ✓ when done. Use **Show pet** and **Show status** (All / To do / Done) to narrow the list, e.g. only Mochi's unfinished tasks; a caption shows how many of the tasks are listed. Choose a task in the dropdown (it lists only the tasks shown), then:
   - **Mark complete** — ticks it off and adds the next occurrence (tomorrow, or in a week);
   - **Delete task** — removes it;
   - **Edit this task** — change its title, duration, priority, frequency or time and click **Save changes**.
6. **Build Schedule** — click **Generate schedule**. PawPal+ shows:
   - a **Today's Schedule** table in clock order: start, end, task (📌 = fixed time), pet, minutes, priority, and *why* it was chosen;
   - a **Skipped** table for tasks that didn't make it, each with the reason (not enough time, a conflict with another appointment, …);
   - a **Plan explanation** expander with the `explain()` text;
   - a summary line: tasks scheduled, minutes used out of the budget, and tasks skipped.
7. Change the time available or the tasks, then click **Generate schedule** again to see the plan update. Pets and tasks stay in place between clicks because the `Owner` is kept in `st.session_state`.

For example, with 40 minutes and three tasks (Mochi's 10-min high-priority Feeding, Biscuit's 30-min high-priority Walk, and Mochi's 45-min low-priority Grooming), the plan schedules Feeding at 08:00 and Walk at 08:10, and skips Grooming. Give Walk a fixed time of 09:00 and it moves there, while Feeding stays at 08:00.

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
